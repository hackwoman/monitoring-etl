"""
Demo 数据工厂 — 共享拓扑定义。

CMDB 实体创建、日志模拟、Trace Span 模拟，全部从这里取数据。
"""

# ============================================================
# 业务定义（增加 user_id 预留）
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
    "商品搜索": {
        "business_domain": "电商",
        "business_owner": "钱七",
        "tech_owner": "孙八",
        "slo_availability": 99.0,
        "slo_latency_p99": 300,
        "business_weight": 0.4,
        "labels": {"env": "prod", "business_line": "搜索"},
    },
    "消息通知": {
        "business_domain": "电商",
        "business_owner": "周九",
        "tech_owner": "吴十",
        "slo_availability": 98.0,
        "slo_latency_p99": 1000,
        "business_weight": 0.2,
        "labels": {"env": "prod", "business_line": "通知"},
    },
}

# ============================================================
# 模拟用户池（用于 user_id 关联）
# ============================================================

USER_POOL = [f"user_{i:05d}" for i in range(1, 101)]  # 100 个模拟用户

# 用户 → 业务偏好映射（模拟用户行为特征）
USER_PREFERENCES = {
    "high_value": {"pay_weight": 0.7, "search_weight": 0.2, "register_weight": 0.1},  # 高价值用户
    "normal": {"pay_weight": 0.3, "search_weight": 0.5, "register_weight": 0.2},       # 普通用户
    "new_user": {"pay_weight": 0.1, "search_weight": 0.3, "register_weight": 0.6},     # 新用户
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
    "app-04":   {"ip": "10.0.1.23", "cpu_cores": 16, "memory_gb": 64, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"}},
    "app-05":   {"ip": "10.0.1.24", "cpu_cores": 16, "memory_gb": 64, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"}},
    "db-master":{"ip": "10.0.1.30", "cpu_cores": 32, "memory_gb": 128,"os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"}},
    "db-slave": {"ip": "10.0.1.31", "cpu_cores": 32, "memory_gb": 128,"os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"}},
    "redis-01": {"ip": "10.0.1.40", "cpu_cores": 8,  "memory_gb": 32, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"}},
    "redis-02": {"ip": "10.0.1.41", "cpu_cores": 8,  "memory_gb": 32, "os": "CentOS 7.9", "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"}},
}

# ============================================================
# 服务定义（同时用于 CMDB + 日志 + Trace）
# ============================================================

SERVICES = {
    "gateway": {
        "type": "Service",
        "host": "web-01",
        "business": "在线支付",
        "attrs": {"language": "Java", "framework": "SpringCloudGateway", "port": 80, "team": "架构组"},
        "labels": {"env": "prod", "team": "架构组", "business_line": "支付"},
        "endpoints": [
            {"method": "POST", "path": "/api/order", "base_latency": 15, "weight": 40},
            {"method": "POST", "path": "/api/login", "base_latency": 10, "weight": 30},
            {"method": "GET",  "path": "/api/inventory", "base_latency": 8, "weight": 20},
            {"method": "GET",  "path": "/api/search", "base_latency": 12, "weight": 25},
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
    "search-service": {
        "type": "Service",
        "host": "app-04",
        "business": "商品搜索",
        "attrs": {"language": "Java", "framework": "SpringBoot", "port": 8084, "team": "搜索组"},
        "labels": {"env": "prod", "team": "搜索组", "business_line": "搜索"},
        "endpoints": [
            {"method": "GET",  "path": "/search/products", "base_latency": 50, "weight": 70},
            {"method": "GET",  "path": "/search/suggest", "base_latency": 20, "weight": 30},
        ],
    },
    "notification-service": {
        "type": "Service",
        "host": "app-05",
        "business": "消息通知",
        "attrs": {"language": "Go", "framework": "Gin", "port": 8085, "team": "通知组"},
        "labels": {"env": "prod", "team": "通知组", "business_line": "通知"},
        "endpoints": [
            {"method": "POST", "path": "/notify/sms", "base_latency": 100, "weight": 40},
            {"method": "POST", "path": "/notify/email", "base_latency": 80, "weight": 35},
            {"method": "POST", "path": "/notify/push", "base_latency": 50, "weight": 25},
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
    "user-db": {
        "type": "MySQL",
        "host": "db-slave",
        "business": "用户注册",
        "attrs": {"db_type": "MySQL", "port": 3306, "db_version": "8.0", "max_connections": 300},
        "labels": {"env": "prod", "team": "DBA"},
    },
    "search-db": {
        "type": "Elasticsearch",
        "host": "app-04",
        "business": "商品搜索",
        "attrs": {"db_type": "Elasticsearch", "port": 9200, "version": "7.17"},
        "labels": {"env": "prod", "team": "搜索组"},
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
    "search-cache": {
        "type": "Redis",
        "host": "redis-02",
        "business": "商品搜索",
        "attrs": {"db_type": "Redis", "port": 6380, "redis_version": "7.0"},
        "labels": {"env": "prod", "team": "搜索组"},
    },
}

NETWORK_DEVICES = {
    "核心交换机-01": {
        "attrs": {"vendor": "Cisco", "model": "C9300", "mgmt_ip": "10.0.0.1", "port_count": 48},
        "labels": {"env": "prod", "region": "cn-east-1"},
    },
    "核心交换机-02": {
        "attrs": {"vendor": "Cisco", "model": "C9300", "mgmt_ip": "10.0.0.2", "port_count": 48},
        "labels": {"env": "prod", "region": "cn-east-1"},
    },
}

# ============================================================
# 关系定义
# ============================================================

RELATIONS = [
    # Business → Service
    ("在线支付", "gateway", "includes", "businesses", "services"),
    ("在线支付", "order-service", "includes", "businesses", "services"),
    ("在线支付", "payment-service", "includes", "businesses", "services"),
    ("在线支付", "inventory-service", "includes", "businesses", "services"),
    ("用户注册", "user-service", "includes", "businesses", "services"),
    ("商品搜索", "search-service", "includes", "businesses", "services"),
    ("消息通知", "notification-service", "includes", "businesses", "services"),
    
    # Service → Service (调用关系)
    ("gateway", "order-service", "calls", "services", "services"),
    ("gateway", "payment-service", "calls", "services", "services"),
    ("gateway", "inventory-service", "calls", "services", "services"),
    ("gateway", "user-service", "calls", "services", "services"),
    ("gateway", "search-service", "calls", "services", "services"),
    ("order-service", "payment-service", "calls", "services", "services"),
    ("order-service", "notification-service", "calls", "services", "services"),
    
    # Service → Middleware (依赖关系)
    ("payment-service", "payment-db", "depends_on", "services", "middlewares"),
    ("payment-service", "user-cache", "depends_on", "services", "middlewares"),
    ("order-service", "order-db", "depends_on", "services", "middlewares"),
    ("inventory-service", "order-db", "depends_on", "services", "middlewares"),
    ("user-service", "user-cache", "depends_on", "services", "middlewares"),
    ("user-service", "session-cache", "depends_on", "services", "middlewares"),
    ("user-service", "user-db", "depends_on", "services", "middlewares"),
    ("search-service", "search-db", "depends_on", "services", "middlewares"),
    ("search-service", "search-cache", "depends_on", "services", "middlewares"),
]

# ============================================================
# 调用链定义（带 span 语义）
# ============================================================

CALL_CHAINS = {
    "create_order": {
        "description": "用户下单",
        "business": "在线支付",
        "spans": [
            ("gateway", "POST /api/order", "server", [
                ("order-service", "POST /order/create", "client", [
                    ("payment-service", "POST /pay/process", "client", [
                        ("payment-db", "INSERT orders", "client", []),
                        ("user-cache", "SETEX cache:user", "client", []),
                    ]),
                    ("inventory-service", "POST /stock/deduct", "client", [
                        ("order-db", "UPDATE stock SET", "client", []),
                    ]),
                    ("notification-service", "POST /notify/push", "client", []),
                ]),
            ]),
        ],
    },
    "user_login": {
        "description": "用户登录",
        "business": "用户注册",
        "spans": [
            ("gateway", "POST /api/login", "server", [
                ("user-service", "POST /user/login", "client", [
                    ("user-db", "SELECT * FROM users", "client", []),
                    ("session-cache", "SET session:xxx", "client", []),
                ]),
            ]),
        ],
    },
    "query_inventory": {
        "description": "查询库存",
        "business": "在线支付",
        "spans": [
            ("gateway", "GET /api/inventory", "server", [
                ("inventory-service", "GET /stock/query", "client", [
                    ("order-db", "SELECT * FROM stock", "client", []),
                ]),
            ]),
        ],
    },
    "check_payment": {
        "description": "查询支付状态",
        "business": "在线支付",
        "spans": [
            ("gateway", "GET /api/payment", "server", [
                ("payment-service", "GET /pay/status", "client", [
                    ("payment-db", "SELECT * FROM payments", "client", []),
                ]),
            ]),
        ],
    },
    "search_products": {
        "description": "商品搜索",
        "business": "商品搜索",
        "spans": [
            ("gateway", "GET /api/search", "server", [
                ("search-service", "GET /search/products", "client", [
                    ("search-db", "POST /products/_search", "client", []),
                    ("search-cache", "GET cache:search", "client", []),
                ]),
            ]),
        ],
    },
    "user_register": {
        "description": "用户注册",
        "business": "用户注册",
        "spans": [
            ("gateway", "POST /api/register", "server", [
                ("user-service", "POST /user/register", "client", [
                    ("user-db", "INSERT users", "client", []),
                    ("user-cache", "SETEX cache:user", "client", []),
                ]),
                ("notification-service", "POST /notify/email", "client", []),
            ]),
        ],
    },
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
            "payment-db": {"latency_multiplier": 10},
        },
    },
    "cascade": {
        "description": "级联故障：payment-db → payment → order",
        "faults": {
            "payment-service": {"error_rate": 0.6, "latency_multiplier": 10, "error_msg": "ConnectionTimeout: payment-db:3306"},
            "payment-db": {"latency_multiplier": 15},
            "order-service": {"error_rate": 0.25, "latency_multiplier": 3, "error_msg": "PaymentServiceException: payment failed after 3 retries"},
        },
    },
    "high_load": {
        "description": "order-service 高负载",
        "faults": {
            "order-service": {"error_rate": 0.1, "latency_multiplier": 5, "error_msg": "Thread pool exhausted, request queued"},
        },
    },
    "search_slow": {
        "description": "搜索服务慢",
        "faults": {
            "search-service": {"error_rate": 0.15, "latency_multiplier": 6, "error_msg": "Elasticsearch timeout"},
            "search-db": {"latency_multiplier": 8},
        },
    },
}

# DB/中间件的基础延迟
DB_BASE_LATENCY = {
    "payment-db": {"INSERT": 5, "SELECT": 3, "UPDATE": 4, "default": 3},
    "order-db":   {"INSERT": 5, "SELECT": 3, "UPDATE": 4, "default": 3},
    "user-db":    {"INSERT": 4, "SELECT": 2, "UPDATE": 3, "default": 2},
    "search-db":  {"POST": 15, "GET": 10, "default": 12},
    "user-cache":    {"GET": 1, "SET": 1, "SETEX": 1, "default": 1},
    "session-cache": {"GET": 1, "SET": 1, "SETEX": 1, "default": 1},
    "search-cache":  {"GET": 1, "SET": 1, "SETEX": 1, "default": 1},
}

# ============================================================
# 健康度覆盖
# ============================================================

HEALTH_OVERRIDES = {
    "payment-service": {"health_score": 72, "health_level": "warning", "risk_score": 78},
    "payment-db":      {"health_score": 55, "health_level": "critical", "risk_score": 85},
    "db-master":       {"health_score": 60, "health_level": "warning", "risk_score": 70},
}
