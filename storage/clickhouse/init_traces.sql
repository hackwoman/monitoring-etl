CREATE DATABASE IF NOT EXISTS traces;

-- 端到端调用链 Span 表
CREATE TABLE IF NOT EXISTS traces.spans
(
    -- 标识
    trace_id          String,
    span_id           String,
    parent_span_id    String DEFAULT '',
    span_name         String,
    
    -- 时间 (微秒)
    start_time_us     UInt64,
    end_time_us       UInt64,
    duration_us       UInt64,
    
    -- 来源
    service_name      LowCardinality(String),
    host_name         LowCardinality(String) DEFAULT '',
    endpoint          String DEFAULT '',
    
    -- 调用关系
    peer_service      LowCardinality(String) DEFAULT '',
    span_kind         Enum8('internal'=0, 'server'=1, 'client'=2, 'producer'=3, 'consumer'=4) DEFAULT 'internal',
    
    -- 状态
    status_code       Enum8('unset'=0, 'ok'=1, 'error'=2) DEFAULT 'unset',
    status_message    String DEFAULT '',
    
    -- HTTP
    http_method       LowCardinality(String) DEFAULT '',
    http_status_code  UInt16 DEFAULT 0,
    http_url          String DEFAULT '',
    
    -- 数据库
    db_system         LowCardinality(String) DEFAULT '',
    db_statement      String DEFAULT '',
    db_operation      String DEFAULT '',
    
    -- 额外属性
    attributes        Map(String, String) DEFAULT map(),
    labels            Map(String, String) DEFAULT map(),
    
    -- 入库时间
    ingest_time       DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(fromUnixTimestamp64Micro(start_time_us))
ORDER BY (trace_id, start_time_us)
TTL fromUnixTimestamp64Micro(start_time_us) + INTERVAL 7 DAY DELETE
SETTINGS index_granularity = 8192;

-- 按 trace_id 查询的索引
ALTER TABLE traces.spans ADD INDEX IF NOT EXISTS idx_trace trace_id TYPE bloom_filter(0.01) GRANULARITY 1;
ALTER TABLE traces.spans ADD INDEX IF NOT EXISTS idx_service service_name TYPE set(50) GRANULARITY 1;
ALTER TABLE traces.spans ADD INDEX IF NOT EXISTS idx_status status_code TYPE set(5) GRANULARITY 1;
