CREATE DATABASE IF NOT EXISTS logs;

CREATE TABLE IF NOT EXISTS logs.log_entries
(
    timestamp       DateTime64(3, 'UTC'),
    ingest_time     DateTime64(3, 'UTC') DEFAULT now64(3),
    source          LowCardinality(String) DEFAULT 'otel',
    agent_id        String DEFAULT '',
    service_name    LowCardinality(String) DEFAULT 'unknown',
    host_name       LowCardinality(String) DEFAULT 'unknown',
    level           LowCardinality(String) DEFAULT 'info',
    message         String,
    body            String DEFAULT '',
    attributes      Map(String, String) DEFAULT map(),
    trace_id        String DEFAULT '',
    span_id         String DEFAULT '',
    labels          Map(String, String) DEFAULT map(),
    timeliness      Enum8('hot'=1, 'warm'=2, 'cool'=3, 'cold'=4) DEFAULT 'hot',
    delay_seconds   UInt32 DEFAULT 0
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (service_name, host_name, level, timestamp)
TTL timestamp + INTERVAL 30 DAY DELETE
SETTINGS index_granularity = 8192;

ALTER TABLE logs.log_entries ADD INDEX IF NOT EXISTS idx_level level TYPE set(20) GRANULARITY 4;
ALTER TABLE logs.log_entries ADD INDEX IF NOT EXISTS idx_message message TYPE tokenbf_v1(30720, 2, 0) GRANULARITY 1;

-- Data completeness tracking
CREATE TABLE IF NOT EXISTS logs.data_completeness
(
    source_id       String,
    time_bucket     DateTime,
    expected_count  UInt64 DEFAULT 0,
    actual_count    UInt64 DEFAULT 0,
    first_event     Nullable(DateTime64(3, 'UTC')),
    last_event      Nullable(DateTime64(3, 'UTC')),
    gap_seconds     UInt32 DEFAULT 0,
    status          Enum8('complete'=1, 'partial'=2, 'gap_detected'=3) DEFAULT 'complete',
    updated_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree()
ORDER BY (source_id, time_bucket);
