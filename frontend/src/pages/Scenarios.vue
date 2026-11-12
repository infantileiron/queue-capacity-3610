<script setup lang="ts">
import {ref,computed} from 'vue';
import type {Workspace} from '../stores/workspace';
import type {ScheduleSegment} from '../types/domain';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
import Status from '../components/common/Status.vue';
import {create} from '../api/scenarios';
import {create as run} from '../api/runs';
import {useAsync} from '../hooks/useAsync';
const props=defineProps<{data:Workspace;canWrite:boolean;refresh:()=>Promise<void>}>();
const emit=defineEmits<{go:[string]}>();
const name=ref(''),profile=ref(''),windows=ref(3),arrival=ref(1),service=ref(1),duration=ref(480),warmup=ref(120),reps=ref(30),seed=ref(2206);
const mode=ref<'fixed'|'variable'>('fixed');
const segments=ref<ScheduleSegment[]>([{start:0,windows:3},{start:300,windows:0},{start:480,windows:4}]);
const {busy,error,execute}=useAsync();
const horizon=computed(()=>(duration.value||0)+(warmup.value||0));
const maxSegmentWindows=computed(()=>Math.max(1,...segments.value.map(s=>s.windows||0)));
function addSegment(){segments.value.push({start:horizon.value-60,windows:1})}
function removeSegment(i:number){if(segments.value.length>1)segments.value.splice(i,1)}
function scheduleLabel(s:Workspace['scenarios'][number]):string{
 if(!s.window_schedule)return `${s.windows}窗全日固定`;
 return s.window_schedule.map(seg=>`${seg.start}′起${seg.windows}窗`).join(' → ');
}
async function submit(){
 await execute(async()=>{
  const payload:Record<string,unknown>={name:name.value,profile_id:profile.value||props.data.profiles[0]?.id,
   arrival_multiplier:arrival.value,service_multiplier:service.value,
   duration_minutes:duration.value,warmup_minutes:warmup.value,replications:reps.value,seed:seed.value};
  if(mode.value==='fixed'){payload.windows=windows.value}
  else{
   const ordered=[...segments.value].sort((a,b)=>a.start-b.start);
   payload.windows=Math.max(...ordered.map(s=>s.windows));
   payload.window_schedule=ordered;
  }
  await create(payload);name.value='';await props.refresh();
 });
}
async function launch(id:string){
 await execute(async()=>{await run({scenario_id:id});await props.refresh();emit('go','results')});
}
</script>
<template>
 <PageHeading code="04 / COUNTER SCENARIOS" title="窗口数之外，把假设也写下来。" description="到达倍率作用于λ，服务倍率作用于单窗口μ。支持全日固定开窗与按时段变窗；固定随机种子保证同一输入和配置可复现。"/>
 <section v-if="canWrite" class="paper">
  <h2>新建窗口预演</h2>
  <div class="mode-switch" role="group" aria-label="开窗模式">
   <button type="button" :class="{active:mode==='fixed'}" @click="mode='fixed'">固定开窗（稳态口径）</button>
   <button type="button" class="secondary" :class="{active:mode==='variable'}" @click="mode='variable'">分时段变窗（暂态口径）</button>
  </div>
  <form class="scenario-form" @submit.prevent="submit">
   <label>方案名称<input aria-label="方案名称" v-model="name" required minlength="2"/></label>
   <label>输入剖面<select aria-label="输入剖面" v-model="profile"><option value="" disabled>默认使用最新剖面</option><option v-for="p in data.profiles" :key="p.id" :value="p.id">{{p.name}}</option></select></label>
   <label v-if="mode==='fixed'">窗口数 c<input aria-label="窗口数" type="number" min="1" max="12" v-model.number="windows"/></label>
   <label>到达倍率<input type="number" min=".2" max="3" step=".1" v-model.number="arrival"/></label>
   <label>服务倍率<input type="number" min=".2" max="3" step=".1" v-model.number="service"/></label>
   <label>观测时域 / 分钟<input type="number" min="60" max="1440" v-model.number="duration"/></label>
   <label>预热 / 分钟<input type="number" min="0" max="1440" v-model.number="warmup"/></label>
   <label>重复次数<input aria-label="重复次数" type="number" min="5" max="100" v-model.number="reps"/></label>
   <label>随机种子<input type="number" min="0" v-model.number="seed"/></label>
   <div v-if="mode==='variable'" class="wide schedule-editor">
    <div class="schedule-head">
     <h3>分时段开窗配置</h3>
     <button type="button" class="text-button" @click="addSegment">＋ 添加时段</button>
    </div>
    <p class="schedule-hint">时间为仿真钟分钟（0 = 仿真开始，含预热 {{warmup}} 分钟，总时域 {{horizon}} 分钟）。首段须从 0 开始，末段至少保留 1 个窗口；开窗数可填 0 表示停窗，停窗窗口办完手中样本后退出，排队样本恢复开窗后按到达顺序办理。</p>
    <div class="segment-row" v-for="(seg,i) in segments" :key="i">
     <label>起点 / 分钟<input type="number" min="0" :max="horizon" v-model.number="seg.start" :disabled="i===0"/></label>
     <label>开窗数量（0—12）<input type="number" min="0" max="12" v-model.number="seg.windows"/></label>
     <button type="button" class="text-button" :disabled="i===0||segments.length<=1" @click="removeSegment(i)">删除</button>
    </div>
    <small>最大开窗数 {{maxSegmentWindows}} 将作为方案窗口上限保存；跨越预热（{{warmup}}′）的调窗会延续队列与在办样本。</small>
   </div>
   <button :disabled="busy">保存窗口方案</button>
  </form>
 </section>
 <Notice v-if="error" error>{{error}}</Notice>
 <section class="paper">
  <h2>已保存方案</h2>
  <article v-for="s in data.scenarios" :key="s.id" class="scenario-row">
   <div class="counter-number">{{s.window_schedule?Math.max(...s.window_schedule.map(x=>x.windows)):s.windows}}<small>{{s.window_schedule?'MAX WINDOWS':'WINDOWS'}}</small></div>
   <div class="scenario-detail">
    <h3>{{s.name}} <span class="mode-tag" :class="s.window_schedule?'variable':'fixed'">{{s.window_schedule?'分时段变窗':'固定开窗'}}</span></h3>
    <p>{{data.profiles.find(p=>p.id===s.profile_id)?.name}}</p>
    <small>{{scheduleLabel(s)}} · 观测{{s.duration_minutes}}分钟 · 预热{{s.warmup_minutes}}分钟 · {{s.replications}}次重复 · seed {{s.seed}}</small>
   </div>
   <button class="secondary" v-if="canWrite" :disabled="busy" @click="launch(s.id)">运行预演　→</button>
  </article>
 </section>
 <section class="paper">
  <h2>运行队列</h2>
  <div class="table-scroll">
   <table><thead><tr><th>窗口方案</th><th>状态</th><th>提交时间</th></tr></thead>
   <tbody><tr v-for="r in data.runs" :key="r.id"><td>{{data.scenarios.find(s=>s.id===r.scenario_id)?.name}}</td><td><Status :value="r.status"/></td><td>{{r.created_at.slice(0,19).replace('T',' ')}}</td></tr></tbody></table>
  </div>
 </section>
</template>
