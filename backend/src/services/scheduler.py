import heapq,math
def schedule(arrivals,services,windows):
 if len(arrivals)!=len(services) or windows<1: raise ValueError("到达与服务长度须一致，窗口数须为正")
 if any(not math.isfinite(x) or x<0 for x in arrivals) or any(not math.isfinite(x) or x<=0 for x in services): raise ValueError("到达须有限非负、服务须为有限正数")
 if any(a>b for a,b in zip(arrivals,arrivals[1:])): raise ValueError("到达时间须递增")
 servers=[(0.0,i+1) for i in range(windows)];heapq.heapify(servers);events=[]
 for i,(arrival,service) in enumerate(zip(arrivals,services)):
  free,server=heapq.heappop(servers);start=max(arrival,free);end=start+service
  events.append({"job":i+1,"arrival":arrival,"service":service,"start":start,"end":end,"wait":start-arrival,"server":server})
  heapq.heappush(servers,(end,server))
 return events
def _normalise_segments(segments,horizon):
 if not isinstance(segments,list) or not segments:raise ValueError("变窗时段至少需要一个时段")
 norm=[]
 for seg in segments:
  if isinstance(seg,dict):
   if "start_minute" not in seg or "windows" not in seg:raise ValueError("变窗时段须包含start_minute与windows")
   start=seg["start_minute"];count=seg["windows"]
  elif isinstance(seg,(tuple,list)) and len(seg)==2:
   start,count=seg
  else:raise ValueError("变窗时段格式无效")
  if not isinstance(start,int) or not isinstance(count,int) or start<0 or count<0 or count>12:raise ValueError("时段起点须为非负整数、开窗数须为0—12的整数")
  norm.append((start,count))
 if any(a[0]>=b[0] for a,b in zip(norm,norm[1:])):raise ValueError("时段起点须严格递增")
 if norm[0][0]!=0:raise ValueError("首个时段须从第0分钟开始")
 if len(norm)>24:raise ValueError("变窗时段最多24段")
 if not any(count>0 for _,count in norm):raise ValueError("至少需要一个开窗数大于0的时段")
 if norm[-1][1]<=0:raise ValueError("末段开窗数须大于0：停窗后须恢复开窗，排队样本才能全部办理")
 if norm[-1][0]>=horizon:raise ValueError("时段配置超出仿真时域")
 return norm
def capacity_at(segments,t):
 count=segments[0][1]
 for start,c in segments:
  if start<=t:count=c
  else:break
 return count
def schedule_variable(arrivals,services,segments,horizon):
 """按时段变窗的离散事件调度。

 停窗：容量下调时优先关闭编号最大的窗口；正在服务的窗口先办完手中样本再退出，
 期间不再领取排队样本。容量降到零时排队样本全部保留，恢复开窗后按到达顺序（FIFO）办理。
 窗口编号在退出后回收复用，保证编号不超过历史最大开窗数。
 """
 if len(arrivals)!=len(services):raise ValueError("到达与服务长度须一致")
 if any(not math.isfinite(x) or x<0 for x in arrivals) or any(not math.isfinite(x) or x<=0 for x in services):raise ValueError("到达须有限非负、服务须为有限正数")
 if any(a>b for a,b in zip(arrivals,arrivals[1:])):raise ValueError("到达时间须递增")
 segments=_normalise_segments(segments,horizon)
 footprint=max(c for _,c in segments)  # 物理窗口位上限：任何时刻编号不超过峰值开窗数
 # active: 在线窗口编号集合；free_t/free_jobs: 编号 -> 空闲时刻 / 当前在办样本（None为空闲）；closing: 办完即退出
 active=set();free_t={};free_jobs={};closing=set();reused=[];next_id=1;target_capacity=segments[0][1]
 def open_one():
  nonlocal next_id
  if reused:sid=heapq.heappop(reused)
  else:sid=next_id;next_id+=1
  active.add(sid);free_t[sid]=0.0;free_jobs[sid]=None;return sid
 for _ in range(segments[0][1]):open_one()
 queue=[];events=[];clock=0.0;ai=0;seq=0
 # 统一事件堆：类型次序 0调窗 < 1到达 < 2完成。时段按左闭右开[start,next)解释，
 # 同一时刻先应用新生效的容量，再让该时刻到达入队，最后处理完成，保证边界归属一致。
 event_heap=[]
 def push_event(t,kind,ref):
  nonlocal seq
  heapq.heappush(event_heap,(t,kind,seq,ref));seq+=1
 for k in range(1,len(segments)):push_event(segments[k][0],0,segments[k][1])
 for idx,a in enumerate(arrivals):push_event(a,1,idx)
 def dispatch():
  # 先到先服务：队首样本交给最早空闲的在线窗口（停办窗口不参与）
  while queue:
   candidates=[(free_t[s],s) for s in active if s not in closing and free_jobs[s] is None]
   if not candidates:return
   _,sid=min(candidates)
   idx=queue.pop(0);arrival=arrivals[idx];start=max(arrival,free_t[sid],clock);end=start+services[idx]
   free_t[sid]=end;free_jobs[sid]=idx
   events.append({"job":idx+1,"arrival":arrival,"service":services[idx],"start":start,"end":end,"wait":start-arrival,"server":sid})
   push_event(end,2,sid)
 def apply_change(target):
  nonlocal target_capacity
  target_capacity=target
  reconcile()
 def reconcile():
  # 目标=可接活窗口数（active中不在closing的）。缩窗：优先关编号最大的，忙则办完再退；
  # 扩窗：受物理位footprint约束，暂未腾位的窗口在closing窗口退出后再补开
  accepting={s for s in active if s not in closing}
  while len(accepting)>target_capacity:
   sid=max(accepting)
   if free_jobs[sid] is None:active.discard(sid);heapq.heappush(reused,sid)
   else:closing.add(sid)
   accepting.discard(sid)
  while len(accepting)<target_capacity and len(active)<footprint:
   sid=open_one();accepting.add(sid)
  dispatch()
 while event_heap:
  clock,kind,_,ref=heapq.heappop(event_heap)
  if kind==1:
   queue.append(ref);ai+=1;dispatch()
  elif kind==0:
   apply_change(ref)
  else:
   sid=ref;free_jobs[sid]=None
   if sid in closing:
    # 停办窗口办完退出、回收编号；若此前扩窗受物理位限制未补开，此时补齐
    active.discard(sid);closing.discard(sid);heapq.heappush(reused,sid)
   reconcile()
 if queue or len(events)!=len(arrivals) or ai!=len(arrivals):raise RuntimeError("仍有样本未被办理：末段须保持开窗以排空队列")
 events.sort(key=lambda e:e["job"])
 return events
