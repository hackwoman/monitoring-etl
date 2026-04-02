-- ============================================================
-- 统一记录表 — ClickHouse
-- 所有可追溯数据的统一索引层（不替代 log_entries / spans）
-- ============================================================

CREATE TABLE IF NOT EXISTS records (
    record_id       UUID DEFAULT generateUUIDv4(),
    record_type     LowCardinality(String) CODEC(ZSTD(1)),   -- 'trace_span' | 'log_entry' | 'event' | 'snapshot' | 'alert'
    source          LowCardinality(String) CODEC(ZSTD(1)),    -- 'vector' | 'health-engine' | 'alert-engine' | 'external' | 'manual'
    timestamp       DateTime64(3, 'Asia/Shanghai'),
    entity_guid     UUID CODEC(LZ4),
    entity_name     String CODEC(ZSTD(1)),
    entity_type     LowCardinality(String) CODEC(ZSTD(1)),
    severity        LowCardinality(String) CODEC(ZSTD(1)),    -- 'info' | 'warning' | 'error' | 'critical'
    title           String CODEC(ZSTD(3)),
    content         String CODEC(ZSTD(3)),
    tags            Map(String, String) CODEC(ZSTD(1)),
    fingerprint     String CODEC(ZSTD(1)),
    group_id        UUID CODEC(LZ4),

    -- 告警相关字段
    alert_status    LowCardinality(String) DEFAULT 'none' CODEC(ZSTD(1)),
    alert_rule_id   UUID CODEC(LZ4),
    alert_starts_at DateTime64(3, 'Asia/Shanghai'),
    alert_ends_at   DateTime64(3, 'Asia/Shanghai'),

    INDEX idx_entity entity_guid TYPE bloom_filter GRANULARITY 3,
    INDEX idx_fingerprint fingerprint TYPE bloom_filter GRANULARITY 3,
    INDEX idx_severity severity TYPE set(4) GRANULARITY 3
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (record_type, entity_guid, timestamp)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192, min_bytes_for_wide_part = 10485760;

-- 活跃告警物化视图（小表，毫秒级查询）
CREATE TABLE IF NOT EXISTS alerts_firing (
    record_id       UUID,
    fingerprint     String,
    entity_guid     UUID,
    entity_name     String,
    entity_type     LowCardinality(String),
    severity        LowCardinality(String),
    title           String,
    alert_rule_id   UUID,
    alert_starts_at DateTime64(3, 'Asia/Shanghai'),
    timestamp       DateTime64(3, 'Asia/Shanghai')
) ENGINE = ReplacingMergeTree(timestamp)
ORDER BY (fingerprint, entity_guid)
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS alerts_firing_mv TO alerts_firing AS
SELECT
    record_id, fingerprint, entity_guid, entity_name,
    entity_type, severity, title, alert_rule_id,
    alert_starts_at, timestamp
FROM records
WHERE alert_status = 'firing';
