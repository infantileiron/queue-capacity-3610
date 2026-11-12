import random,statistics,math
from src.services.scheduler import schedule,schedule_variable,capacity_at
def _segment_stats(events,segments,warmup,end):
 # 时段按仿真起点（含预热）计时；仅统计与观测期有交集的时段
 out=[]
 for k,(start,count) in enumerate(segments):
  stop=segments[k+1][0] if k+1<len(segments) else end
  lo=max(start,warmup);hi=min(stop,end)
  if lo>=hi:
   out.append({"segment":k+1,"start_minute":start,"end_minute":stop,"windows":count,"observed":False,"arrivals":0,"mean_wait_minutes":None,"p_wait":None,"max_wait_minutes":None,"busy_fraction":None})
   continue
  observed=[e for e in events if warmup<=e["arrival"]<end and lo<=e["arrival"]<hi]
  waits=[e["wait"] for e in observed]
  busy=sum(max(0,min(e["end"],hi)-max(e["start"],lo)) for e in events)
  capacity=count*(hi-lo)
  out.append({"segment":k+1,"start_minute":start,"end_minute":stop,"windows":count,"observed":True,"arrivals":len(observed),"mean_wait_minutes":statistics.mean(waits) if waits else None,"p_wait":(sum(x>1e-9 for x in waits)/len(waits)) if waits else None,"max_wait_minutes":max(waits) if waits else None,"busy_fraction":(busy/capacity) if capacity>0 else None})
 return out
def simulate(arrival_rate,service_rate,windows,duration,warmup,replications,seed,window_schedule=None):
 if arrival_rate<=0 or service_rate<=0 or windows<1 or duration<=0 or warmup<0 or replications<2:raise ValueError("无效仿真参数")
 if arrival_rate*(duration+warmup)>20000:raise ValueError("预期到达超过20000条，请缩短时域或降低负荷")
 variable=bool(window_schedule);end=warmup+duration
 if variable:
  from src.services.scheduler import _normalise_segments
  segments=_normalise_segments(window_schedule,end)
 else:
  segments=None
 results=[];segment_rows=[];last_events=[]
 for rep in range(replications):
  rng=random.Random(seed+rep);arrivals=[];services=[];t=0
  while True:
   t+=rng.expovariate(arrival_rate)
   if t>=end:break
   arrivals.append(t);services.append(rng.expovariate(service_rate))
   if len(arrivals)>50000:raise ValueError("单次仿真事件超过50000条")
  if variable:
   events=schedule_variable(arrivals,services,segments,end)
   segment_rows.append(_segment_stats(events,segments,warmup,end))
  else:
   events=schedule(arrivals,services,windows)
  observed=[e for e in events if e["arrival"]>=warmup]
  if not observed:raise ValueError("观测时域没有到达，请增大时域")
  waits=[e["wait"] for e in observed]
  if variable:
   denom=sum(capacity_at(segments,max(warmup,start))*(min(end,stop)-max(warmup,start)) for k,(start,_) in enumerate(segments) for stop in [segments[k+1][0] if k+1<len(segments) else end] if min(end,stop)>max(warmup,start))
   busy=sum(max(0,min(e["end"],end)-max(e["start"],warmup)) for e in events)
   busy_fraction=busy/denom if denom>0 else None
  else:
   busy=sum(max(0,min(e["end"],end)-max(e["start"],warmup)) for e in events)
   busy_fraction=busy/(windows*duration)
  results.append({"replication":rep+1,"arrivals":len(observed),"mean_wait_minutes":statistics.mean(waits),"p_wait":sum(x>1e-9 for x in waits)/len(waits),"max_wait_minutes":max(waits),"busy_fraction":busy_fraction})
  last_events=observed[:80]
 means=[r["mean_wait_minutes"] for r in results];mean=statistics.mean(means);se=statistics.stdev(means)/math.sqrt(replications)
 payload={"mean_wait_minutes":mean,"mean_wait_ci95":[max(0,mean-1.96*se),mean+1.96*se],"p_wait":statistics.mean(r["p_wait"] for r in results),"busy_fraction":(statistics.mean(r["busy_fraction"] for r in results if r["busy_fraction"] is not None) if any(r["busy_fraction"] is not None for r in results) else None),"replications":results,"timeline":last_events,"duration_minutes":duration,"warmup_minutes":warmup,"seed":seed,"ci_method":"重复试验均值的正态近似95%区间（1.96×重复均值标准误）"}
 if variable:
  # 跨重复汇总每个时段：到达量取重复均值，等待与忙碌比例按重复均值聚合
  summaries=[]
  for k,row in enumerate(segment_rows[0]):
   per=[rep_rows[k] for rep_rows in segment_rows]
   waits_v=[p["mean_wait_minutes"] for p in per if p["mean_wait_minutes"] is not None]
   pwaits=[p["p_wait"] for p in per if p["p_wait"] is not None]
   busies=[p["busy_fraction"] for p in per if p["busy_fraction"] is not None]
   maxes=[p["max_wait_minutes"] for p in per if p["max_wait_minutes"] is not None]
   summaries.append({"segment":row["segment"],"start_minute":row["start_minute"],"end_minute":row["end_minute"],"windows":row["windows"],"observed":row["observed"],"arrivals":statistics.mean(p["arrivals"] for p in per),"mean_wait_minutes":statistics.mean(waits_v) if waits_v else None,"p_wait":statistics.mean(pwaits) if pwaits else None,"max_wait_minutes":max(maxes) if maxes else None,"busy_fraction":statistics.mean(busies) if busies else None})
  payload.update({"capacity_mode":"variable","window_schedule":[{"start_minute":s,"windows":c} for s,c in segments],"segment_summaries":summaries})
 else:
  payload["capacity_mode"]="fixed"
 return payload
