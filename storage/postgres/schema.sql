-- ============================================================
-- CMDB Core Schema - Phase 2 认知层
-- ============================================================

-- 实体类型定义
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

-- Seed builtin types
INSERT INTO entity_type_def (type_name, display_name, category, icon, description, definition) VALUES
    ('Business','业务服务','business','business','业务层实体','{"attributes":[{"key":"business_domain","name":"业务域","type":"string","required":false},{"key":"business_owner","name":"业务负责人","type":"string","required":false},{"key":"tech_owner","name":"技术负责人","type":"string","required":false},{"key":"slo_availability","name":"SLO可用性","type":"float","required":false,"default":99.9},{"key":"business_weight","name":"业务权重","type":"float","required":true,"default":1.0,"min":0,"max":3.0}],"metrics":[{"name":"business.success_rate","display":"业务成功率","type":"gauge","unit":"percent","category":"business","thresholds":{"warn":99.5,"crit":99.0}},{"name":"business.throughput","display":"业务吞吐量","type":"gauge","unit":"count/min","category":"business"},{"name":"business.user_count","display":"在线用户数","type":"gauge","unit":"count","category":"business"}],"relations":[{"type":"includes","direction":"out","target":"Service","dimension":"vertical"}],"health":{"method":"children_avg"}}'),
    ('Service','微服务','application','service','微服务实例','{"attributes":[{"key":"language","name":"编程语言","type":"string","required":false},{"key":"framework","name":"框架","type":"string","required":false},{"key":"port","name":"服务端口","type":"int","required":true,"default":8080,"min":1,"max":65535},{"key":"team","name":"负责团队","type":"string","required":false},{"key":"version","name":"版本号","type":"string","required":false}],"templates":["base_software"],"metrics":[{"name":"http.server.request.duration.p99","display":"P99延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":500,"crit":2000}},{"name":"http.server.request.duration.p50","display":"P50延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":200,"crit":800}},{"name":"http.server.request.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance"},{"name":"http.server.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}},{"name":"http.server.request.5xx_count","display":"5xx错误数","type":"counter","unit":"count/min","category":"error","thresholds":{"rate_warn":10,"rate_crit":50}},{"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":70,"crit":90}},{"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":95}},{"name":"system.disk.usage","display":"磁盘使用率","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":80,"crit":90}},{"name":"jvm.heap.usage","display":"JVM堆内存","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":75,"crit":90}},{"name":"business.order.success_rate","display":"业务成功率","type":"gauge","unit":"percent","category":"business","thresholds":{"warn":99,"crit":95}}],"relations":[{"type":"calls","direction":"out","target":"Service","dimension":"horizontal"},{"type":"depends_on","direction":"out","target":"Database","dimension":"horizontal"},{"type":"depends_on","direction":"out","target":"Redis","dimension":"horizontal"},{"type":"runs_on","direction":"out","target":"Host","dimension":"vertical"},{"type":"has_endpoint","direction":"out","target":"Endpoint","dimension":"vertical"}],"health":{"method":"weighted_avg","dimensions":[{"name":"performance","metric":"http.server.request.duration.p99","weight":0.30,"category":"performance"},{"name":"error","metric":"http.server.request.error_rate","weight":0.25,"category":"error"},{"name":"resource","metric":"system.cpu.usage","weight":0.20,"category":"resource"},{"name":"business","metric":"business.order.success_rate","weight":0.25,"category":"business"}]}}'),
    ('Host','主机','infrastructure','host','物理机/虚拟机','{"attributes":[{"key":"ip","name":"IP地址","type":"string","required":true},{"key":"cpu_cores","name":"CPU核数","type":"int","required":true,"min":1,"max":256},{"key":"memory_gb","name":"内存(GB)","type":"int","required":true,"min":1,"max":4096},{"key":"disk_gb","name":"磁盘(GB)","type":"int","required":false},{"key":"os","name":"操作系统","type":"string","required":false},{"key":"sn","name":"序列号","type":"string","required":false},{"key":"vendor","name":"厂商","type":"string","required":false},{"key":"cloud_provider","name":"云厂商","type":"string","required":false},{"key":"instance_type","name":"实例规格","type":"string","required":false}],"templates":["base_hardware","base_cloud"],"metrics":[{"name":"system.cpu.usage","display":"CPU使用率","type":"gauge","unit":"percent","category":"compute","thresholds":{"warn":70,"crit":90}},{"name":"system.cpu.load.1m","display":"1分钟负载","type":"gauge","unit":"count","category":"compute"},{"name":"system.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"memory","thresholds":{"warn":80,"crit":95}},{"name":"system.disk.usage","display":"磁盘使用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":80,"crit":90}},{"name":"system.disk.io.util","display":"磁盘IO利用率","type":"gauge","unit":"percent","category":"disk","thresholds":{"warn":70,"crit":90}},{"name":"system.network.bytes_recv","display":"网络入流量","type":"gauge","unit":"MB/s","category":"network"},{"name":"system.network.bytes_sent","display":"网络出流量","type":"gauge","unit":"MB/s","category":"network"},{"name":"system.network.packet.loss","display":"网络丢包率","type":"gauge","unit":"percent","category":"network","thresholds":{"warn":0.1,"crit":1.0}}],"relations":[{"type":"hosts","direction":"out","target":"Service","dimension":"vertical"},{"type":"hosts","direction":"out","target":"Database","dimension":"vertical"},{"type":"hosts","direction":"out","target":"Redis","dimension":"vertical"},{"type":"connected_to","direction":"out","target":"NetworkDevice","dimension":"vertical"}],"health":{"method":"weighted_avg","dimensions":[{"name":"cpu","display":"CPU","metric":"system.cpu.usage","weight":0.30,"category":"compute"},{"name":"memory","display":"内存","metric":"system.memory.usage","weight":0.25,"category":"memory"},{"name":"disk","display":"磁盘","metric":"system.disk.usage","weight":0.25,"category":"disk"},{"name":"disk_io","display":"磁盘IO","metric":"system.disk.io.util","weight":0.20,"category":"disk"}]},"discovery":{"auto_match":["host.name","host.ip"],"reconcile_priority":["qualified_name","attributes.sn","attributes.ip","name"]}}'),
    ('Database','数据库','middleware','database','数据库实例','{"attributes":[{"key":"db_type","name":"数据库类型","type":"string"},{"key":"port","name":"端口","type":"int"}],"templates":["base_database"],"metrics":[{"name":"db.connections.active","display":"活跃连接数","type":"gauge","unit":"count","thresholds":{"warn":80,"crit":95}},{"name":"db.queries.slow","display":"慢查询数","type":"counter","unit":"count/min","thresholds":{"rate_warn":10,"rate_crit":50}}],"relations":[{"type":"runs_on","direction":"out","target":"Host"}],"health":{"method":"weighted_avg","dimensions":[{"name":"connections","weight":0.3},{"name":"slow_queries","weight":0.3},{"name":"query_latency","weight":0.4}]}}'),
    ('MySQL','MySQL','middleware','mysql','MySQL数据库','{"super_type":"Database","templates":["base_database"],"attributes":[{"key":"db_version","name":"数据库版本","type":"string","required":false},{"key":"port","name":"端口","type":"int","required":true,"default":3306},{"key":"max_connections","name":"最大连接数","type":"int","required":false,"default":500},{"key":"replication_mode","name":"复制模式","type":"string","required":false}],"metrics":[{"name":"mysql.connections.active","display":"活跃连接数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":400,"crit":480}},{"name":"mysql.connections.usage_rate","display":"连接使用率","type":"gauge","unit":"percent","category":"connections","thresholds":{"warn":80,"crit":95}},{"name":"mysql.queries.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance"},{"name":"mysql.queries.slow","display":"慢查询数","type":"counter","unit":"count/min","category":"performance","thresholds":{"rate_warn":5,"rate_crit":20}},{"name":"mysql.queries.avg_latency","display":"平均查询延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":100,"crit":500}},{"name":"mysql.buffer_pool.hit_rate","display":"Buffer Pool命中率","type":"gauge","unit":"percent","category":"performance","thresholds":{"warn":95,"crit":90}},{"name":"mysql.replication.lag","display":"主从延迟","type":"gauge","unit":"seconds","category":"replication","thresholds":{"warn":5,"crit":30}},{"name":"mysql.replication.io_running","display":"IO线程状态","type":"gauge","unit":"bool","category":"replication"},{"name":"mysql.innodb.row_lock.waited","display":"行锁等待","type":"counter","unit":"count/min","category":"locks","thresholds":{"rate_warn":10,"rate_crit":50}}],"relations":[{"type":"runs_on","direction":"out","target":"Host","dimension":"vertical"}],"health":{"method":"weighted_avg","dimensions":[{"name":"connections","display":"连接","metric":"mysql.connections.usage_rate","weight":0.20,"category":"connections"},{"name":"performance","display":"性能","metric":"mysql.queries.avg_latency","weight":0.25,"category":"performance"},{"name":"slow_queries","display":"慢查询","metric":"mysql.queries.slow","weight":0.20,"category":"performance"},{"name":"replication","display":"复制","metric":"mysql.replication.lag","weight":0.15,"category":"replication"},{"name":"buffer_pool","display":"缓存","metric":"mysql.buffer_pool.hit_rate","weight":0.20,"category":"performance"}]}}'),
    ('Redis','Redis','middleware','redis','Redis缓存','{"attributes":[{"key":"redis_version","name":"Redis版本","type":"string","required":false},{"key":"port","name":"端口","type":"int","required":true,"default":6379},{"key":"max_memory","name":"最大内存","type":"string","required":false},{"key":"cluster_mode","name":"集群模式","type":"string","required":false}],"metrics":[{"name":"redis.memory.usage","display":"内存使用率","type":"gauge","unit":"percent","category":"memory","thresholds":{"warn":75,"crit":90}},{"name":"redis.memory.fragmentation_ratio","display":"内存碎片率","type":"gauge","unit":"ratio","category":"memory","thresholds":{"warn":1.5,"crit":3.0}},{"name":"redis.commands.qps","display":"命令QPS","type":"gauge","unit":"count/s","category":"performance"},{"name":"redis.commands.avg_latency","display":"平均延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":5,"crit":20}},{"name":"redis.commands.hit_rate","display":"命中率","type":"gauge","unit":"percent","category":"performance","thresholds":{"warn":90,"crit":80}},{"name":"redis.clients.connected","display":"连接客户端数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":500,"crit":1000}},{"name":"redis.clients.blocked","display":"阻塞客户端数","type":"gauge","unit":"count","category":"connections","thresholds":{"warn":10,"crit":50}},{"name":"redis.keyspace.keys","display":"键总数","type":"gauge","unit":"count","category":"data"},{"name":"redis.replication.lag","display":"主从延迟","type":"gauge","unit":"seconds","category":"replication","thresholds":{"warn":5,"crit":30}}],"relations":[{"type":"runs_on","direction":"out","target":"Host","dimension":"vertical"}],"health":{"method":"weighted_avg","dimensions":[{"name":"memory","display":"内存","metric":"redis.memory.usage","weight":0.25,"category":"memory"},{"name":"hit_rate","display":"命中率","metric":"redis.commands.hit_rate","weight":0.30,"category":"performance"},{"name":"latency","display":"延迟","metric":"redis.commands.avg_latency","weight":0.25,"category":"performance"},{"name":"connections","display":"连接","metric":"redis.clients.connected","weight":0.20,"category":"connections"}]}}'),
    ('Middleware','中间件','middleware','middleware','中间件实例','{}'),
    ('NetworkDevice','网络设备','infrastructure','network','网络设备','{"templates":["base_network"],"metrics":[{"name":"network.packet.loss","display":"丢包率","type":"gauge","unit":"percent","category":"reliability","thresholds":{"warn":0.1,"crit":1.0}},{"name":"network.latency","display":"网络延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":10,"crit":50}},{"name":"network.bandwidth.utilization","display":"带宽利用率","type":"gauge","unit":"percent","category":"capacity","thresholds":{"warn":70,"crit":90}},{"name":"network.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"reliability","thresholds":{"warn":0.01,"crit":0.1}},{"name":"network.device.cpu","display":"设备CPU","type":"gauge","unit":"percent","category":"resource","thresholds":{"warn":70,"crit":90}}],"relations":[{"type":"connected_to","direction":"out","target":"Host","dimension":"vertical"},{"type":"connected_to","direction":"out","target":"NetworkDevice","dimension":"vertical"}],"health":{"method":"weighted_avg","dimensions":[{"name":"packet_loss","weight":0.35},{"name":"latency","weight":0.25},{"name":"utilization","weight":0.20},{"name":"error_rate","weight":0.20}]}}'),
    ('K8sCluster','K8s集群','runtime','k8s','Kubernetes集群','{"templates":["base_container"],"metrics":[{"name":"k8s.cpu.utilization","display":"CPU利用率","type":"gauge","unit":"percent","thresholds":{"warn":70,"crit":90}},{"name":"k8s.memory.utilization","display":"内存利用率","type":"gauge","unit":"percent","thresholds":{"warn":80,"crit":95}}],"relations":[{"type":"contains","direction":"out","target":"K8sPod"}],"health":{"method":"weighted_avg","dimensions":[{"name":"cpu","weight":0.4},{"name":"memory","weight":0.4},{"name":"nodes","weight":0.2}]}}'),
    ('K8sPod','K8s Pod','runtime','pod','Kubernetes Pod','{"attributes":[{"key":"namespace","name":"命名空间","type":"string"}],"metrics":[{"name":"k8s.pod.cpu.usage","display":"CPU使用","type":"gauge","unit":"millicores"},{"name":"k8s.pod.restarts","display":"重启次数","type":"counter","unit":"count","thresholds":{"rate_warn":3,"rate_crit":10}}],"relations":[{"type":"runs","direction":"out","target":"Service"},{"type":"scheduled_on","direction":"out","target":"Host"}],"health":{"method":"weighted_avg","dimensions":[{"name":"cpu","weight":0.3},{"name":"memory","weight":0.3},{"name":"restarts","weight":0.4}]}}'),
    ('IP','IP地址','infrastructure','ip','IP地址','{}'),
    ('Endpoint','API端点','application','endpoint','API端点','{"attributes":[{"key":"method","name":"HTTP方法","type":"string","required":true},{"key":"path","name":"URL路径","type":"string","required":true},{"key":"service","name":"所属服务","type":"string","required":true}],"metrics":[{"name":"endpoint.request.duration.p99","display":"P99延迟","type":"gauge","unit":"ms","category":"performance","thresholds":{"warn":500,"crit":2000}},{"name":"endpoint.request.qps","display":"QPS","type":"gauge","unit":"count/s","category":"performance"},{"name":"endpoint.request.error_rate","display":"错误率","type":"gauge","unit":"percent","category":"error","thresholds":{"warn":1,"crit":5}}],"relations":[{"type":"belongs_to","direction":"in","target":"Service","dimension":"vertical"},{"type":"calls","direction":"out","target":"Endpoint","dimension":"horizontal"}],"health":{"method":"weighted_avg","dimensions":[{"name":"latency","weight":0.40},{"name":"error_rate","weight":0.35},{"name":"qps","weight":0.25}]}}')
ON CONFLICT (type_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    category = EXCLUDED.category,
    icon = EXCLUDED.icon,
    definition = EXCLUDED.definition,
    description = EXCLUDED.description;

-- 实体实例
CREATE TABLE IF NOT EXISTS entity (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL REFERENCES entity_type_def(type_name),
    name            VARCHAR(512) NOT NULL,
    qualified_name  VARCHAR(1024) UNIQUE NOT NULL,
    attributes      JSONB DEFAULT '{}',
    labels          JSONB DEFAULT '{}',
    status          VARCHAR(32) DEFAULT 'active',
    source          VARCHAR(64) DEFAULT 'manual',
    expected_metrics    JSONB DEFAULT '[]',
    expected_relations  JSONB DEFAULT '[]',
    health_score    INT,
    health_level    VARCHAR(16),
    health_detail   JSONB,
    last_observed   TIMESTAMPTZ,
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
    ('runs_on','Application','app','Host','host','应用运行在主机上'),
    ('Host_runs','Host','host','Application','app','主机运行应用'),
    ('depends_on','Service','service','Database','db','服务依赖数据库'),
    ('calls','Service','caller','Service','callee','服务调用服务'),
    ('includes','Business','biz','Service','service','业务包含服务'),
    ('hosts','Host','host','Service','service','主机承载服务'),
    ('connected_to','Host','host','NetworkDevice','device','主机连接网络设备'),
    ('contains','K8sCluster','cluster','K8sPod','pod','集群包含Pod'),
    ('scheduled_on','K8sPod','pod','Host','node','Pod调度到节点'),
    ('runs','K8sPod','pod','Service','service','Pod运行服务')
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
    dimension       VARCHAR(16) DEFAULT 'vertical',  -- 'horizontal' 调用链 / 'vertical' 归属树
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
    ('env','环境','enum','["prod","staging","dev","test"]','部署环境'),
    ('team','团队','string',NULL,'负责团队'),
    ('business_line','业务线','string',NULL,'业务归属'),
    ('region','地域','string',NULL,'部署地域'),
    ('tenant','租户','string',NULL,'多租户隔离标识'),
    ('project','项目','string',NULL,'项目归属'),
    ('app_version','应用版本','string',NULL,'应用发布版本')
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
    ('base_hardware','infrastructure','[{"key":"cpu_cores","name":"CPU核数","type":"int"},{"key":"memory_gb","name":"内存(GB)","type":"int"},{"key":"disk_gb","name":"磁盘(GB)","type":"int"},{"key":"os","name":"操作系统","type":"string"},{"key":"ip","name":"IP地址","type":"string"},{"key":"sn","name":"序列号","type":"string"}]','基础硬件属性',true),
    ('base_network','infrastructure','[{"key":"vendor","name":"厂商","type":"string"},{"key":"model","name":"型号","type":"string"},{"key":"mgmt_ip","name":"管理IP","type":"string"},{"key":"port_count","name":"端口数","type":"int"},{"key":"firmware_version","name":"固件版本","type":"string"}]','网络设备属性',true),
    ('base_database','middleware','[{"key":"db_type","name":"数据库类型","type":"string"},{"key":"db_version","name":"版本","type":"string"},{"key":"port","name":"端口","type":"int"},{"key":"max_connections","name":"最大连接数","type":"int"},{"key":"replication_mode","name":"复制模式","type":"string"}]','数据库属性',true),
    ('base_container','runtime','[{"key":"cluster_name","name":"集群名","type":"string"},{"key":"namespace","name":"命名空间","type":"string"},{"key":"node_count","name":"节点数","type":"int"},{"key":"k8s_version","name":"K8s版本","type":"string"}]','容器/K8s属性',true),
    ('base_cloud','infrastructure','[{"key":"cloud_provider","name":"云厂商","type":"string"},{"key":"region","name":"地域","type":"string"},{"key":"az","name":"可用区","type":"string"},{"key":"instance_type","name":"实例规格","type":"string"},{"key":"vpc_id","name":"VPC ID","type":"string"}]','云资源属性',true),
    ('base_software','application','[{"key":"language","name":"编程语言","type":"string"},{"key":"framework","name":"框架","type":"string"},{"key":"version","name":"版本","type":"string"},{"key":"port","name":"服务端口","type":"int"},{"key":"team","name":"负责团队","type":"string"}]','软件/应用属性',true)
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
