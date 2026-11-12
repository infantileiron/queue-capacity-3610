from src.services.erlang import erlang_c
from src.services.simulation import simulate
def analyze(profile,scenario):
 arrival=profile.arrival_rate*scenario.arrival_multiplier;service=profile.service_rate*scenario.service_multiplier
 schedule_cfg=getattr(scenario,"window_schedule",None)
 analytic=erlang_c(arrival,service,scenario.windows)
 simulation=simulate(arrival,service,scenario.windows,scenario.duration_minutes,scenario.warmup_minutes,scenario.replications,scenario.seed,schedule_cfg)
 variable=bool(schedule_cfg)
 if variable:
  analytic["steady_state_applicable"]=False
  analytic["capacity_mode"]="variable"
 else:
  analytic["steady_state_applicable"]=analytic["stable"]
  analytic["capacity_mode"]="fixed"
 assumptions=["所有率均为每分钟；μ是每个窗口的服务率。理论要求泊松到达、独立指数服务、同质窗口、无限等候空间及稳态。","观测按时段估计均值；聚合高峰与平峰不保证泊松稳态。CV偏离1提示指数假设可能不符。","仿真从空系统开始，先warmup后统计观测期到达，服务可延续到观察结束之后。warmup只能缓解初态影响，不能保证已收敛。","rho≥1没有有限稳态均值；有限期仿真仍会给出暂态等待，不能用于证明稳定。","95%区间量化固定模型下重复仿真误差，不含输入率估计误差。"]
 if variable:
  assumptions.append("变窗方案按时段调整开窗数：停开窗口办完手中样本后退出，容量为零期间排队样本保留，恢复开窗后按到达顺序办理；预热跨越调窗时队列与在办样本延续。容量随时间变化，整体不构成稳态，分时段与总量结果均为有限时域暂态，不能作为稳态结论。")
 return {"analytic":analytic,"simulation":simulation,"comparison":[erlang_c(arrival,service,c) for c in sorted({2,3,4,scenario.windows})],"profile_statistics":profile.statistics,"capacity_mode":"variable" if variable else "fixed","assumptions":assumptions}
