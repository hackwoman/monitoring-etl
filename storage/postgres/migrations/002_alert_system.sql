-- ============================================================
-- 统一告警中心 — PostgreSQL 迁移
-- 告警策略 + 告警实例 + 通知渠道
-- ============================================================

-- 告警策略表
CREATE TABLE IF NOT EXISTS alert_rule (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name       VARCHAR(256) NOT NULL,
    description     TEXT,
    rule_source     VARCHAR(32) DEFAULT 'builtin',
    target_type     VARCHAR(128),
    target_filter   JSONB DEFAULT '{}',
    condition_type  VARCHAR(32) NOT NULL,
    condition_expr  JSONB NOT NULL,
    severity        VARCHAR(16) DEFAULT 'warning',
    eval_interval   INT DEFAULT 60,
    eval_window     INT DEFAULT 300,
    for_duration    INT DEFAULT 0,
    group_by        JSONB DEFAULT '["entity_guid"]',
    inhibit_rules   JSONB DEFAULT '[]',
    silence_until   TIMESTAMPTZ,
    notify_channels JSONB DEFAULT '[]',
    notify_template TEXT,
    is_enabled      BOOLEAN DEFAULT true,
    created_by      VARCHAR(128) DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alert_rule_target ON alert_rule(target_type) WHERE is_enabled = true;

-- 告警实例表
CREATE TABLE IF NOT EXISTS alert_instance (
    alert_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id         UUID NOT NULL REFERENCES alert_rule(rule_id),
    entity_guid     UUID REFERENCES entity(guid),
    entity_name     VARCHAR(512),
    entity_type     VARCHAR(128),
    status          VARCHAR(16) DEFAULT 'firing',
    starts_at       TIMESTAMPTZ DEFAULT now(),
    ends_at         TIMESTAMPTZ,
    ack_at          TIMESTAMPTZ,
    ack_by          VARCHAR(128),
    silence_at      TIMESTAMPTZ,
    silence_until   TIMESTAMPTZ,
    severity        VARCHAR(16),
    title           VARCHAR(512),
    summary         TEXT,
    fingerprint     VARCHAR(64),
    record_id       UUID,
    group_id        UUID,
    blast_radius    INT DEFAULT 0,
    affected_biz    JSONB DEFAULT '[]',
    notified_at     TIMESTAMPTZ,
    notify_count    INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alert_inst_status ON alert_instance(status) WHERE status = 'firing';
CREATE INDEX IF NOT EXISTS idx_alert_inst_entity ON alert_instance(entity_guid);
CREATE INDEX IF NOT EXISTS idx_alert_inst_rule ON alert_instance(rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_inst_severity ON alert_instance(severity);
CREATE INDEX IF NOT EXISTS idx_alert_inst_fp ON alert_instance(fingerprint);
CREATE INDEX IF NOT EXISTS idx_alert_inst_group ON alert_instance(group_id) WHERE group_id IS NOT NULL;

-- 通知渠道表
CREATE TABLE IF NOT EXISTS notification_channel (
    channel_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_name    VARCHAR(256) NOT NULL,
    channel_type    VARCHAR(32) NOT NULL,
    config          JSONB NOT NULL,
    template        TEXT,
    is_enabled      BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 预置告警规则（12 条）
-- ============================================================

INSERT INTO alert_rule (rule_name, description, rule_source, target_type, condition_type, condition_expr, severity, eval_interval, eval_window, for_duration) VALUES

-- 1. 主机 CPU 过高
('主机 CPU 过高', 'CPU 使用率超过 90% 持续 5 分钟', 'builtin', 'Host', 'threshold',
 '{"metric": "system.cpu.usage", "operator": ">", "value": 90, "unit": "percent"}',
 'critical', 60, 300, 300),

-- 2. 主机内存不足
('主机内存不足', '内存使用率超过 95% 持续 3 分钟', 'builtin', 'Host', 'threshold',
 '{"metric": "system.memory.usage", "operator": ">", "value": 95, "unit": "percent"}',
 'critical', 60, 300, 180),

-- 3. 主机磁盘将满
('主机磁盘将满', '磁盘使用率超过 90%', 'builtin', 'Host', 'threshold',
 '{"metric": "system.disk.usage", "operator": ">", "value": 90, "unit": "percent"}',
 'warning', 60, 300, 0),

-- 4. 服务 P99 延迟高
('服务 P99 延迟高', 'P99 延迟超过 2000ms 持续 3 分钟', 'builtin', 'Service', 'threshold',
 '{"metric": "http.server.request.duration.p99", "operator": ">", "value": 2000, "unit": "ms"}',
 'error', 60, 300, 180),

-- 5. 服务错误率高
('服务错误率高', '错误率超过 5% 持续 2 分钟', 'builtin', 'Service', 'threshold',
 '{"metric": "http.server.request.error_rate", "operator": ">", "value": 5, "unit": "percent"}',
 'critical', 60, 180, 120),

-- 6. MySQL 连接数高
('MySQL 连接数高', '活跃连接使用率超过 90%', 'builtin', 'MySQL', 'threshold',
 '{"metric": "mysql.connections.usage_rate", "operator": ">", "value": 90, "unit": "percent"}',
 'critical', 60, 300, 0),

-- 7. MySQL 主从延迟
('MySQL 主从延迟', '主从复制延迟超过 30 秒', 'builtin', 'MySQL', 'threshold',
 '{"metric": "mysql.replication.lag", "operator": ">", "value": 30, "unit": "seconds"}',
 'error', 60, 300, 0),

-- 8. Redis 内存高
('Redis 内存高', 'Redis 内存使用率超过 90%', 'builtin', 'Redis', 'threshold',
 '{"metric": "redis.memory.usage", "operator": ">", "value": 90, "unit": "percent"}',
 'warning', 60, 300, 0),

-- 9. 实体健康度下降
('实体健康度下降', '健康等级从 healthy 降至 warning', 'builtin', NULL, 'health_change',
 '{"from_level": "healthy", "to_level": "warning"}',
 'warning', 60, 0, 0),

-- 10. 实体健康度严重
('实体健康度严重', '健康等级从 warning 降至 critical', 'builtin', NULL, 'health_change',
 '{"from_level": "warning", "to_level": "critical"}',
 'critical', 60, 0, 0),

-- 11. 服务不可达
('服务不可达', 'QPS 为 0 持续 5 分钟', 'builtin', 'Service', 'absence',
 '{"metric": "http.server.request.qps", "absent_for": 300, "threshold": 0}',
 'critical', 60, 300, 300),

-- 12. 级联告警归并
('级联告警归并', '同一 group_id 超过 3 条告警', 'builtin', NULL, 'composite',
 '{"logic": "group_count", "group_by": "group_id", "operator": ">", "value": 3}',
 'error', 120, 300, 0)

ON CONFLICT DO NOTHING;
