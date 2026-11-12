-- 变窗容量：capacity_scenarios 增加分时段开窗配置（JSON，NULL 表示固定开窗，沿用原仿真路径）。
-- 新库由 SQLAlchemy metadata 在建表时直接包含该列；既有库执行本 ALTER 后即可使用。
-- 固定开窗方案 window_schedule 为 NULL，结果与升级前完全一致，可复现原结果。
ALTER TABLE capacity_scenarios
  ADD COLUMN window_schedule JSON NULL;
