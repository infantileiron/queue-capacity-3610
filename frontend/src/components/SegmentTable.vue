<script setup lang="ts">
import type {SegmentSummary} from '../types/domain';
import {number,percent} from '../utils/format';
defineProps<{rows:SegmentSummary[];warmup:number}>();
const clock=(m:number,w:number)=>{const total=m-w;const hh=String(9+Math.floor(total/60)).padStart(2,'0');const mm=String(total%60).padStart(2,'0');return `${hh}:${mm}`;};
</script>
<template><div class="table-scroll"><table><thead><tr><th>时段（仿真分钟 / 时钟）</th><th>开窗数</th><th>到达量（重复均值）</th><th>平均等待</th><th>等待概率</th><th>最长等待</th><th>实际忙碌比例</th></tr></thead><tbody>
 <tr v-for="r in rows" :key="r.segment" :class="{closed:r.windows===0}">
  <td><b>第{{r.segment}}时段 {{r.start_minute}}′—{{r.end_minute}}′</b><small v-if="r.observed">{{clock(r.start_minute,warmup)}}—{{clock(r.end_minute,warmup)}}（观测期）</small><small v-else>仅位于预热期，不计入观测</small></td>
  <td><b>{{r.windows}}</b><small v-if="r.windows===0">停窗：样本排队保留</small></td>
  <td>{{number(r.arrivals,1)}}</td>
  <td>{{r.mean_wait_minutes==null?'—':number(r.mean_wait_minutes)+' 分钟'}}</td>
  <td>{{r.p_wait==null?'—':percent(r.p_wait)}}</td>
  <td>{{r.max_wait_minutes==null?'—':number(r.max_wait_minutes)+' 分钟'}}</td>
  <td>{{r.busy_fraction==null?'无容量':percent(r.busy_fraction)}}<small v-if="r.busy_fraction!=null&&r.busy_fraction>1">停窗窗口办完在办样本的溢出</small></td>
 </tr>
</tbody></table></div></template>
