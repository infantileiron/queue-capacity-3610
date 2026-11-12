import heapq,math
from collections import deque
def schedule(arrivals,services,windows):
 if len(arrivals)!=len(services) or windows<1: raise ValueError("到达与服务长度须一致，窗口数须为正")
 if any(not math.isfinite(x) or x<0 for x in arrivals) or any(not math.isfinite(x) or x<=0 for x in services): raise ValueError("到达须有限非负、服务须有限正数")
 if any(a>b for a,b in zip(arrivals,arrivals[1:])): raise ValueError("到达时间须递增")
 servers=[(0.0,i+1) for i in range(windows)];heapq.heapify(servers);events=[]
 for i,(arrival,service) in enumerate(zip(arrivals,services)):
  free,server=heapq.heappop(servers);start=max(arrival,free);end=start+service
  events.append({"job":i+1,"arrival":arrival,"service":service,"start":start,"end":end,"wait":start-arrival,"server":server})
  heapq.heappush(servers,(end,server))
 return events

def normalize_schedule(raw,horizon,max_windows=12):
 """把时段开窗配置规整为覆盖 [0,horizon] 的分段常量容量表。
 输入：[{"start":分钟,"windows":n}, ...]，时间为仿真钟（0=仿真开始，含预热）。
 输出：[{"start":s,"end":e,"windows":n}, ...]，按起点递增、相邻同容量合并。"""
 if not isinstance(raw,list) or not raw: raise ValueError("变窗方案须提供至少一个时段配置")
 seg=[]
 for item in raw:
  if not isinstance(item,dict) or "start" not in item or "windows" not in item: raise ValueError("时段配置须包含 start 与 windows")
  try: start=int(item["start"]);windows=int(item["windows"])
  except (TypeError,ValueError): raise ValueError("时段起点与开窗数须为整数")
  if start<0: raise ValueError("时段起点不能为负")
  if windows<0 or windows>max_windows: raise ValueError(f"开窗数须在 0—{max_windows} 之间")
  seg.append((start,windows))
 seg.sort(key=lambda x:x[0])
 if seg[0][0]!=0: raise ValueError("首个时段须从仿真开始（起点0）配置开窗数")
 if any(a[0]==b[0] for a,b in zip(seg,seg[1:])): raise ValueError("时段起点不能重复")
 if seg[-1][0]>=horizon: raise ValueError("最后一个时段起点须早于仿真结束时间")
 if seg[-1][1]<1: raise ValueError("末段至少保留1个窗口，以便停窗期间排队样本在恢复后办结")
 merged=[]
 for start,windows in seg:
  if merged and merged[-1]["windows"]==windows: continue
  if merged: merged[-1]["end"]=start
  merged.append({"start":start,"end":None,"windows":windows})
 for s,e in zip(merged,merged[1:]):
  if s["end"]!=e["start"]: raise ValueError("时段配置必须连续覆盖整个仿真时域")
 merged[-1]["end"]=horizon
 if any(s["end"]-s["start"]<=0 for s in merged): raise ValueError("每段时长须为正")
 return merged

def _capacity_at(schedule,t):
 current=schedule[0]["windows"]
 for seg in schedule:
  if seg["start"]<=t<seg["end"]: return seg["windows"]
 return schedule[-1]["windows"]

def schedule_variable(arrivals,services,schedule):
 """按时段开窗数量调度。
 规则：
 - 减窗时优先让空闲窗口立即退出，忙碌窗口办完手中样本后退出（不抢占、不中断）；
 - 容量降到0期间新到达样本进入队列等待，不分配窗口；恢复开窗后按到达顺序（FCFS）办理；
 - 增窗时补充新窗口承接队列；预热期间的调窗延续队列与在办样本，不重置系统。
 事件结构与固定 schedule() 完全一致，同一时间点按“调窗→完成→到达→派发”顺序处理。"""
 if len(arrivals)!=len(services): raise ValueError("到达与服务长度须一致")
 if any(not math.isfinite(x) or x<0 for x in arrivals) or any(not math.isfinite(x) or x<=0 for x in services): raise ValueError("到达须有限非负、服务须有限正数")
 if any(a>b for a,b in zip(arrivals,arrivals[1:])): raise ValueError("到达时间须递增")
 horizon=schedule[-1]["end"]
 # free：可承接新样本的空闲窗口堆 (可用时刻, 编号)；closing：已通知退出、办完即走的忙碌窗口集合
 free=[(0.0,i+1) for i in range(schedule[0]["windows"])];heapq.heapify(free)
 closing=set();next_id=schedule[0]["windows"]+1
 # completion_heap：(完成时刻, 窗口编号, 样本序号)
 completion_heap=[];queue=deque();events=[];ai=0;change_idx=0
 change_times=[seg["start"] for seg in schedule if seg["start"]>0]
 def reconcile(target):
  nonlocal next_id
  # 窗口三态：free 空闲可派工；completion_heap 中忙碌，其中 closing 子集办完即退、不回池。
  # 调窗后最终保留的窗口 = 空闲 + 忙碌但未被通知退出（closing 的窗口办完会消失）。
  retained=len(free)+len(completion_heap)-len(closing)
  while retained>target:
   if free:
    heapq.heappop(free)
   else:
    # 全部在忙：选最早办完且尚未通知退出的窗口，办完手中样本后退出
    end,server,idx=min((e for e in completion_heap if e[1] not in closing),key=lambda e:(e[0],e[1]))
    closing.add(server)
   retained-=1
  while retained<target:
   heapq.heappush(free,(0.0,next_id));next_id+=1;retained+=1
 def dispatch(now):
  while queue and free:
   idx=queue.popleft()
   avail,server=heapq.heappop(free)
   start=max(now,avail);end=start+services[idx]
   events.append({"job":idx+1,"arrival":arrivals[idx],"service":services[idx],"start":start,"end":end,"wait":start-arrivals[idx],"server":server})
   heapq.heappush(completion_heap,(end,server,idx))
 while ai<len(arrivals) or completion_heap or queue:
  next_complete=completion_heap[0][0] if completion_heap else math.inf
  next_arrival=arrivals[ai] if ai<len(arrivals) else math.inf
  next_change=change_times[change_idx] if change_idx<len(change_times) else math.inf
  now=min(next_complete,next_arrival,next_change)
  if not math.isfinite(now): break
  if now==next_change:
   reconcile(_capacity_at(schedule,now));change_idx+=1
  # 同一时刻先处理完成，释放窗口（closing 中的窗口办完即退出，不再回池）
  while completion_heap and completion_heap[0][0]<=now+1e-12:
   end,server,idx=heapq.heappop(completion_heap)
   if server in closing: closing.discard(server)
   else: heapq.heappush(free,(end,server))
  # 再处理该时刻到达，入队（容量为0时无窗口可派，样本留在队列等待恢复）
  while ai<len(arrivals) and arrivals[ai]<=now+1e-12:
   queue.append(ai);ai+=1
  dispatch(now)
 events.sort(key=lambda e:e["job"])
 return events
