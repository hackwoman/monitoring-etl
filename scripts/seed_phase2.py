#!/usr/bin/env python3
"""Phase 2 预置数据：属性模板 + 内置类型定义。

加载顺序：
1. attribute_template (6 套模板)
2. entity_type_def (10 种内置类型，含完整 definition)
3. label_definition (补充标准维度)
4. data_check_rule (10 条预置检查规则)
"""

import os
import json
import psycopg2

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    "dbname": os.getenv("CMDB_DATABASE", "cmdb"),
}

# ============================================================
# 属性模板
# ============================================================

ATTRIBUTE_TEMPLATES = [
    {
        "template_name": "base_hardware",
        "category": "infrastructure",
        "description": "基础硬件属性",
        "is_builtin": True,
        "attributes": [
            {"key": "cpu_cores", "name": "CPU核数", "type": "int"},
            {"key": "memory_gb", "name": "内存(GB)", "type": "int"},
            {"key": "disk_gb", "name": "磁盘(GB)", "type": "int"},
            {"key": "os", "name": "操作系统", "type": "string"},
            {"key": "os_version", "name": "系统版本", "type": "string"},
            {"key": "sn", "name": "序列号", "type": "string"},
            {"key": "ip", "name": "IP地址", "type": "string"},
        ],
    },
    {
        "template_name": "base_network",
        "category": "infrastructure",
        "description": "网络设备属性",
        "is_builtin": True,
        "attributes": [
            {"key": "vendor", "name": "厂商", "type": "string"},
            {"key": "model", "name": "型号", "type": "string"},
            {"key": "mgmt_ip", "name": "管理IP", "type": "string"},
            {"key": "port_count", "name": "端口数", "type": "int"},
            {"key": "firmware_version", "name": "固件版本", "type": "string"},
        ],
    },
    {
        "template_name": "base_database",
        "category": "middleware",
        "description": "数据库属性",
        "is_builtin": True,
        "attributes": [
            {"key": "db_type", "name": "数据库类型", "type": "string"},
            {"key": "db_version", "name": "版本", "type": "string"},
            {"key": "port", "name": "端口", "type": "int"},
            {"key": "max_connections", "name": "最大连接数", "type": "int"},
            {"key": "replication_mode", "name": "复制模式", "type": "string"},
        ],
    },
    {
        "template_name": "base_container",
        "category": "runtime",
        "description": "容器/K8s属性",
        "is_builtin": True,
        "attributes": [
            {"key": "cluster_name", "name": "集群名", "type": "string"},
            {"key": "namespace", "name": "命名空间", "type": "string"},
            {"key": "node_count", "name": "节点数", "type": "int"},
            {"key": "k8s_version", "name": "K8s版本", "type": "string"},
            {"key": "container_runtime", "name": "容器运行时", "type": "string"},
        ],
    },
    {
        "template_name": "base_cloud",
        "category": "infrastructure",
        "description": "云资源属性",
        "is_builtin": True,
        "attributes": [
            {"key": "cloud_provider", "name": "云厂商", "type": "string"},
            {"key": "region", "name": "地域", "type": "string"},
            {"key": "az", "name": "可用区", "type": "string"},
            {"key": "instance_type", "name": "实例规格", "type": "string"},
            {"key": "vpc_id", "name": "VPC ID", "type": "string"},
            {"key": "charge_type", "name": "计费方式", "type": "string"},
        ],
    },
    {
        "template_name": "base_software",
        "category": "application",
        "description": "软件/应用属性",
        "is_builtin": True,
        "attributes": [
            {"key": "language", "name": "编程语言", "type": "string"},
            {"key": "framework", "name": "框架", "type": "string"},
            {"key": "version", "name": "版本", "type": "string"},
            {"key": "port", "name": "服务端口", "type": "int"},
            {"key": "team", "name": "负责团队", "type": "string"},
            {"key": "repo_url", "name": "代码仓库", "type": "string"},
        ],
    },
]

# ============================================================
# 内置类型定义
# ============================================================

BUILTIN_TYPES = [
    {
        "type_name": "Business",
        "display_name": "业务服务",
        "category": "business",
        "icon": "business",
        "description": "业务层实体，如在线支付、用户注册等",
        "definition": {
            "attributes": [
                {"key": "business_domain", "name": "业务域", "type": "string"},
                {"key": "business_owner", "name": "业务负责人", "type": "string"},
                {"key": "tech_owner", "name": "技术负责人", "type": "string"},
                {"key": "slo_availability", "name": "可用性SLO(%)", "type": "float"},
                {"key": "slo_latency_p99", "name": "P99延迟目标(ms)", "type": "int"},
                {"key": "business_weight", "name": "业务权重", "type": "float"},
            ],
            "templates": [],
            "metrics": [
                {"name": "business.success_rate", "display": "业务成功率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 99.0, "crit": 95.0}},
                {"name": "business.response_time", "display": "业务响应时间", "type": "gauge", "unit": "ms", "thresholds": {"warn": 500, "crit": 2000}},
                {"name": "business.throughput", "display": "业务吞吐量", "type": "gauge", "unit": "count/s"},
            ],
            "relations": [
                {"type": "includes", "direction": "out", "target": "Service"},
                {"type": "includes", "direction": "out", "target": "Database"},
            ],
            "health": {
                "method": "children_avg",
                "description": "下属资源健康度加权平均",
            },
            "discovery": {"auto_match": [], "reconcile_priority": ["name"]},
        },
    },
    {
        "type_name": "Service",
        "display_name": "微服务",
        "category": "application",
        "icon": "service",
        "description": "微服务实例",
        "definition": {
            "attributes": [
                {"key": "language", "name": "编程语言", "type": "string"},
                {"key": "framework", "name": "框架", "type": "string"},
                {"key": "port", "name": "服务端口", "type": "int"},
                {"key": "team", "name": "负责团队", "type": "string"},
            ],
            "templates": ["base_software"],
            "metrics": [
                {"name": "http.server.request.duration", "display": "HTTP请求延迟", "type": "histogram", "unit": "ms", "otel": "http.server.request.duration",
                 "thresholds": {"p99_warn": 500, "p99_crit": 2000}, "dimensions": ["method", "route", "status_code"]},
                {"name": "http.server.request.count", "display": "HTTP请求量", "type": "counter", "unit": "count/s",
                 "dimensions": ["method", "status_code"]},
                {"name": "http.server.request.error_rate", "display": "错误率", "type": "gauge", "unit": "percent",
                 "thresholds": {"warn": 1, "crit": 5}},
                {"name": "system.cpu.usage", "display": "CPU使用率", "type": "gauge", "unit": "percent",
                 "thresholds": {"warn": 70, "crit": 90}},
                {"name": "system.memory.usage", "display": "内存使用率", "type": "gauge", "unit": "percent",
                 "thresholds": {"warn": 80, "crit": 95}},
            ],
            "relations": [
                {"type": "calls", "direction": "out", "target": "Service"},
                {"type": "depends_on", "direction": "out", "target": "Database"},
                {"type": "runs_on", "direction": "out", "target": "Host"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "latency", "metric": "http.server.request.duration.p99", "weight": 0.4},
                    {"name": "error_rate", "metric": "http.server.request.error_rate", "weight": 0.3},
                    {"name": "saturation", "metric": "system.cpu.usage", "weight": 0.3},
                ],
            },
            "discovery": {
                "auto_match": ["service.name"],
                "reconcile_priority": ["qualified_name", "name"],
            },
        },
    },
    {
        "type_name": "Host",
        "display_name": "主机",
        "category": "infrastructure",
        "icon": "host",
        "description": "物理机/虚拟机/云主机",
        "definition": {
            "attributes": [],
            "templates": ["base_hardware", "base_cloud"],
            "metrics": [
                {"name": "system.cpu.usage", "display": "CPU使用率", "type": "gauge", "unit": "percent", "otel": "system.cpu.utilization",
                 "thresholds": {"warn": 70, "crit": 90}},
                {"name": "system.memory.usage", "display": "内存使用率", "type": "gauge", "unit": "percent",
                 "thresholds": {"warn": 80, "crit": 95}},
                {"name": "system.disk.usage", "display": "磁盘使用率", "type": "gauge", "unit": "percent",
                 "thresholds": {"warn": 80, "crit": 90}, "dimensions": ["mount_point"]},
                {"name": "system.disk.io.util", "display": "磁盘IO利用率", "type": "gauge", "unit": "percent",
                 "thresholds": {"warn": 70, "crit": 90}},
                {"name": "system.network.io", "display": "网络流量", "type": "counter", "unit": "bytes/s"},
                {"name": "system.load.1m", "display": "系统负载(1min)", "type": "gauge",
                 "thresholds": {"warn": 4, "crit": 8}},
            ],
            "relations": [
                {"type": "hosts", "direction": "out", "target": "Service"},
                {"type": "connected_to", "direction": "out", "target": "NetworkDevice"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "cpu", "metric": "system.cpu.usage", "weight": 0.3},
                    {"name": "memory", "metric": "system.memory.usage", "weight": 0.3},
                    {"name": "disk", "metric": "system.disk.usage", "weight": 0.2},
                    {"name": "io", "metric": "system.disk.io.util", "weight": 0.2},
                ],
            },
            "discovery": {
                "auto_match": ["host.name", "host.ip"],
                "reconcile_priority": ["qualified_name", "attributes.sn", "attributes.ip", "name"],
            },
        },
    },
    {
        "type_name": "Database",
        "display_name": "数据库",
        "category": "middleware",
        "icon": "database",
        "description": "数据库实例(MySQL/PostgreSQL/MongoDB等)",
        "definition": {
            "attributes": [
                {"key": "db_type", "name": "数据库类型", "type": "string"},
                {"key": "db_version", "name": "版本", "type": "string"},
                {"key": "port", "name": "端口", "type": "int"},
                {"key": "max_connections", "name": "最大连接数", "type": "int"},
            ],
            "templates": ["base_database"],
            "metrics": [
                {"name": "db.connections.active", "display": "活跃连接数", "type": "gauge", "unit": "count",
                 "thresholds": {"warn": 80, "crit": 95}},
                {"name": "db.queries.slow", "display": "慢查询数", "type": "counter", "unit": "count/min",
                 "thresholds": {"rate_warn": 10, "rate_crit": 50}},
                {"name": "db.replication.lag", "display": "复制延迟", "type": "gauge", "unit": "seconds",
                 "thresholds": {"warn": 5, "crit": 30}},
                {"name": "db.query.duration", "display": "查询延迟", "type": "histogram", "unit": "ms",
                 "thresholds": {"p99_warn": 100, "p99_crit": 1000}},
            ],
            "relations": [
                {"type": "runs_on", "direction": "out", "target": "Host"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "connections", "metric": "db.connections.active", "weight": 0.3},
                    {"name": "slow_queries", "metric": "db.queries.slow", "weight": 0.3},
                    {"name": "replication", "metric": "db.replication.lag", "weight": 0.2},
                    {"name": "query_latency", "metric": "db.query.duration.p99", "weight": 0.2},
                ],
            },
            "discovery": {
                "auto_match": ["host.name"],
                "reconcile_priority": ["qualified_name", "name"],
            },
        },
    },
    {
        "type_name": "MySQL",
        "display_name": "MySQL数据库",
        "category": "middleware",
        "icon": "mysql",
        "super_type": "Database",
        "description": "MySQL 数据库实例",
        "definition": {
            "attributes": [
                {"key": "storage_engine", "name": "存储引擎", "type": "string"},
                {"key": "binlog_format", "name": "Binlog格式", "type": "string"},
            ],
            "templates": ["base_database"],
            "metrics": [
                {"name": "mysql.connections.active", "display": "活跃连接数", "type": "gauge", "unit": "count", "thresholds": {"warn": 80, "crit": 95}},
                {"name": "mysql.queries.slow", "display": "慢查询数", "type": "counter", "unit": "count/min", "thresholds": {"rate_warn": 10, "rate_crit": 50}},
                {"name": "mysql.replication.lag", "display": "复制延迟", "type": "gauge", "unit": "seconds", "thresholds": {"warn": 5, "crit": 30}},
                {"name": "mysql.buffer_pool.hit_rate", "display": "Buffer Pool命中率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 95, "crit": 90}},
                {"name": "mysql.threads.running", "display": "运行线程数", "type": "gauge", "unit": "count", "thresholds": {"warn": 50, "crit": 100}},
            ],
            "relations": [
                {"type": "runs_on", "direction": "out", "target": "Host"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "connections", "metric": "mysql.connections.active", "weight": 0.25},
                    {"name": "slow_queries", "metric": "mysql.queries.slow", "weight": 0.25},
                    {"name": "replication", "metric": "mysql.replication.lag", "weight": 0.25},
                    {"name": "buffer_pool", "metric": "mysql.buffer_pool.hit_rate", "weight": 0.25},
                ],
            },
            "discovery": {"auto_match": ["host.name"], "reconcile_priority": ["qualified_name", "name"]},
        },
    },
    {
        "type_name": "Redis",
        "display_name": "Redis缓存",
        "category": "middleware",
        "icon": "redis",
        "description": "Redis 缓存实例",
        "definition": {
            "attributes": [
                {"key": "redis_version", "name": "Redis版本", "type": "string"},
                {"key": "max_memory", "name": "最大内存", "type": "string"},
                {"key": "port", "name": "端口", "type": "int"},
            ],
            "templates": [],
            "metrics": [
                {"name": "redis.memory.usage", "display": "内存使用率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 80, "crit": 95}},
                {"name": "redis.clients.connected", "display": "连接客户端数", "type": "gauge", "unit": "count", "thresholds": {"warn": 500, "crit": 1000}},
                {"name": "redis.commands.hit_rate", "display": "命令命中率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 95, "crit": 90}},
                {"name": "redis.key.count", "display": "Key数量", "type": "gauge", "unit": "count"},
                {"name": "redis.evicted.keys", "display": "淘汰Key数", "type": "counter", "unit": "count/min"},
            ],
            "relations": [
                {"type": "runs_on", "direction": "out", "target": "Host"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "memory", "metric": "redis.memory.usage", "weight": 0.3},
                    {"name": "hit_rate", "metric": "redis.commands.hit_rate", "weight": 0.4},
                    {"name": "connections", "metric": "redis.clients.connected", "weight": 0.3},
                ],
            },
            "discovery": {"auto_match": ["host.name"], "reconcile_priority": ["qualified_name", "name"]},
        },
    },
    {
        "type_name": "NetworkDevice",
        "display_name": "网络设备",
        "category": "infrastructure",
        "icon": "network",
        "description": "交换机/路由器/防火墙等网络设备",
        "definition": {
            "attributes": [],
            "templates": ["base_network"],
            "metrics": [
                {"name": "network.port.utilization", "display": "端口利用率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 70, "crit": 90}},
                {"name": "network.packet.loss", "display": "丢包率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 0.1, "crit": 1.0}},
                {"name": "network.latency", "display": "网络延迟", "type": "gauge", "unit": "ms", "thresholds": {"warn": 10, "crit": 50}},
            ],
            "relations": [
                {"type": "connected_to", "direction": "out", "target": "Host"},
                {"type": "connected_to", "direction": "out", "target": "NetworkDevice"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "packet_loss", "metric": "network.packet.loss", "weight": 0.5},
                    {"name": "latency", "metric": "network.latency", "weight": 0.3},
                    {"name": "utilization", "metric": "network.port.utilization", "weight": 0.2},
                ],
            },
            "discovery": {"auto_match": ["attributes.mgmt_ip"], "reconcile_priority": ["attributes.sn", "attributes.mgmt_ip", "name"]},
        },
    },
    {
        "type_name": "K8sCluster",
        "display_name": "K8s集群",
        "category": "runtime",
        "icon": "k8s",
        "description": "Kubernetes 集群",
        "definition": {
            "attributes": [],
            "templates": ["base_container"],
            "metrics": [
                {"name": "k8s.node.ready", "display": "就绪节点数", "type": "gauge", "unit": "count"},
                {"name": "k8s.pod.running", "display": "运行中Pod数", "type": "gauge", "unit": "count"},
                {"name": "k8s.cpu.utilization", "display": "CPU利用率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 70, "crit": 90}},
                {"name": "k8s.memory.utilization", "display": "内存利用率", "type": "gauge", "unit": "percent", "thresholds": {"warn": 80, "crit": 95}},
            ],
            "relations": [
                {"type": "contains", "direction": "out", "target": "K8sPod"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "cpu", "metric": "k8s.cpu.utilization", "weight": 0.4},
                    {"name": "memory", "metric": "k8s.memory.utilization", "weight": 0.4},
                    {"name": "nodes", "metric": "k8s.node.ready", "weight": 0.2},
                ],
            },
            "discovery": {"auto_match": ["attributes.cluster_name"], "reconcile_priority": ["name"]},
        },
    },
    {
        "type_name": "K8sPod",
        "display_name": "K8s Pod",
        "category": "runtime",
        "icon": "pod",
        "description": "Kubernetes Pod",
        "definition": {
            "attributes": [
                {"key": "namespace", "name": "命名空间", "type": "string"},
                {"key": "node_name", "name": "所在节点", "type": "string"},
                {"key": "restart_count", "name": "重启次数", "type": "int"},
            ],
            "templates": [],
            "metrics": [
                {"name": "k8s.pod.cpu.usage", "display": "CPU使用", "type": "gauge", "unit": "millicores"},
                {"name": "k8s.pod.memory.usage", "display": "内存使用", "type": "gauge", "unit": "bytes"},
                {"name": "k8s.pod.restarts", "display": "重启次数", "type": "counter", "unit": "count", "thresholds": {"rate_warn": 3, "rate_crit": 10}},
                {"name": "k8s.pod.ready", "display": "就绪状态", "type": "gauge", "unit": "bool"},
            ],
            "relations": [
                {"type": "runs", "direction": "out", "target": "Service"},
                {"type": "scheduled_on", "direction": "out", "target": "Host"},
            ],
            "health": {
                "method": "weighted_avg",
                "dimensions": [
                    {"name": "cpu", "metric": "k8s.pod.cpu.usage", "weight": 0.3},
                    {"name": "memory", "metric": "k8s.pod.memory.usage", "weight": 0.3},
                    {"name": "restarts", "metric": "k8s.pods.restarts", "weight": 0.4},
                ],
            },
            "discovery": {"auto_match": ["name", "attributes.namespace"], "reconcile_priority": ["qualified_name", "name"]},
        },
    },
]

# ============================================================
# 预置标签定义
# ============================================================

LABEL_DEFINITIONS = [
    ("env", "环境", "enum", '["prod","staging","dev","test"]', "部署环境"),
    ("team", "团队", "string", None, "负责团队"),
    ("business_line", "业务线", "string", None, "业务归属"),
    ("region", "地域", "string", None, "部署地域"),
    ("tenant", "租户", "string", None, "多租户隔离标识"),
    ("project", "项目", "string", None, "项目归属"),
    ("app_version", "应用版本", "string", None, "应用发布版本"),
]

# ============================================================
# 预置数据检查规则
# ============================================================

CHECK_RULES = [
    {
        "rule_name": "主机必须有业务归属",
        "rule_type": "completeness",
        "target_type": "Host",
        "check_sql": "SELECT guid FROM entity WHERE type_name = 'Host' AND status = 'active' AND (biz_service IS NULL OR biz_service = '')",
        "severity": "warning",
    },
    {
        "rule_name": "数据库必须有负责人(team标签)",
        "rule_type": "completeness",
        "target_type": "Database",
        "check_sql": "SELECT guid FROM entity WHERE type_name IN ('Database','MySQL','PostgreSQL','Redis') AND status = 'active' AND (labels->>'team' IS NULL OR labels->>'team' = '')",
        "severity": "warning",
    },
    {
        "rule_name": "服务必须有环境标签",
        "rule_type": "completeness",
        "target_type": "Service",
        "check_sql": "SELECT guid FROM entity WHERE type_name = 'Service' AND status = 'active' AND (labels->>'env' IS NULL OR labels->>'env' = '')",
        "severity": "warning",
    },
    {
        "rule_name": "IP地址不能重复",
        "rule_type": "uniqueness",
        "target_type": "Host",
        "check_sql": "SELECT attributes->>'ip' FROM entity WHERE type_name = 'Host' AND status = 'active' AND attributes->>'ip' IS NOT NULL GROUP BY attributes->>'ip' HAVING COUNT(*) > 1",
        "severity": "error",
    },
    {
        "rule_name": "实体名不能重复(同类型)",
        "rule_type": "uniqueness",
        "target_type": None,
        "check_sql": "SELECT type_name, name FROM entity WHERE status = 'active' GROUP BY type_name, name HAVING COUNT(*) > 1",
        "severity": "error",
    },
    {
        "rule_name": "健康度异常但无活跃告警",
        "rule_type": "consistency",
        "target_type": None,
        "check_sql": "SELECT guid FROM entity WHERE health_level IN ('critical','down') AND status = 'active' AND risk_score IS NULL",
        "severity": "warning",
    },
    {
        "rule_name": "实体超过30天未更新",
        "rule_type": "freshness",
        "target_type": None,
        "check_sql": "SELECT guid FROM entity WHERE status = 'active' AND updated_at < now() - INTERVAL '30 days'",
        "severity": "warning",
    },
    {
        "rule_name": "关系两端实体必须存在",
        "rule_type": "consistency",
        "target_type": None,
        "check_sql": "SELECT r.guid FROM relationship r LEFT JOIN entity e1 ON r.from_guid = e1.guid LEFT JOIN entity e2 ON r.to_guid = e2.guid WHERE r.is_active = true AND (e1.guid IS NULL OR e2.guid IS NULL)",
        "severity": "error",
    },
    {
        "rule_name": "孤立实体(无任何关系)",
        "rule_type": "completeness",
        "target_type": None,
        "check_sql": "SELECT e.guid FROM entity e LEFT JOIN relationship r1 ON e.guid = r1.from_guid AND r1.is_active = true LEFT JOIN relationship r2 ON e.guid = r2.to_guid AND r2.is_active = true WHERE e.status = 'active' AND e.type_name != 'Business' AND r1.guid IS NULL AND r2.guid IS NULL",
        "severity": "warning",
    },
    {
        "rule_name": "业务实体必须有SLO定义",
        "rule_type": "completeness",
        "target_type": "Business",
        "check_sql": "SELECT guid FROM entity WHERE type_name = 'Business' AND status = 'active' AND (attributes->>'slo_availability' IS NULL)",
        "severity": "warning",
    },
]


def seed():
    """加载 Phase 2 预置数据。"""
    print("🌱 Phase 2 预置数据加载")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. 属性模板
        print("   📋 属性模板...")
        for tmpl in ATTRIBUTE_TEMPLATES:
            cur.execute("""
                INSERT INTO attribute_template (template_name, category, attributes, description, is_builtin)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (template_name) DO UPDATE SET
                    attributes = EXCLUDED.attributes,
                    description = EXCLUDED.description
            """, (tmpl["template_name"], tmpl["category"],
                  json.dumps(tmpl["attributes"]), tmpl["description"], True))
        print(f"      ✅ {len(ATTRIBUTE_TEMPLATES)} 套模板")

        # 2. 内置类型
        print("   📦 内置类型定义...")
        for typ in BUILTIN_TYPES:
            # 更新已有记录的 display_name
            cur.execute("""
                INSERT INTO entity_type_def (type_name, display_name, category, icon, super_type, definition, description, is_custom)
                VALUES (%s, %s, %s, %s, %s, %s, %s, false)
                ON CONFLICT (type_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    category = EXCLUDED.category,
                    icon = EXCLUDED.icon,
                    super_type = EXCLUDED.super_type,
                    definition = EXCLUDED.definition,
                    description = EXCLUDED.description,
                    updated_at = now()
            """, (typ["type_name"], typ.get("display_name"), typ.get("category"),
                  typ.get("icon"), typ.get("super_type"),
                  json.dumps(typ["definition"]), typ.get("description")))
        print(f"      ✅ {len(BUILTIN_TYPES)} 种类型")

        # 3. 标签定义
        print("   🏷️  标签定义...")
        for key, name, vtype, enum, desc in LABEL_DEFINITIONS:
            cur.execute("""
                INSERT INTO label_definition (label_key, label_name, value_type, enum_values, description)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (label_key) DO UPDATE SET
                    label_name = EXCLUDED.label_name,
                    enum_values = EXCLUDED.enum_values,
                    description = EXCLUDED.description
            """, (key, name, vtype, enum, desc))
        print(f"      ✅ {len(LABEL_DEFINITIONS)} 个标签")

        # 4. 数据检查规则
        print("   🔍 数据检查规则...")
        for rule in CHECK_RULES:
            cur.execute("""
                INSERT INTO data_check_rule (rule_name, rule_type, target_type, check_sql, severity, is_builtin)
                VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT DO NOTHING
            """, (rule["rule_name"], rule["rule_type"], rule["target_type"],
                  rule["check_sql"], rule["severity"]))
        print(f"      ✅ {len(CHECK_RULES)} 条规则")

        conn.commit()
        print("\n✅ 预置数据加载完成")

        # 验证
        cur.execute("SELECT type_name, category FROM entity_type_def ORDER BY type_name")
        print("\n   实体类型:")
        for row in cur.fetchall():
            print(f"      {row[0]} ({row[1]})")

        cur.execute("SELECT template_name, category FROM attribute_template ORDER BY template_name")
        print("\n   属性模板:")
        for row in cur.fetchall():
            print(f"      {row[0]} ({row[1]})")

        cur.execute("SELECT COUNT(*) FROM data_check_rule WHERE is_builtin = true")
        print(f"\n   检查规则: {cur.fetchone()[0]} 条")

    except Exception as e:
        conn.rollback()
        print(f"❌ 加载失败: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    seed()
