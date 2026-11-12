import random,statistics,math
from src.services.scheduler import schedule,schedule_variable,normalize_schedule
def simulate(arrival_rate,service_rate,windows,duration,warmup,replications,seed,window_schedule=None):
 if arrival_rate<=0 or service_rate<=0 or windows<1 or duration<=0 or warmup<0 or replications<2:raise ValueError("无效仿真参数")
 if arrival_rate*(duration+warmup)>20000:raise ValueError("预期到达超过20000条，请缩短时域或降低负荷")
 end=warmup+duration
 if window_schedule:
  segments=normalize_schedule(window_schedule,end)
  variable=True
 else:
  segments=[{"start":0,"end":end,"windows":windows}];variable=False
 results=[];last_events=[];segment_summaries=[]
 for rep in range(replications):
  rng=random.Random(seed+rep);arrivals=[];services=[];t=0
  while True:
   t+=rng.expovariate(arrival_rate)
   if t>=end:break
   arrivals.append(t);services.append(rng.expovariate(service_rate))
   if len(arrivals)>50000:raise ValueError("单次仿真事件超过50000条")
  if variable:
   events=schedule_variable(arrivals,services,segments)
   seg_stats=_segment_stats(events,segments,warmup,end)
  else:
   events=schedule(arrivals,services,windows)
  observed=[e for e in events if e["arrival"]>=warmup]
  if not observed:raise ValueError("观测时域没有到达，请增大时域")
  waits=[e["wait"] for e in observed]
  busy=sum(max(0,min(e["end"],end)-max(e["start"],warmup)) for e in events)
  capacity_minutes=sum(seg["windows"]*max(0,min(seg["end"],end)-max(seg["start"],warmup)) for seg in segments)
  row={"replication":rep+1,"arrivals":len(observed),"mean_wait_minutes":statistics.mean(waits),"p_wait":sum(x>1e-9 for x in waits)/len(waits),"max_wait_minutes":max(waits),"busy_fraction":busy/capacity_minutes}
  if variable:
   row["segments"]=seg_stats
   segment_summaries.append(seg_stats)
  results.append(row)
  last_events=observed[:80]
 means=[r["mean_wait_minutes"] for r in results];mean=statistics.mean(means);se=statistics.stdev(means)/math.sqrt(replications)
 payload={"mean_wait_minutes":mean,"mean_wait_ci95":[max(0,mean-1.96*se),mean+1.96*se],"p_wait":statistics.mean(r["p_wait"] for r in results),"busy_fraction":statistics.mean(r["busy_fraction"] for r in results),"replications":results,"timeline":last_events,"duration_minutes":duration,"warmup_minutes":warmup,"seed":seed,"ci_method":"重复试验均值的正态近似95%区间（1.96×重复均值标准误）"}
 if variable:
  payload["capacity_mode"]="variable"
  payload["window_schedule"]=[{"start":seg["start"],"windows":seg["windows"]} for seg in segments]
  payload["segment_summary"]=_aggregate_segments(segment_summaries,warmup)
 else:
  payload["capacity_mode"]="fixed"
 return payload
def _segment_of(segments,t):
 for seg in segments:
  if seg["start"]<=t<seg["end"]:return seg
 return segments[-1]
def _segment_stats(events,segments,warmup,end):
 """按样本到达所属时段统计观测期内的到达量、等待与实际忙碌比例。
 忙碌按服务区间与“观测期∩时段”的交集积分；时段容量为0时忙碌比例记为 None。"""
 out=[]
 for seg in segments:
  lo=max(seg["start"],warmup);hi=min(seg["end"],end)
  span=max(0,hi-lo)
  members=[e for e in events if warmup<=e["arrival"]<hi and _segment_of(segments,e["arrival"]) is seg]
  waits=[e["wait"] for e in members]
  busy=sum(max(0,min(e["end"],hi)-max(e["start"],lo)) for e in events)
  capacity=seg["windows"]*span
  out.append({"start":seg["start"],"end":seg["end"],"windows":seg["windows"],"observed":span>0,"arrivals":len(members),"mean_wait_minutes":statistics.mean(waits) if waits else None,"p_wait":(sum(w>1e-9 for w in waits)/len(waits)) if waits else None,"busy_minutes":busy,"busy_fraction":(busy/capacity) if capacity>0 else None})
 return out
def _aggregate_segments(per_rep,warmup):
 summary=[]
 for i,seg in enumerate(per_rep[0]):
  rows=[rep[i] for rep in per_rep]
  waits=[r["mean_wait_minutes"] for r in rows if r["mean_wait_minutes"] is not None]
  pwaits=[r["p_wait"] for r in rows if r["p_wait"] is not None]
  busy=[r["busy_fraction"] for r in rows if r["busy_fraction"] is not None]
  summary.append({"start":seg["start"],"end":seg["end"],"windows":seg["windows"],"observed":seg["observed"],"arrivals":statistics.mean(r["arrivals"] for r in rows),"mean_wait_minutes":statistics.mean(waits) if waits else None,"p_wait":statistics.mean(pwaits) if pwaits else None,"busy_fraction":statistics.mean(busy) if busy else None})
 return summary
