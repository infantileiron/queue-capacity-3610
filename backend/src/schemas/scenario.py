from pydantic import BaseModel,Field,model_validator
class WindowSegment(BaseModel):
 start_minute:int=Field(ge=0)
 windows:int=Field(ge=0,le=12)
class ScenarioInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 profile_id:str
 windows:int=Field(ge=1,le=12)
 arrival_multiplier:float=Field(default=1,ge=.2,le=3,allow_inf_nan=False)
 service_multiplier:float=Field(default=1,ge=.2,le=3,allow_inf_nan=False)
 duration_minutes:int=Field(default=480,ge=60,le=1440)
 warmup_minutes:int=Field(default=120,ge=0,le=1440)
 replications:int=Field(default=30,ge=5,le=100)
 seed:int=Field(default=2206,ge=0,le=2147483647)
 window_schedule:list[WindowSegment]|None=Field(default=None)
 @model_validator(mode="after")
 def _check_schedule(self):
  if self.window_schedule:
   starts=[seg.start_minute for seg in self.window_schedule]
   if starts[0]!=0:raise ValueError("首个时段须从第0分钟开始（时间轴包含预热）")
   if any(a>=b for a,b in zip(starts,starts[1:])):raise ValueError("时段起点须严格递增")
   if len(self.window_schedule)>24:raise ValueError("变窗时段最多24段")
   if not any(seg.windows>0 for seg in self.window_schedule):raise ValueError("至少需要一个开窗数大于0的时段")
   if self.window_schedule[-1].windows<=0:raise ValueError("末段开窗数须大于0：停窗后须恢复开窗，排队样本才能全部办理")
   horizon=self.warmup_minutes+self.duration_minutes
   if starts[-1]>=horizon:raise ValueError("时段配置超出预热与观测的总时域")
  return self
