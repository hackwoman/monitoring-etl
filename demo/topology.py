"""
Demo 数据工厂 — 共享拓扑定义。

CMDB 实体创建、日志模拟、指标生成，全部从这里取数据。
保证数据一致性。
"""

# ============================================================
# 业务定义
# ============================================================

BUSINESSES = {
    "在线支付": {
        "business_domain": "电商",
        "business_owner": "张三",
        "tech_owner": "李四",
        "slo_availability": 99.9,
        "slo_latency_p99": 200,
        "business_weight": 1.0,
        "labels": {"env": "prod", "business_line": "支付"},
    },
    "用户注册": {
        "business_domain": "电商",
        "business_owner": "王五",
        "tech_owner": "赵六",
        "slo_availability": 99.5,
        "slo_latency_p99": 500,
        "business_weight": 0.6,
        "labels": {"env": "prod", "business_line": "用户"},
    },
}

# ============================================================
# 主机定义
# ============================================================

HOSTS = {
    "web-01":   {"ip": "10.0.1.10", "cpu_cores": 8,  "memory_gb": 32, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"}},
    "web-02":   {"ip": "10.0.1.11", "cpu_cores": 8,  "memory_gb": 32, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"}},
    "app-01":   {"ip": "10.0.1.20", "cpu_cores": 16, "memory_gb": 64, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"}},
    "app-02":   {"ip": "10.0.1.21", "cpu_cores": 16, "memory_gb": 64, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"}},
    "app-03":   {"ip": "10.0.1.22", "cpu_cores": 16, "memory_gb": 64, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"}},
    "db-master":{"ip": "10.0.1.30", "cpu_cores": 32, "memory_gb": 128,"os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"}},
    "db-slave": {"ip": "10.0.1.31", "cpu_cores": 32, "memory_gb": 128,"os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"}},
    "redis-01": {"ip": "10.0.1.40", "cpu_cores": 8,  "memory_gb": 32, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"}},
}

# ============================================================
# 服务定义（同时用于 CMDB + 日志模拟）
# ============================================================

SERVICES = {
    "gateway": {
        "type": "Service",
        "host": "web-01",
        "business": "在线支付",
        "attrs": {"language": "Java", "framework": "SpringCloudGateway", "port": 80, "team": "架构组"},
        "labels": {"env": "prod", "team": "架构组", "business_line": "支付"},
        # 日志模拟配置
        "endpoints": [
            {"method": "POST", "path": "/api/order", "base_latency": 15, "weight": 40},
            {"method": "POST", "path": "/api/login", "base_latency": 10, "weight": 30},
            {"method": "GET",  "path": "/api/inventory", "base_latency": 8, "weight": 20},
            {"method": "GET",  "path": "/api/health", "base_latency": 2, "weight": 10},
        ],
    },
    "order-service": {
        "type": "Service",
        "host": "app-01",
        "business": "在线支付",
        "attrs": {"language": "Java", "framework": "SpringBoot", "port": 8081, "team": "订单组"},
        "labels": {"env": "prod", "team": "订单组", "business_line": "支付"},
        "endpoints": [
            {"method": "POST", "path": "/order/create", "base_latency": 120, "weight": 50},
            {"method": "GET",  "path": "/order/list", "base_latency": 45, "weight": 30},
            {"method": "GET",  "path": "/order/detail", "base_latency": 30, "weight": 20},
        ],
    },
    "payment-service": {
        "type": "Service",
        "host": "app-02",
        "business": "在线支付",
        "attrs": {"language": "Java", "framework": "SpringBoot", "port": 8080, "team": "支付组"},
        "labels": {"env": "prod", "team": "支付组", "business_line": "支付"},
        "endpoints": [
            {"method": "POST", "path": "/pay/process", "base_latency": 80, "weight": 60},
            {"method": "GET",  "path": "/pay/status", "base_latency": 20, "weight": 40},
        ],
    },
    "inventory-service": {
        "type": "Service",
        "host": "app-03",
        "business": "在线支付",
        "attrs": {"language": "Go", "framework": "Gin", "port": 8082, "team": "库存组"},
        "labels": {"env": "prod", "team": "库存组", "business_line": "支付"},
        "endpoints": [
            {"method": "GET",  "path": "/stock/query", "base_latency": 35, "weight": 50},
            {"method": "POST", "path": "/stock/deduct", "base_latency": 50, "weight": 30},
            {"method": "POST", "path": "/stock/restock", "base_latency": 40, "weight": 20},
        ],
    },
    "user-service": {
        "type": "Service",
        "host": "app-02",
        "business": "用户注册",
        "attrs": {"language": "Go", "framework": "Gin", "port": 8083, "team": "用户组"},
        "labels": {"env": "prod", "team": "用户组", "business_line": "用户"},
        "endpoints": [
            {"method": "POST", "path": "/user/register", "base_latency": 60, "weight": 40},
            {"method": "GET",  "path": "/user/profile", "base_latency": 15, "weight": 60},
        ],
    },
}

# ============================================================
# 数据库/缓存定义
# ============================================================

MIDDLEWARES = {
    "payment-db": {
        "type": "MySQL",
        "host": "db-master",
        "business": "在线支付",
        "attrs": {"db_type": "MySQL", "port": 3306, "db_version": "8.0", "max_connections": 500},
        "labels": {"env": "prod", "team": "DBA"},
    },
    "order-db": {
        "type": "MySQL",
        "host": "db-master",
        "business": "在线支付",
        "attrs": {"db_type": "MySQL", "port": 3306, "db_version": "8.0", "max_connections": 500},
        "labels": {"env": "prod", "team": "DBA"},
    },
    "user-cache": {
        "type": "Redis",
        "host": "redis-01",
        "business": "在线支付",
        "attrs": {"db_type": "Redis", "port": 6379, "redis_version": "7.0"},
        "labels": {"env": "prod", "team": "DBA"},
    },
    "session-cache": {
        "type": "Redis",
        "host": "redis-01",
        "business": "用户注册",
        "attrs": {"db_type": "Redis", "port": 6379, "redis_version": "7.0"},
        "labels": {"env": "prod", "team": "DBA"},
    },
}

# ============================================================
# 网络设备
# ============================================================

NETWORK_DEVICES = {
    "核心交换机-01": {
        "attrs": {"vendor": "Cisco", "model": "C9300", "mgmt_ip": "10.0.0.1", "port_count": 48},
        "labels": {"env": "prod", "region": "cn-east-1"},
    },
}

# ============================================================
# 关系定义（统一声明）
# ============================================================

# (source_key, target_key, relation_type, source_pool, target_pool)
RELATIONS = [
    # 业务 → 服务
    ("在线支付", "gateway", "includes", "businesses", "services"),
    ("在线支付", "order-service", "includes", "businesses", "services"),
    ("在线支付", "payment-service", "includes", "businesses", "services"),
    ("在线支付", "inventory-service", "includes", "businesses", "services"),
    ("用户注册", "user-service", "includes", "businesses", "services"),
    # 服务调用
    ("gateway", "order-service", "calls", "services", "services"),
    ("gateway", "payment-service", "calls", "services", "services"),
    ("gateway", "inventory-service", "calls", "services", "services"),
    ("gateway", "user-service", "calls", "services", "services"),
    ("order-service", "payment-service", "calls", "services", "services"),
    # 服务依赖数据库
    ("payment-service", "payment-db", "depends_on", "services", "middlewares"),
    ("payment-service", "user-cache", "depends_on", "services", "middlewares"),
    ("order-service", "order-db", "depends_on", "services", "middlewares"),
    ("inventory-service", "order-db", "depends_on", "services", "middlewares"),
    ("user-service", "user-cache", "depends_on", "services", "middlewares"),
    ("user-service", "session-cache", "depends_on", "services", "middlewares"),
    # 服务运行在主机 (由 services.*.host 字段隐含定义)
    # 数据库运行在主机 (由 middlewares.*.host 字段隐含定义)
]

# ============================================================
# 调用链定义（日志模拟用）
# ============================================================

CALL_CHAINS = {
    "create_order": ["gateway", "order-service", "payment-service", "inventory-service"],
    "user_login": ["gateway", "user-service"],
    "query_inventory": ["gateway", "inventory-service"],
    "check_payment": ["gateway", "payment-service"],
    "user_register": ["gateway", "user-service"],
}

# ============================================================
# 故障场景
# ============================================================

SCENARIOS = {
    "normal": {
        "description": "正常运营",
        "faults": {},
    },
    "slow_db": {
        "description": "payment-db 慢查询",
        "faults": {
            "payment-service": {"error_rate": 0.3, "latency_multiplier": 8, "error_msg": "ConnectionTimeout: payment-db:3306 after 5000ms"},
        },
    },
    "cascade": {
        "description": "级联故障：payment-db → payment → order",
        "faults": {
            "payment-service": {"error_rate": 0.6, "latency_multiplier": 10, "error_msg": "ConnectionTimeout: payment-db:3306"},
            "order-service": {"error_rate": 0.25, "latency_multiplier": 3, "error_msg": "PaymentServiceException: payment failed after 3 retries"},
        },
    },
    "high_load": {
        "description": "order-service 高负载",
        "faults": {
            "order-service": {"error_rate": 0.1, "latency_multiplier": 5, "error_msg": "Thread pool exhausted, request queued"},
        },
    },
}

# ============================================================
# 异常时默认健康度（模拟数据）
# ============================================================

HEALTH_OVERRIDES = {
    "payment-service": {"health_score": 72, "health_level": "warning", "risk_score": 78},
    "payment-db":      {"health_score": 55, "health_level": "critical", "risk_score": 85},
    "db-master":       {"health_score": 60, "health_level": "warning", "risk_score": 70},
}
