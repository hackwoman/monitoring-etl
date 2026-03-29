CREATE DATABASE IF NOT EXISTS traces;

CREATE TABLE IF NOT EXISTS traces.spans
(
    trace_id          String,
    span_id           String,
    parent_span_id    String DEFAULT '',
    span_name         String,
    
    start_time        DateTime,
    end_time          DateTime,
    duration_ms       UInt64,
    start_time_us     UInt64 DEFAULT 0,
    duration_us       UInt64 DEFAULT 0,
    
    service_name      LowCardinality(String),
    host_name         LowCardinality(String) DEFAULT '',
    endpoint          String DEFAULT '',
    peer_service      LowCardinality(String) DEFAULT '',
    span_kind         LowCardinality(String) DEFAULT 'internal',
    
    status_code       LowCardinality(String) DEFAULT 'ok',
    status_message    String DEFAULT '',
    
    http_method       LowCardinality(String) DEFAULT '',
    http_status_code  UInt16 DEFAULT 0,
    http_url          String DEFAULT '',
    
    db_system         LowCardinality(String) DEFAULT '',
    db_operation      String DEFAULT '',
    
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
