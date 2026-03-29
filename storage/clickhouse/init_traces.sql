CREATE DATABASE IF NOT EXISTS traces;

CREATE TABLE IF NOT EXISTS traces.spans
(
    trace_id          String,
    span_id           String,
    parent_span_id    String DEFAULT '',
    span_name         String,
    
    -- 时间 (直接用 DateTime, factory 里转换)
    start_time        DateTime64(3),
    end_time          DateTime64(3),
    duration_ms       UInt64,
    
    -- 原始微秒（保留，供排序用）
    start_time_us     UInt64 DEFAULT 0,
    duration_us       UInt64 DEFAULT 0,
    
    -- 来源
    service_name      LowCardinality(String),
    host_name         LowCardinality(String) DEFAULT '',
    endpoint          String DEFAULT '',
    
    -- 调用关系
    peer_service      LowCardinality(String) DEFAULT '',
    span_kind         LowCardinality(String) DEFAULT 'internal',
    
    -- 状态
    status_code       LowCardinality(String) DEFAULT 'ok',
    status_message    String DEFAULT '',
    
    -- HTTP
    http_method       LowCardinality(String) DEFAULT '',
    http_status_code  UInt16 DEFAULT 0,
    http_url          String DEFAULT '',
    
    -- 数据库
    db_system         LowCardinality(String) DEFAULT '',
    db_operation      String DEFAULT '',
    
    -- 额外属性
    attributes        Map(String, String) DEFAULT map(),
    labels            Map(String, String) DEFAULT map(),
    
    ingest_time       DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(start_time)
ORDER BY (trace_id, start_time)
TTL start_time + INTERVAL 7 DAY DELETE
SETTINGS index_granularity = 8192;

ALTER TABLE traces.spans ADD INDEX IF NOT EXISTS idx_trace trace_id TYPE bloom_filter(0.01) GRANULARITY 1;
ALTER TABLE traces.spans ADD INDEX IF NOT EXISTS idx_service service_name TYPE set(50) GRANULARITY 1;
