#!/usr/bin/env python3
"""Database initialization script for PostgreSQL CMDB - Phase 2 认知层。"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    "dbname": "postgres",
}

CMDB_DB = os.getenv("CMDB_DATABASE", "cmdb")

INIT_SQL = """
-- ============================================================
-- CMDB Core Schema - Phase 2 认知层
-- ============================================================

-- 实体类型定义（收敛属性/指标/关系/健康规则）
CREATE TABLE IF NOT EXISTS entity_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    display_name    VARCHAR(256),
    category        VARCHAR(64) DEFAULT 'custom',
    icon            VARCHAR(128),
    super_type      VARCHAR(128),
    super_types     JSONB DEFAULT '[]',
    attribute_defs  JSONB DEFAULT '{}',
    definition      JSONB DEFAULT '{}',
    description     TEXT,
    is_custom       BOOLEAN DEFAULT false,
    version         INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Seed default entity types (Phase 2 增强版)
INSERT INTO entity_type_def (type_name, display_name, category, icon, description, definition) VALUES
    ('Business',    '业务服务', 'business',        'business', '业务层实体', '{"attributes":[],"templates":[],"metrics":[{"name":"business.success_rate","display":"业务成功率","type":"gauge","unit":"percent","thresholds":{"warn":99,"crit":95}},{"name":"business.response_time","display":"业务响应时间","type":"gauge","unit":"ms","thresholds":{"warn":500,"crit":2000}}],"relations":[{"type":"includes","direction":"out","target":"Service"}],"health":{"method":"children_avg"}}'),
    ('Service',     '微服务',   'application',     'service',  '微服务实例', '{"attributes":[{"key":"language","name":"编程语言","type":"string"},{"key":"port","name":"服务端口","type":"int"}],"templates":["base_software"],"metrics":[{"name":"http.server.request.duration","display":"HTTP请求延迟","type":"histogram","unit":"ms","thresholds":{"p99_warn":500,"p99_crit":2000}},{"name":"http.server.request.error_rate","display":"错误率","type":"gauge","unit":"percent","thresholds":{"warn":1,"crit":5}},{"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","thresholds":{"warn":70,"crit":90}}],"relations":[{"type":"calls","direction":"out","target":"Service"},{"type":"depends_on","direction":"out","target":"Database"},{"type":"runs_on","direction":"out","target":"Host"}],"health":{"method":"weighted_avg","dimensions":[{"name":"latency","metric":"http.server.request.duration.p99","weight":0.4},{"name":"error_rate","metric":"http.server.request.error_rate","weight":0.3},{"name":"saturation","metric":"system.cpu.usage","weight":0.3}]},"discovery":{"auto_match":["service.name"],"reconcile_priority":["qualified_name","name"]}}'),
    ('Host',        '主机',     'infrastructure',  'host',     '物理机/虚拟机', '{"attributes":[],"templates":["base_hardware","base_cloud"],"metrics":[{"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","thresholds":{"warn":70,"crit":90}},{"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","thresholds":{"warn":80,"crit":95}},{"name":"system.disk.usage","display":"磁盘使用率","type":"gauge","unit":"percent","thresholds":{"warn":80,"crit":90}},{"name":"system.disk.io.util","display":"磁盘IO利用率","type":"gauge","unit":"percent","thresholds":{"warn":70,"crit":90}}],"relations":[{"type":"hosts","direction":"out","target":"Service"},{"type":"connected_to","direction":"out","target":"NetworkDevice"}],"health":{"method":"weighted_avg","dimensions":[{"name":"cpu","metric":"system.cpu.usage","weight":0.3},{"name":"memory","metric":"system.memory.usage","weight":0.3},{"name":"disk","metric":"system.disk.usage","weight":0.2},{"name":"io","metric":"system.disk.io.util","weight":0.2}]},"discovery":{"auto_match":["host.name","host.ip"],"reconcile_priority":["qualified_name","attributes.sn","attributes.ip","name"]}}'),
    ('Database',    '数据库',   'middleware',      'database', '数据库实例', '{"attributes":[{"key":"db_type","name":"数据库类型","type":"string"},{"key":"port","name":"端口","type":"int"}],"templates":["base_database"],"metrics":[{"name":"db.connections.active","display":"活跃连接数","type":"gauge","unit":"count","thresholds":{"warn":80,"crit":95}},{"name":"db.queries.slow","display":"慢查询数","type":"counter","unit":"count/min","thresholds":{"rate_warn":10,"rate_crit":50}}],"relations":[{"type":"runs_on","direction":"out","target":"Host"}],"health":{"method":"weighted_avg","dimensions":[{"name":"connections","metric":"db.connections.active","weight":0.3},{"name":"slow_queries","metric":"db.queries.slow","weight":0.3},{"name":"query_latency","metric":"db.query.duration.p99","weight":0.4}]}}'),
    ('MySQL',       'MySQL',    'middleware',      'mysql',    'MySQL数据库', '{"super_type":"Database","templates":["base_database"],"metrics":[{"name":"mysql.connections.active","display":"活跃连接数","type":"gauge","unit":"count","thresholds":{"warn":80,"crit":95}},{"name":"mysql.queries.slow","display":"慢查询数","type":"counter","unit":"count/min","thresholds":{"rate_warn":10,"rate_crit":50}},{"name":"mysql.buffer_pool.hit_rate","display":"Buffer Pool命中率","type":"gauge","unit":"percent","thresholds":{"warn":95,"crit":90}}],"relations":[{"type":"runs_on","direction":"out","target":"Host"}],"health":{"method":"weighted_avg","dimensions":[{"name":"connections","weight":0.25},{"name":"slow_queries","weight":0.25},{"name":"replication","weight":0.25},{"name":"buffer_pool","weight":0.25}]}}'),
    ('Redis',       'Redis',    'middleware',      'redis',    'Redis缓存', '{"templates":[],"metrics":[{"name":"redis.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","thresholds":{"warn":80,"crit":95}},{"name":"redis.commands.hit_rate","display":"命令命中率","type":"gauge","unit":"percent","thresholds":{"warn":95,"crit":90}},{"name":"redis.clients.connected","display":"连接客户端数","type":"gauge","unit":"count","thresholds":{"warn":500,"crit":1000}}],"relations":[{"type":"runs_on","direction":"out","target":"Host"}],"health":{"method":"weighted_avg","dimensions":[{"name":"memory","weight":0.3},{"name":"hit_rate","weight":0.4},{"name":"connections","weight":0.3}]}}'),
    ('Middleware',  '中间件',   'middleware',      'middleware','中间件实例', '{}'),
    ('NetworkDevice','网络设备', 'infrastructure',  'network',  '网络设备', '{"templates":["base_network"],"metrics":[{"name":"network.packet.loss","display":"丢包率","type":"gauge","unit":"percent","thresholds":{"warn":0.1,"crit":1.0}},{"name":"network.latency","display":"网络延迟","type":"gauge","unit":"ms","thresholds":{"warn":10,"crit":50}}],"relations":[{"type":"connected_to","direction":"out","target":"Host"},{"type":"connected_to","direction":"out","target":"NetworkDevice"}],"health":{"method":"weighted_avg","dimensions":[{"name":"packet_loss","weight":0.5},{"name":"latency","weight":0.3},{"name":"utilization","weight":0.2}]}}'),
    ('K8sCluster',  'K8s集群',  'runtime',         'k8s',      'Kubernetes集群', '{"templates":["base_container"],"metrics":[{"name":"k8s.cpu.utilization","display":"CPU利用率","type":"gauge","unit":"percent","thresholds":{"warn":70,"crit":90}},{"name":"k8s.memory.utilization","display":"内存利用率","type":"gauge","unit":"percent","thresholds":{"warn":80,"crit":95}}],"relations":[{"type":"contains","direction":"out","target":"K8sPod"}],"health":{"method":"weighted_avg","dimensions":[{"name":"cpu","weight":0.4},{"name":"memory","weight":0.4},{"name":"nodes","weight":0.2}]}}'),
    ('K8sPod',      'K8s Pod',  'runtime',         'pod',      'Kubernetes Pod', '{"attributes":[{"key":"namespace","name":"命名空间","type":"string"}],"templates":[],"metrics":[{"name":"k8s.pod.cpu.usage","display":"CPU使用","type":"gauge","unit":"millicores"},{"name":"k8s.pod.restarts","display":"重启次数","type":"counter","unit":"count","thresholds":{"rate_warn":3,"rate_crit":10}}],"relations":[{"type":"runs","direction":"out","target":"Service"},{"type":"scheduled_on","direction":"out","target":"Host"}],"health":{"method":"weighted_avg","dimensions":[{"name":"cpu","weight":0.3},{"name":"memory","weight":0.3},{"name":"restarts","weight":0.4}]}}'),
    ('IP',          'IP地址',   'infrastructure',  'ip',       'IP地址', '{}'),
    ('Endpoint',    'API端点',  'application',     'endpoint', 'API端点', '{}')
ON CONFLICT (type_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    category = EXCLUDED.category,
    icon = EXCLUDED.icon,
    definition = EXCLUDED.definition,
    description = EXCLUDED.description;

-- 实体实例（四维度：身份/期望/观测/影响）
CREATE TABLE IF NOT EXISTS entity (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL REFERENCES entity_type_def(type_name),
    name            VARCHAR(512) NOT NULL,
    qualified_name  VARCHAR(1024) UNIQUE NOT NULL,
    attributes      JSONB DEFAULT '{}',
    labels          JSONB DEFAULT '{}',
    status          VARCHAR(32) DEFAULT 'active',
    source          VARCHAR(64) DEFAULT 'manual',

    -- 期望
    expected_metrics    JSONB DEFAULT '[]',
    expected_relations  JSONB DEFAULT '[]',

    -- 观测
    health_score    INT,
    health_level    VARCHAR(16),
    health_detail   JSONB,
    last_observed   TIMESTAMPTZ,

    -- 影响
    biz_service     VARCHAR(256),
    risk_score      INT,
    propagation_hops INT,
    blast_radius    INT,

    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entity_type ON entity(type_name);
CREATE INDEX IF NOT EXISTS idx_entity_name ON entity(name);
CREATE INDEX IF NOT EXISTS idx_entity_labels ON entity USING GIN(labels);
CREATE INDEX IF NOT EXISTS idx_entity_health ON entity(health_level) WHERE health_level IN ('warning', 'critical', 'down');
CREATE INDEX IF NOT EXISTS idx_entity_risk ON entity(risk_score DESC) WHERE risk_score > 50;
CREATE INDEX IF NOT EXISTS idx_entity_biz ON entity(biz_service) WHERE biz_service IS NOT NULL;

-- 关系类型定义
CREATE TABLE IF NOT EXISTS relationship_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    end1_type       VARCHAR(128),
    end1_name       VARCHAR(128),
    end2_type       VARCHAR(128),
    end2_name       VARCHAR(128),
    description     TEXT
);

INSERT INTO relationship_type_def VALUES
    ('runs_on',      'Application','app',  'Host',       'host',  '应用运行在主机上'),
    ('Host_runs',    'Host',       'host', 'Application','app',   '主机运行应用'),
    ('depends_on',   'Service',    'service','Database',  'db',    '服务依赖数据库'),
    ('calls',        'Service',    'caller','Service',    'callee','服务调用服务'),
    ('includes',     'Business',   'biz',  'Service',    'service','业务包含服务'),
    ('hosts',        'Host',       'host', 'Service',    'service','主机承载服务'),
    ('connected_to', 'Host',       'host', 'NetworkDevice','device','主机连接网络设备'),
    ('contains',     'K8sCluster', 'cluster','K8sPod',    'pod',   '集群包含Pod'),
    ('scheduled_on', 'K8sPod',     'pod',  'Host',       'node',  'Pod调度到节点'),
    ('runs',         'K8sPod',     'pod',  'Service',    'service','Pod运行服务')
ON CONFLICT (type_name) DO NOTHING;

-- 关系实例
CREATE TABLE IF NOT EXISTS relationship (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL,
    end1_guid       UUID NOT NULL REFERENCES entity(guid),
    end2_guid       UUID NOT NULL REFERENCES entity(guid),
    from_guid       UUID REFERENCES entity(guid),
    to_guid         UUID REFERENCES entity(guid),
    attributes      JSONB DEFAULT '{}',
    source          VARCHAR(64) DEFAULT 'manual',
    confidence      FLOAT DEFAULT 1.0,
    is_active       BOOLEAN DEFAULT true,
    first_seen      TIMESTAMPTZ DEFAULT now(),
    last_seen       TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rel_type ON relationship(type_name);
CREATE INDEX IF NOT EXISTS idx_rel_end1 ON relationship(end1_guid);
CREATE INDEX IF NOT EXISTS idx_rel_end2 ON relationship(end2_guid);
CREATE INDEX IF NOT EXISTS idx_rel_from ON relationship(from_guid) WHERE from_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rel_to ON relationship(to_guid) WHERE to_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rel_active ON relationship(is_active) WHERE is_active = true;

-- 标签定义
CREATE TABLE IF NOT EXISTS label_definition (
    label_key       VARCHAR(128) PRIMARY KEY,
    label_name      VARCHAR(256),
    value_type      VARCHAR(32) DEFAULT 'string',
    enum_values     JSONB,
    description     TEXT,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ DEFAULT now()
);

INSERT INTO label_definition (label_key, label_name, value_type, enum_values, description) VALUES
    ('env',          '环境',     'enum',   '["prod","staging","dev","test"]', '部署环境'),
    ('team',         '团队',     'string', NULL, '负责团队'),
    ('business_line','业务线',   'string', NULL, '业务归属'),
    ('region',       '地域',     'string', NULL, '部署地域'),
    ('tenant',       '租户',     'string', NULL, '多租户隔离标识'),
    ('project',      '项目',     'string', NULL, '项目归属'),
    ('app_version',  '应用版本', 'string', NULL, '应用发布版本')
ON CONFLICT (label_key) DO NOTHING;

-- 属性组合模板
CREATE TABLE IF NOT EXISTS attribute_template (
    template_name   VARCHAR(128) PRIMARY KEY,
    category        VARCHAR(64),
    attributes      JSONB NOT NULL DEFAULT '[]',
    description     TEXT,
    is_builtin      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

INSERT INTO attribute_template (template_name, category, attributes, description, is_builtin) VALUES
    ('base_hardware', 'infrastructure', '[{"key":"cpu_cores","name":"CPU核数","type":"int"},{"key":"memory_gb","name":"内存(GB)","type":"int"},{"key":"disk_gb","name":"磁盘(GB)","type":"int"},{"key":"os","name":"操作系统","type":"string"},{"key":"ip","name":"IP地址","type":"string"},{"key":"sn","name":"序列号","type":"string"}]', '基础硬件属性', true),
    ('base_network',  'infrastructure', '[{"key":"vendor","name":"厂商","type":"string"},{"key":"model","name":"型号","type":"string"},{"key":"mgmt_ip","name":"管理IP","type":"string"},{"key":"port_count","name":"端口数","type":"int"},{"key":"firmware_version","name":"固件版本","type":"string"}]', '网络设备属性', true),
    ('base_database', 'middleware',     '[{"key":"db_type","name":"数据库类型","type":"string"},{"key":"db_version","name":"版本","type":"string"},{"key":"port","name":"端口","type":"int"},{"key":"max_connections","name":"最大连接数","type":"int"},{"key":"replication_mode","name":"复制模式","type":"string"}]', '数据库属性', true),
    ('base_container','runtime',        '[{"key":"cluster_name","name":"集群名","type":"string"},{"key":"namespace","name":"命名空间","type":"string"},{"key":"node_count","name":"节点数","type":"int"},{"key":"k8s_version","name":"K8s版本","type":"string"}]', '容器/K8s属性', true),
    ('base_cloud',    'infrastructure', '[{"key":"cloud_provider","name":"云厂商","type":"string"},{"key":"region","name":"地域","type":"string"},{"key":"az","name":"可用区","type":"string"},{"key":"instance_type","name":"实例规格","type":"string"},{"key":"vpc_id","name":"VPC ID","type":"string"}]', '云资源属性', true),
    ('base_software', 'application',    '[{"key":"language","name":"编程语言","type":"string"},{"key":"framework","name":"框架","type":"string"},{"key":"version","name":"版本","type":"string"},{"key":"port","name":"服务端口","type":"int"},{"key":"team","name":"负责团队","type":"string"}]', '软件/应用属性', true)
ON CONFLICT (template_name) DO NOTHING;

-- CMDB 事件订阅
CREATE TABLE IF NOT EXISTS cmdb_event_subscription (
    subscription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber      VARCHAR(256) NOT NULL,
    event_types     VARCHAR(64)[] NOT NULL,
    filter          JSONB DEFAULT '{}',
    callback_url    VARCHAR(512),
    callback_mode   VARCHAR(16) DEFAULT 'webhook',
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cmdb_event_log (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      VARCHAR(64) NOT NULL,
    entity_guid     UUID,
    payload         JSONB,
    published_at    TIMESTAMPTZ DEFAULT now(),
    status          VARCHAR(16) DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_event_log_status ON cmdb_event_log(status) WHERE status = 'pending';

-- 数据质量检查
CREATE TABLE IF NOT EXISTS data_check_rule (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name       VARCHAR(256) NOT NULL,
    rule_type       VARCHAR(32) NOT NULL,
    target_type     VARCHAR(128),
    check_sql       TEXT NOT NULL,
    expected_result VARCHAR(32) DEFAULT 'empty',
    severity        VARCHAR(16) DEFAULT 'warning',
    check_schedule  VARCHAR(64) DEFAULT '0 2 * * *',
    is_builtin      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_quality_snapshot (
    snapshot_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_time   TIMESTAMPTZ DEFAULT now(),
    overall_score   INT,
    total_entities  INT,
    total_rules     INT,
    passed_rules    INT,
    failed_rules    INT,
    type_scores     JSONB DEFAULT '{}',
    issues          JSONB DEFAULT '[]'
);

-- 预置数据检查规则
INSERT INTO data_check_rule (rule_name, rule_type, target_type, check_sql, severity, is_builtin) VALUES
    ('主机必须有业务归属', 'completeness', 'Host', 'SELECT guid FROM entity WHERE type_name = ''Host'' AND status = ''active'' AND (biz_service IS NULL OR biz_service = '''')', 'warning', true),
    ('数据库必须有负责人', 'completeness', 'Database', 'SELECT guid FROM entity WHERE type_name IN (''Database'',''MySQL'',''Redis'') AND status = ''active'' AND (labels->>''team'' IS NULL OR labels->>''team'' = '''')', 'warning', true),
    ('服务必须有环境标签', 'completeness', 'Service', 'SELECT guid FROM entity WHERE type_name = ''Service'' AND status = ''active'' AND (labels->>''env'' IS NULL OR labels->>''env'' = '''')', 'warning', true),
    ('IP地址不能重复', 'uniqueness', 'Host', 'SELECT attributes->>''ip'' FROM entity WHERE type_name = ''Host'' AND status = ''active'' AND attributes->>''ip'' IS NOT NULL GROUP BY attributes->>''ip'' HAVING COUNT(*) > 1', 'error', true),
    ('实体名不能重复(同类型)', 'uniqueness', NULL, 'SELECT type_name, name FROM entity WHERE status = ''active'' GROUP BY type_name, name HAVING COUNT(*) > 1', 'error', true),
    ('实体超过30天未更新', 'freshness', NULL, 'SELECT guid FROM entity WHERE status = ''active'' AND updated_at < now() - INTERVAL ''30 days''', 'warning', true),
    ('关系两端实体必须存在', 'consistency', NULL, 'SELECT r.guid FROM relationship r LEFT JOIN entity e1 ON r.end1_guid = e1.guid LEFT JOIN entity e2 ON r.end2_guid = e2.guid WHERE r.is_active = true AND (e1.guid IS NULL OR e2.guid IS NULL)', 'error', true),
    ('孤立实体(无任何关系)', 'completeness', NULL, 'SELECT e.guid FROM entity e LEFT JOIN relationship r1 ON e.guid = r1.end1_guid AND r1.is_active = true LEFT JOIN relationship r2 ON e.guid = r2.end2_guid AND r2.is_active = true WHERE e.status = ''active'' AND e.type_name != ''Business'' AND r1.guid IS NULL AND r2.guid IS NULL', 'warning', true)
ON CONFLICT DO NOTHING;
"""


def init_database():
    """Create CMDB database and initialize schema."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Check if database exists
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (CMDB_DB,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE {CMDB_DB}')
        print(f"✅ Database '{CMDB_DB}' created")
    else:
        print(f"ℹ️  Database '{CMDB_DB}' already exists")

    cur.close()
    conn.close()

    # Connect to CMDB database and run init SQL
    cmdb_config = {**DB_CONFIG, "dbname": CMDB_DB}
    conn = psycopg2.connect(**cmdb_config)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(INIT_SQL)
    cur.close()
    conn.close()
    print("✅ CMDB schema initialized (Phase 2 认知层)")


if __name__ == "__main__":
    print("Initializing CMDB database...")
    init_database()
    print("Done!")
