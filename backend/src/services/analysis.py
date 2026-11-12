from src.services.erlang import erlang_c
from src.services.simulation import simulate
_BASE_ASSUMPTIONS=["所有率均为每分钟；μ是每个窗口的服务率。理论要求泊松到达、独立指数服务、同质窗口、无限等候空间及稳态。","观测按时段估计均值；聚合高峰与平峰不保证泊松稳态。CV偏离1提示指数假设可能不符。","仿真从空系统开始，先warmup后统计观测期到达，服务可延续到观察结束之后。warmup只能缓解初态影响，不能保证已收敛。","rho≥1没有有限稳态均值；有限期仿真仍会给出暂态等待，不能用于证明稳定。","95%区间量化固定模型下重复仿真误差，不含输入率估计误差。"]
_VARIABLE_ASSUMPTIONS=["变窗方案的窗口数随仿真钟分段变化，不存在单一稳态；分时段Erlang-C仅以该段恒定容量作参考，不构成稳态结论。","减窗不抢占在办样本：被关闭的窗口办完手中样本后退出；容量为0期间到达样本排队等待，恢复开窗后按到达顺序（FCFS）办理。","调窗时刻跨越预热与观测边界时，队列与在办样本连续延续，系统不重置；分时段忙碌比例按服务区间与观测期交集积分，容量为0的时段忙碌比例留空。","有限时域的变窗结果均为暂态数值，不能用于证明长期稳定或替代固定开窗稳态分析。"]
def analyze(profile,scenario):
 arrival=profile.arrival_rate*scenario.arrival_multiplier;service=profile.service_rate*scenario.service_multiplier
 schedule=getattr(scenario,"window_schedule",None)
 if schedule:
  simulation=simulate(arrival,service,scenario.windows,scenario.duration_minutes,scenario.warmup_minutes,scenario.replications,scenario.seed,window_schedule=schedule)
  analytic=_variable_analytic(arrival,service,simulation["window_schedule"],scenario.warmup_minutes,scenario.duration_minutes+scenario.warmup_minutes)
  comparison=[]
  assumptions=_VARIABLE_ASSUMPTIONS+_BASE_ASSUMPTIONS[:2]+_BASE_ASSUMPTIONS[4:]
 else:
  analytic=erlang_c(arrival,service,scenario.windows)
  simulation=simulate(arrival,service,scenario.windows,scenario.duration_minutes,scenario.warmup_minutes,scenario.replications,scenario.seed)
  comparison=[erlang_c(arrival,service,c) for c in sorted({2,3,4,scenario.windows})]
  assumptions=_BASE_ASSUMPTIONS
 return {"analytic":analytic,"simulation":simulation,"comparison":comparison,"profile_statistics":profile.statistics,"assumptions":assumptions}
def _variable_analytic(arrival,service,window_schedule,warmup,horizon):
 """变窗没有单一稳态：汇总口径字段供界面展示，stable 恒为 False、稳态量为 None；
 各时段的参考 Erlang-C 放在 segment_analytic，只作分时段参考。"""
 counts=[s["windows"] for s in window_schedule]
 segment_analytic=[]
 for i,seg in enumerate(window_schedule):
  end=window_schedule[i+1]["start"] if i+1<len(window_schedule) else horizon
  ref=erlang_c(arrival,service,max(1,seg["windows"]))
  segment_analytic.append({"start":seg["start"],"end":end,"windows":seg["windows"],"rho":ref["rho"],"stable":ref["stable"],"p_wait":ref["p_wait"] if seg["windows"]>0 else None,"mean_wait_minutes":ref["mean_wait_minutes"] if seg["windows"]>0 else None})
 return {"arrival_rate":arrival,"service_rate":service,"windows":max(counts),"rho":None,"stable":False,"p_wait":None,"mean_wait_minutes":None,"mean_system_minutes":None,"mean_queue_length":None,"capacity_mode":"variable","segment_analytic":segment_analytic}
