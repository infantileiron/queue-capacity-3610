<script setup lang="ts">
import {ref,computed} from 'vue';
import type {Workspace} from '../stores/workspace';
import type {WindowSegment} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import Status from '../components/common/Status.vue';
import {create} from '../api/scenarios';
import {create as run} from '../api/runs';
import {useAsync} from '../hooks/useAsync';
const props=defineProps<{data:Workspace;canWrite:boolean;refresh:()=>Promise<void>}>();
const emit=defineEmits<{go:[string]}>();
const name=ref(''),profile=ref(''),windows=ref(3),arrival=ref(1),service=ref(1),duration=ref(480),warmup=ref(120),reps=ref(30),seed=ref(2206);
const variable=ref(false);
const segments=ref<WindowSegment[]>([{start_minute:0,windows:3}]);
const {busy,error,execute}=useAsync();
const horizon=computed(()=>duration.value+warmup.value);
function addSegment(){const last=segments.value[segments.value.length-1];segments.value.push({start_minute:Math.min(horizon.value-1,(last?.start_minute??0)+120),windows:last?.windows??windows.value});}
function removeSegment(i:number){segments.value.splice(i,1);}
function setVariable(on:boolean){if(on&&segments.value.length)segments.value[0].windows=windows.value;variable.value=on;}
const segmentError=computed(()=>{
 if(!variable.value)return '';
 if(segments.value.length===0)return '请至少配置一个时段';
 if(segments.value[0].start_minute!==0)return '首个时段须从第0分钟开始（时间轴含预热）';
 for(let i=1;i<segments.value.length;i++)if(segments.value[i].start_minute<=segments.value[i-1].start_minute)return '时段起点须严格递增';
 if(segments.value[segments.value.length-1].start_minute>=horizon.value)return '时段配置超出预热与观测总时域（'+horizon.value+'分钟）';
 if(!segments.value.some(s=>s.windows>0))return '至少需要一个开窗数大于0的时段';
 if(segments.value[segments.value.length-1].windows<=0)return '末段开窗数须大于0：停窗后须恢复开窗，排队样本才能全部办理';
 if(segments.value.some(s=>s.windows<0||s.windows>12))return '开窗数须在0—12之间（0表示停窗）';
 return '';
});
const scheduleLabel=(s:Workspace['scenarios'][number])=>{
 if(!s.window_schedule||s.window_schedule.length<=1)return `${s.windows}窗固定`;
 return s.window_schedule.map(g=>`${g.windows}窗@${g.start_minute}′`).join(' → ');
};
async function submit(){
 await execute(async()=>{
  const peakWindows=variable.value?Math.max(0,...segments.value.map(s=>Math.trunc(s.windows))):windows.value;
  const payload={name:name.value,profile_id:profile.value||props.data.profiles[0]?.id,windows:peakWindows,arrival_multiplier:arrival.value,service_multiplier:service.value,duration_minutes:duration.value,warmup_minutes:warmup.value,replications:reps.value,seed:seed.value,window_schedule:variable.value?segments.value.map(s=>({start_minute:Math.trunc(s.start_minute),windows:Math.trunc(s.windows)})):null};
  await create(payload);name.value='';await props.refresh();
 });
}
async function launch(id:string){await execute(async()=>{await run({scenario_id:id});await props.refresh();emit('go','results');});}
</script>
<template><PageHeading code="04 / COUNTER SCENARIOS" title="窗口数之外，把假设也写下来。" description="到达倍率作用于λ，服务倍率作用于单窗口μ。支持按时段调窗：停窗办完手中样本再退出，零容量期间排队样本恢复开窗后按到达顺序办理。固定随机种子保证可复现。"/>
<section v-if="canWrite" class="paper"><h2>新建窗口预演</h2>
 <div class="mode-switch" role="group" aria-label="开窗模式">
  <button type="button" :class="{active:!variable}" @click="setVariable(false)">固定开窗（稳态口径）</button>
  <button type="button" :class="{active:variable}" @click="setVariable(true)">按时段变窗（暂态口径）</button>
 </div>
 <form class="scenario-form" @submit.prevent="submit">
  <label>方案名称<input aria-label="方案名称" v-model="name" required minlength="2"/></label>
  <label>输入剖面<select aria-label="输入剖面" v-model="profile"><option value="" disabled>默认使用最新剖面</option><option v-for="p in data.profiles" :key="p.id" :value="p.id">{{p.name}}</option></select></label>
  <label v-if="!variable">窗口数 c<input aria-label="窗口数" type="number" min="1" max="12" v-model.number="windows"/></label>
  <label>到达倍率<input type="number" min=".2" max="3" step=".1" v-model.number="arrival"/></label>
  <label>服务倍率<input type="number" min=".2" max="3" step=".1" v-model.number="service"/></label>
  <label>观测时域 / 分钟<input type="number" min="60" max="1440" v-model.number="duration"/></label>
  <label>预热 / 分钟<input type="number" min="0" max="1440" v-model.number="warmup"/></label>
  <label>重复次数<input aria-label="重复次数" type="number" min="5" max="100" v-model.number="reps"/></label>
  <label>随机种子<input type="number" min="0" v-model.number="seed"/></label>
  <div v-if="variable" class="wide segment-editor">
   <div class="segment-head"><b>分时段开窗（时间轴从0开始，含{{warmup}}分钟预热；0窗=停窗）</b><button type="button" class="secondary" @click="addSegment">＋ 添加时段</button></div>
   <div class="segment-row" v-for="(g,i) in segments" :key="i">
    <small>时段{{i+1}}{{i===0?'（起）':''}}</small>
    <label>起始分钟<input type="number" min="0" :max="horizon-1" :disabled="i===0" v-model.number="g.start_minute"/></label>
    <label>开窗数<input type="number" min="0" max="12" v-model.number="g.windows"/></label>
    <button type="button" class="text-button" :disabled="i===0" @click="removeSegment(i)">删除</button>
   </div>
   <p class="segment-tip">示例：3窗@0′ → 0窗@{{Math.min(180,horizon-1)}}′（午间停窗）→ 3窗@{{Math.min(240,horizon-1)}}′ → 4窗@{{Math.min(360,horizon-1)}}′（下午增窗）。停窗窗口办完在办样本后退出，排队样本不丢失。</p>
  </div>
  <Notice v-if="segmentError" error>{{segmentError}}</Notice>
  <button :disabled="busy||!!segmentError">保存窗口方案</button>
 </form>
</section>
<Notice v-if="error" error>{{error}}</Notice>
<section class="paper"><h2>已保存方案</h2>
 <article v-for="s in data.scenarios" :key="s.id" class="scenario-row">
  <div class="counter-number">{{s.window_schedule&&s.window_schedule.length>1?'变':s.windows}}<small>{{s.window_schedule&&s.window_schedule.length>1?'VARIABLE':'WINDOWS'}}</small></div>
  <div class="scenario-detail"><h3>{{s.name}}</h3><p>{{data.profiles.find(p=>p.id===s.profile_id)?.name}}</p><small>{{scheduleLabel(s)}} · 观测{{s.duration_minutes}}分钟 · 预热{{s.warmup_minutes}}分钟 · {{s.replications}}次重复 · seed {{s.seed}}</small></div>
  <button class="secondary" v-if="canWrite" :disabled="busy" @click="launch(s.id)">运行预演　→</button>
 </article>
</section>
<section class="paper"><h2>运行队列</h2><div class="table-scroll"><table><thead><tr><th>窗口方案</th><th>状态</th><th>提交时间</th></tr></thead><tbody><tr v-for="r in data.runs" :key="r.id"><td>{{data.scenarios.find(s=>s.id===r.scenario_id)?.name}}</td><td><Status :value="r.status"/></td><td>{{r.created_at.slice(0,19).replace('T',' ')}}</td></tr></tbody></table></div></section>
</template>
