-- 002 变窗方案：capacity_scenarios 增加分时段开窗配置列。
-- 初次部署由 SQLAlchemy metadata 直接建表（含新列）；既有 MySQL 部署执行本文件即可幂等升级。
-- 固定开窗方案 window_schedule 为 NULL，行为与升级前完全一致。
SET @col_exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'capacity_scenarios' AND COLUMN_NAME = 'window_schedule');
SET @ddl := IF(@col_exists = 0,
 'ALTER TABLE capacity_scenarios ADD COLUMN window_schedule JSON NULL AFTER windows',
 'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
