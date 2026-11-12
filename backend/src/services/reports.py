import uuid,csv,io
from sqlalchemy import select
from fastapi import HTTPException
from src.models import Report,CapacityReview
from src.services.runs import require_completed
from src.utils.time import now
from src.utils.serialization import serialize
def create(db,payload,user):
 require_completed(db,payload.run_id)
 review=db.scalar(select(CapacityReview).where(CapacityReview.run_id==payload.run_id).order_by(CapacityReview.created_at.desc()))
 if not review or review.decision!="accepted":raise HTTPException(409,"最新复核须为接受后才能归档")
 if db.scalar(select(Report).where(Report.run_id==payload.run_id)):raise HTTPException(409,"本次运行已归档")
 item=Report(id=str(uuid.uuid4()),published_by=user["email"],created_at=now(),**payload.model_dump());db.add(item);db.commit();return serialize(item)
def export(db,id):
 report=db.get(Report,id)
 if not report:raise HTTPException(404,"报告不存在")
 result=require_completed(db,report.run_id).result
 columns=["replication","arrivals","mean_wait_minutes","p_wait","max_wait_minutes","busy_fraction"]
 buf=io.StringIO();writer=csv.DictWriter(buf,columns);writer.writeheader();writer.writerows(result["simulation"]["replications"])
 if result["simulation"].get("capacity_mode")=="variable":
  buf.write("\n分时段统计（仿真钟分钟，0=仿真开始含预热；容量0时段忙碌比例留空）\n")
  seg_columns=["start","end","windows","observed","arrivals","mean_wait_minutes","p_wait","busy_fraction"]
  seg_writer=csv.DictWriter(buf,seg_columns,extrasaction="ignore")
  seg_writer.writeheader();seg_writer.writerows(result["simulation"]["segment_summary"])
 return "﻿"+buf.getvalue()
