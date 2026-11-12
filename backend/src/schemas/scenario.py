from pydantic import BaseModel,Field,field_validator
class ScheduleSegment(BaseModel):
 start:int=Field(ge=0,le=2880)
 windows:int=Field(ge=0,le=12)
class ScenarioInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 profile_id:str
 windows:int=Field(default=1,ge=1,le=12)
 window_schedule:list[ScheduleSegment]|None=Field(default=None)
 arrival_multiplier:float=Field(default=1,ge=.2,le=3,allow_inf_nan=False)
 service_multiplier:float=Field(default=1,ge=.2,le=3,allow_inf_nan=False)
 duration_minutes:int=Field(default=480,ge=60,le=1440)
 warmup_minutes:int=Field(default=120,ge=0,le=1440)
 replications:int=Field(default=30,ge=5,le=100)
 seed:int=Field(default=2206,ge=0,le=2147483647)
 @field_validator("window_schedule")
 @classmethod
 def _check_schedule(cls,v,info):
  if v is None:return v
  starts=[s.start for s in v]
  if starts[0]!=0:raise ValueError("首个时段须从仿真开始（起点0）配置开窗数")
  if any(a>=b for a,b in zip(starts,starts[1:])):raise ValueError("时段起点须严格递增且不重复")
  if v[-1].windows<1:raise ValueError("末段至少保留1个窗口，以便停窗排队样本恢复后办结")
  return v
 @property
 def variable(self):return self.window_schedule is not None
