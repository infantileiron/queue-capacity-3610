<script setup lang="ts">
import type {SegmentStat} from '../types/domain';
import {number,percent} from '../utils/format';
const props=defineProps<{rows:SegmentStat[];warmup:number}>();
const clock=(t:number)=>`${t}′`;
const range=(r:SegmentStat)=>`${clock(r.start)}–${clock(r.end)}`;
</script>
<template>
 <div class="table-scroll">
  <table class="segment-table">
   <thead><tr><th>时段（仿真钟）</th><th>开窗数</th><th>区间属性</th><th>到达量（次重复均值）</th><th>平均等待 / 分钟</th><th>等待概率</th><th>实际忙碌比例</th></tr></thead>
   <tbody>
    <tr v-for="r in rows" :key="r.start" :class="{zero:r.windows===0,warm:!r.observed}">
     <td><b>{{range(r)}}</b><small v-if="r.start<warmup">含预热段</small></td>
     <td>{{r.windows===0?'停窗（0窗）':r.windows}}</td>
     <td>{{r.observed?'观测期内':'仅预热（不计观测）'}}</td>
     <td>{{number(r.arrivals,1)}}</td>
     <td>{{r.mean_wait_minutes==null?'—':number(r.mean_wait_minutes)}}</td>
     <td>{{r.p_wait==null?'—':percent(r.p_wait)}}</td>
     <td>{{r.busy_fraction==null?'容量为0，留空':percent(r.busy_fraction)}}</td>
    </tr>
   </tbody>
  </table>
 </div>
 <small class="segment-footnote">到达量按样本到达所属时段归属；忙碌按服务区间与“观测期∩时段”交集积分，分母为该时段名义开窗容量。停窗时段到达样本排队等待恢复开窗，故其等待体现在后续时段。</small>
</template>
