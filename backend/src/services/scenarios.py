import uuid
from sqlalchemy import select
from fastapi import HTTPException
from src.models import CapacityScenario,ServiceProfile
from src.services.scheduler import normalize_schedule
from src.utils.time import now
from src.utils.serialization import serialize
def create(db,payload):
 profile=db.get(ServiceProfile,payload.profile_id)
 if not profile:raise HTTPException(404,"服务剖面不存在")
 horizon=payload.duration_minutes+payload.warmup_minutes
 data=payload.model_dump()
 if payload.window_schedule:
  schedule=normalize_schedule(data["window_schedule"],horizon)
  data["window_schedule"]=[{"start":s["start"],"windows":s["windows"]} for s in schedule]
  data["windows"]=max(s["windows"] for s in schedule)
  # 校验末段起点须早于仿真结束（normalize 已保证），并检查跨时域覆盖
  if schedule[-1]["start"]>=horizon:raise HTTPException(422,"最后一个时段起点须早于仿真结束时间")
 if profile.arrival_rate*payload.arrival_multiplier*horizon>20000:raise HTTPException(422,"仿真事件预算过大，请缩短时域")
 if db.scalar(select(CapacityScenario).where(CapacityScenario.name==payload.name)):raise HTTPException(409,"方案名称已存在")
 item=CapacityScenario(id=str(uuid.uuid4()),created_at=now(),**data);db.add(item);db.commit();return serialize(item)
