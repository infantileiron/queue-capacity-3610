"""变窗容量调度与仿真验证脚本（项目源码外的独立验证，不随服务部署）。
运行：PYTHONPATH=backend python -I verify/test_variable_capacity.py
"""
import sys,os,random,statistics
sys.path.insert(0,os.path.join(os.path.dirname(__file__),"..","backend"))
from src.services.scheduler import schedule,schedule_variable,normalize_schedule
from src.services.simulation import simulate
from src.services.erlang import erlang_c

def approx(a,b,tol=1e-9):return abs(a-b)<=tol

def test_fixed_equivalence():
 """常量容量的变窗路径与原固定路径逐事件一致，固定结果可复现。"""
 rng=random.Random(7);arrivals=[];t=0
 for _ in range(300):
  t+=rng.expovariate(0.8);arrivals.append(t)
 services=[rng.expovariate(0.2) for _ in arrivals]
 fixed=schedule(arrivals,services,3)
 seg=normalize_schedule([{"start":0,"windows":3}],600)
 var=schedule_variable(arrivals,services,seg)
 assert len(fixed)==len(var)
 for a,b in zip(fixed,var):
  assert a==b,(a,b)
 # 完整 simulate 固定路径两次调用结果一致（复现）
 r1=simulate(0.8,0.2,3,480,120,12,2206)
 r2=simulate(0.8,0.2,3,480,120,12,2206)
 assert r1==r2
 assert r1["capacity_mode"]=="fixed"
 print("ok 固定开窗路径与原实现逐事件一致且可复现")

def test_close_after_current_job():
 """减窗：空闲窗口立即退，忙碌窗口办完手中样本再退出，不抢占。"""
 # 1个窗口在 t=0 开始服务长样本；t=10 要求容量降到0，该窗口须办完才退出
 arrivals=[0.0,12.0];services=[20.0,5.0]
 seg=normalize_schedule([{"start":0,"windows":1},{"start":10,"windows":0},{"start":30,"windows":1}],100)
 ev=schedule_variable(arrivals,services,seg)
 j1,j2=ev
 assert approx(j1["start"],0.0) and approx(j1["end"],20.0),j1  # 未被抢占
 # t=12 到达时容量为0，排队；t=30 恢复后由新窗口按FCFS办理（旧窗口已退出，编号递增）
 assert approx(j2["start"],30.0),j2
 assert approx(j2["wait"],18.0),j2
 assert j2["server"]==2,j2
 print("ok 停窗窗口办完手中样本再退出；零容量期间样本排队，恢复后FCFS办理")

def test_idle_closes_immediately_busy_waits():
 """2窗：1忙1闲时减到1窗，空闲窗立即退出；再减到0，忙碌窗办完才退。"""
 arrivals=[0.0,5.0,40.0];services=[30.0,8.0,4.0]
 seg=normalize_schedule([{"start":0,"windows":2},{"start":10,"windows":1},{"start":20,"windows":0},{"start":50,"windows":1}],100)
 ev=schedule_variable(arrivals,services,seg)
 # t=5 的样本由2号窗服务，t=10减窗时2号窗忙→办完(13)退出；1号窗忙→办完(30)退出
 j2=ev[1]
 assert approx(j2["end"],13.0),j2
 # t=40 容量0，样本排队到 t=50
 j3=ev[2]
 assert approx(j3["start"],50.0) and approx(j3["wait"],10.0),j3
 print("ok 空闲窗立即退出、忙碌窗办完再退，零容量后恢复开窗承接队列")

def test_increase_takes_queue_fcfs():
 """容量为0积压多个样本，恢复+增窗后按到达顺序分配。"""
 arrivals=[10.0,11.0,12.0,13.0];services=[5.0,5.0,5.0,5.0]
 seg=normalize_schedule([{"start":0,"windows":0},{"start":20,"windows":2}],100)
 ev=schedule_variable(arrivals,services,seg)
 # t=20 两个新窗口开始，按到达顺序取前两个；完成后再取后两个
 starts=[(e["job"],e["start"]) for e in ev]
 assert approx(starts[0][1],20.0) and approx(starts[1][1],20.0),starts
 assert approx(starts[2][1],25.0) and approx(starts[3][1],25.0),starts
 waits=[e["wait"] for e in ev]
 assert waits==[10,9,13,12],waits
 print("ok 恢复开窗后排队样本严格按到达顺序办理，等待=开始-到达")

def test_warmup_carries_state():
 """调窗跨越预热：预热内减窗产生的在办/排队状态延续到观测期，不重置。"""
 # 预热20，观测期60；t=10（预热内）3→1窗并出现排队，观测期开始时队列仍在
 rng=random.Random(11);arrivals=[];t=0
 while True:
  t+=rng.expovariate(1.5)
  if t>=80:break
  arrivals.append(t)
 services=[rng.expovariate(0.25) for _ in arrivals]
 seg=normalize_schedule([{"start":0,"windows":3},{"start":10,"windows":1}],80)
 ev=schedule_variable(arrivals,services,seg)
 assert all(e["end"]>=e["start"]>=e["arrival"]-1e-12 for e in ev)
 # 观测期（t>=20）到达的样本，其等待可能因预热遗留队列而显著大于0
 obs_wait=max(e["wait"] for e in ev if e["arrival"]>=20)
 assert obs_wait>0
 print("ok 预热内调窗的队列与在办样本连续延续到观测期")

def test_segment_stats():
 sim=simulate(0.8,0.2,3,480,120,12,2206,window_schedule=[
  {"start":0,"windows":4},{"start":100,"windows":3},
  {"start":300,"windows":0},{"start":480,"windows":4}])
 assert sim["capacity_mode"]=="variable"
 summ=sim["segment_summary"]
 assert [s["windows"] for s in summ]==[4,3,0,4]
 # 分时段到达量之和≈总观测到达量（按到达所属时段归属）
 total=sum(s["arrivals"] for s in summ)
 rep_total=statistics.mean(r["arrivals"] for r in sim["replications"])
 assert approx(total,rep_total,1e-9),(total,rep_total)
 # 零容量时段：无样本可以在该时段开始服务，忙碌比例留空
 zero=[s for s in summ if s["windows"]==0][0]
 assert zero["busy_fraction"] is None
 assert zero["arrivals"]>0  # 午间仍有到达，只是排队
 # 每个重复都带分时段统计
 assert all(len(r["segments"])==4 for r in sim["replications"])
 print("ok 分时段给出到达量/等待/忙碌比例，零容量时段忙碌比例留空且到达仍计入")

def test_variable_not_steady_state():
 from src.services.analysis import _variable_analytic
 analytic=_variable_analytic(0.8,0.2,[{"start":0,"windows":4},{"start":100,"windows":3},{"start":300,"windows":0},{"start":480,"windows":4}],120,600)
 assert analytic["stable"] is False and analytic["rho"] is None
 assert analytic["mean_wait_minutes"] is None
 assert len(analytic["segment_analytic"])==4
 zero_seg=analytic["segment_analytic"][2]
 assert zero_seg["windows"]==0 and zero_seg["mean_wait_minutes"] is None
 print("ok 变窗结果标记为非稳态，稳态量留空，分时段Erlang-C仅作参考")

def test_schedule_validation():
 """时段配置校验：起点、连续性、末段窗口、取值范围。"""
 fails=[
  [{"start":5,"windows":2}],                       # 未从0开始
  [{"start":0,"windows":2},{"start":0,"windows":3}],# 起点重复
  [{"start":0,"windows":0}],                        # 末段为0窗口
  [{"start":0,"windows":2},{"start":100,"windows":3}],# 末段起点不早于结束
  [{"start":0,"windows":13}],                       # 超上限
  [{"start":0,"windows":-1}],                       # 负值
 ]
 for bad in fails:
  try:
   normalize_schedule(bad,100);raise AssertionError(f"应拒绝 {bad}")
  except ValueError:pass
 # 相邻同容量合并
 merged=normalize_schedule([{"start":0,"windows":2},{"start":30,"windows":2},{"start":60,"windows":3}],100)
 assert [(s["start"],s["windows"]) for s in merged]==[(0,2),(60,3)],merged
 ok=normalize_schedule([{"start":0,"windows":4},{"start":100,"windows":0},{"start":300,"windows":4}],600)
 assert ok[-1]["end"]==600 and ok[1]["windows"]==0
 print("ok 时段配置校验完整，同容量相邻段自动合并")
def test_consecutive_capacity_changes():
 """连续调窗（无完成事件介入）时容量计数必须正确，closing 窗口不重复计数。"""
 # 4窗全部忙碌，连续 4→2→0，不应多退窗口也不应报错
 arrivals=[0.0,0.5,1.0,1.5,60.0];services=[30.0,30.0,30.0,30.0,5.0]
 seg=normalize_schedule([{"start":0,"windows":4},{"start":10,"windows":2},{"start":15,"windows":0},{"start":80,"windows":2}],120)
 ev=schedule_variable(arrivals,services,seg)
 assert len(ev)==5
 # 前4个样本在 t≈0 由4个窗口开始，服务到 ~30.5；调窗后都办完退出
 first4=ev[:4]
 assert all(0<=e["start"]<=1.6 for e in first4)
 # t=60 到达时容量为0，排队到 t=80 恢复，2个新窗口之一承接
 j5=ev[4]
 assert approx(j5["start"],80.0),j5
 assert approx(j5["wait"],20.0),j5
 # 恢复后新窗口编号在旧4窗之后
 assert j5["server"]>=5
 print("ok 连续减窗（4→2→0）计数正确，恢复增窗正常承接")

def test_down_then_up_with_completion():
 """减窗后窗口完成退出，再增窗：只补差额，不重复建窗、编号不重用。"""
 arrivals=[0.0,1.0,2.0,40.0,61.0,62.0];services=[10.0,10.0,10.0,4.0,4.0,4.0]
 seg=normalize_schedule([{"start":0,"windows":3},{"start":20,"windows":1},{"start":60,"windows":2}],120)
 ev=schedule_variable(arrivals,services,seg)
 # t≈0三个窗口各接一个样本，12前全部完成回池；t=20减到1时均空闲→退2留1（堆中最晚空闲者3号窗）
 # t=40由保留的3号窗服务；t=60增到2只补1个新窗口（编号4），61/62两个样本由3、4号窗并行办理
 servers_used=sorted({e["server"] for e in ev})
 assert servers_used==[1,2,3,4],servers_used
 assert max(servers_used)==4  # 仅新增一个窗口，无重复编号
 j4=ev[3];assert approx(j4["start"],40.0) and j4["server"]==3,j4
 j5,j6=ev[4],ev[5]
 # 61到达即由新增4号窗开工；62到达时3号窗已空闲，立即开工（等待均为0）
 assert approx(j5["start"],61.0) and j5["server"]==4,(j5,j6)
 assert approx(j6["start"],62.0) and j6["server"]==3 and approx(j6["wait"],0.0),(j5,j6)
 print("ok 减窗后增窗只补差额窗口，编号不重用，新窗并行承接到达")

def test_initial_zero_capacity():
 """首段允许0窗：仿真开始即停窗，所有早期到达排队，首次开窗后按序办理。"""
 arrivals=[1.0,2.0,3.0];services=[5.0,5.0,5.0]
 seg=normalize_schedule([{"start":0,"windows":0},{"start":20,"windows":1}],100)
 ev=schedule_variable(arrivals,services,seg)
 assert approx(ev[0]["start"],20.0) and approx(ev[1]["start"],25.0) and approx(ev[2]["start"],30.0)
 assert [e["wait"] for e in ev]==[19,23,27]
 print("ok 初始0窗时全部到达排队，首次开窗后FCFS顺序办理")

def test_csv_export_shape():
 """变窗运行的CSV在固定列后追加分时段表，固定运行保持原口径（复刻 reports.export 拼装逻辑）。"""
 import io,csv
 base_cols=["replication","arrivals","mean_wait_minutes","p_wait","max_wait_minutes","busy_fraction"]
 sim={"capacity_mode":"variable","replications":[{"replication":1,"arrivals":10,"mean_wait_minutes":2.0,"p_wait":.5,"max_wait_minutes":9,"busy_fraction":.8}],
      "segment_summary":[{"start":0,"end":100,"windows":0,"observed":False,"arrivals":0,"mean_wait_minutes":None,"p_wait":None,"busy_minutes":0,"busy_fraction":None}]}
 buf=io.StringIO();w=csv.DictWriter(buf,base_cols);w.writeheader();w.writerows(sim["replications"])
 if sim.get("capacity_mode")=="variable":
  buf.write("\n分时段统计（仿真钟分钟，0=仿真开始含预热；容量0时段忙碌比例留空）\n")
  sw=csv.DictWriter(buf,["start","end","windows","observed","arrivals","mean_wait_minutes","p_wait","busy_fraction"],extrasaction="ignore")
  sw.writeheader();sw.writerows(sim["segment_summary"])
 text=buf.getvalue()
 assert text.splitlines()[0]=="replication,arrivals,mean_wait_minutes,p_wait,max_wait_minutes,busy_fraction"
 assert "分时段统计" in text
 last=text.rstrip().splitlines()[-1].split(",")
 assert last[:5]==["0","100","0","False","0"] and last[5:]==["","",""]  # 空等待/概率/忙碌比例
 print("ok 变窗CSV追加时段表，固定列口径不变，零容量留空")

if __name__=="__main__":
 for fn in (test_fixed_equivalence,test_close_after_current_job,test_idle_closes_immediately_busy_waits,
            test_increase_takes_queue_fcfs,test_warmup_carries_state,test_segment_stats,
            test_variable_not_steady_state,test_schedule_validation,
            test_consecutive_capacity_changes,test_down_then_up_with_completion,
            test_initial_zero_capacity,test_csv_export_shape):
  fn()
 print("\n全部验证通过")
