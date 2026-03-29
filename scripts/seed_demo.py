#!/usr/bin/env python3
"""演示数据：模拟一个在线支付业务的完整资源体系。"""

import requests, json

BASE = "http://localhost:8001/api/v1/cmdb"

def post(path, data):
    r = requests.post(f"{BASE}{path}", json=data)
    print(f"  POST {path} → {r.status_code}")
    return r.json() if r.ok else None

# ============================================================
# 业务实体
# ============================================================
print("🏢 创建业务实体...")
biz = post("/entities", {
    "type_name": "Business",
    "name": "在线支付",
    "attributes": {
        "business_domain": "电商",
        "business_owner": "张三",
        "tech_owner": "李四",
        "slo_availability": 99.9,
        "slo_latency_p99": 200,
        "business_weight": 1.0
    },
    "labels": {"env": "prod", "business_line": "支付"},
    "biz_service": "在线支付",
    "source": "manual"
})

biz2 = post("/entities", {
    "type_name": "Business",
    "name": "用户注册",
    "attributes": {"business_domain": "电商", "slo_availability": 99.5},
    "labels": {"env": "prod", "business_line": "用户"},
    "biz_service": "用户注册",
    "source": "manual"
})

# ============================================================
# 主机
# ============================================================
print("\n🖥️  创建主机...")
hosts = {}
for i, name in enumerate(["web-01", "web-02", "app-01", "app-02", "db-master", "db-slave", "redis-01"]):
    h = post("/entities", {
        "type_name": "Host",
        "name": name,
        "attributes": {"ip": f"10.0.1.{i+10}", "cpu_cores": 8, "memory_gb": 32, "os": "CentOS 7.9"},
        "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"},
        "biz_service": "在线支付" if i < 6 else "在线支付",
        "source": "manual"
    })
    if h:
        hosts[name] = h["guid"]

# ============================================================
# 服务
# ============================================================
print("\n⚙️  创建服务...")
svcs = {}
for name, attrs in [
    ("payment-service", {"language": "Java", "framework": "SpringBoot", "port": 8080, "team": "支付组"}),
    ("order-service", {"language": "Java", "framework": "SpringBoot", "port": 8081, "team": "订单组"}),
    ("user-service", {"language": "Go", "framework": "Gin", "port": 8082, "team": "用户组"}),
    ("gateway", {"language": "Java", "framework": "SpringCloudGateway", "port": 80, "team": "架构组"}),
    ("auth-service", {"language": "Java", "framework": "SpringBoot", "port": 8083, "team": "安全组"}),
]:
    svc = post("/entities", {
        "type_name": "Service",
        "name": name,
        "attributes": attrs,
        "labels": {"env": "prod", "team": attrs.get("team", ""), "business_line": "支付" if "payment" in name or "order" in name else "用户"},
        "biz_service": "在线支付" if name in ["payment-service", "order-service", "gateway"] else "用户注册",
        "source": "manual"
    })
    if svc:
        svcs[name] = svc["guid"]

# ============================================================
# 数据库 / 缓存
# ============================================================
print("\n🗄️  创建数据库/缓存...")
dbs = {}
for name, t, attrs in [
    ("payment-db", "MySQL", {"db_type": "MySQL", "port": 3306, "db_version": "8.0", "max_connections": 500}),
    ("order-db", "MySQL", {"db_type": "MySQL", "port": 3306, "db_version": "8.0", "max_connections": 500}),
    ("user-cache", "Redis", {"db_type": "Redis", "port": 6379, "redis_version": "7.0"}),
    ("session-cache", "Redis", {"db_type": "Redis", "port": 6379, "redis_version": "7.0"}),
]:
    db = post("/entities", {
        "type_name": t,
        "name": name,
        "attributes": attrs,
        "labels": {"env": "prod", "team": "DBA"},
        "biz_service": "在线支付" if "payment" in name or "order" in name else "用户注册",
        "source": "manual"
    })
    if db:
        dbs[name] = db["guid"]

# ============================================================
# 网络设备
# ============================================================
print("\n🌐 创建网络设备...")
net = post("/entities", {
    "type_name": "NetworkDevice",
    "name": "核心交换机-01",
    "attributes": {"vendor": "Cisco", "model": "C9300", "mgmt_ip": "10.0.0.1", "port_count": 48},
    "labels": {"env": "prod", "region": "cn-east-1"},
    "source": "manual"
})

# ============================================================
# 关系
# ============================================================
print("\n🔗 创建关系...")
rels = [
    # 业务包含服务
    (biz, svcs.get("payment-service"), "includes"),
    (biz, svcs.get("order-service"), "includes"),
    (biz, svcs.get("gateway"), "includes"),
    # 服务调用
    (svcs.get("gateway"), svcs.get("payment-service"), "calls"),
    (svcs.get("gateway"), svcs.get("order-service"), "calls"),
    (svcs.get("gateway"), svcs.get("user-service"), "calls"),
    (svcs.get("gateway"), svcs.get("auth-service"), "calls"),
    (svcs.get("payment-service"), svcs.get("order-service"), "calls"),
    # 服务依赖数据库
    (svcs.get("payment-service"), dbs.get("payment-db"), "depends_on"),
    (svcs.get("payment-service"), dbs.get("user-cache"), "depends_on"),
    (svcs.get("order-service"), dbs.get("order-db"), "depends_on"),
    (svcs.get("user-service"), dbs.get("user-cache"), "depends_on"),
    (svcs.get("auth-service"), dbs.get("session-cache"), "depends_on"),
    # 服务运行在主机
    (svcs.get("gateway"), hosts.get("web-01"), "runs_on"),
    (svcs.get("gateway"), hosts.get("web-02"), "runs_on"),
    (svcs.get("payment-service"), hosts.get("app-01"), "runs_on"),
    (svcs.get("order-service"), hosts.get("app-01"), "runs_on"),
    (svcs.get("user-service"), hosts.get("app-02"), "runs_on"),
    (svcs.get("auth-service"), hosts.get("app-02"), "runs_on"),
    # 数据库运行在主机
    (dbs.get("payment-db"), hosts.get("db-master"), "runs_on"),
    (dbs.get("order-db"), hosts.get("db-master"), "runs_on"),
    (dbs.get("user-cache"), hosts.get("redis-01"), "runs_on"),
    (dbs.get("session-cache"), hosts.get("redis-01"), "runs_on"),
    # 主机连接网络设备
    (hosts.get("web-01"), net["guid"] if net else None, "connected_to"),
    (hosts.get("web-02"), net["guid"] if net else None, "connected_to"),
]

for e1, e2, rel_type in rels:
    if e1 and e2:
        post(f"/entities/{e1}/relations", {
            "type_name": rel_type,
            "end2_guid": e2,
            "source": "manual"
        })

# ============================================================
# 设置健康度（模拟部分异常）
# ============================================================
print("\n💚 设置健康度...")
import requests as req
health_data = {
    "payment-service": {"health_score": 72, "health_level": "warning", "risk_score": 78},
    "order-service": {"health_score": 95, "health_level": "healthy", "risk_score": 30},
    "user-service": {"health_score": 88, "health_level": "healthy", "risk_score": 20},
    "gateway": {"health_score": 99, "health_level": "healthy", "risk_score": 10},
    "auth-service": {"health_score": 92, "health_level": "healthy", "risk_score": 15},
    "payment-db": {"health_score": 55, "health_level": "critical", "risk_score": 85},
    "order-db": {"health_score": 90, "health_level": "healthy", "risk_score": 25},
    "user-cache": {"health_score": 98, "health_level": "healthy", "risk_score": 5},
    "session-cache": {"health_score": 96, "health_level": "healthy", "risk_score": 8},
    "db-master": {"health_score": 60, "health_level": "warning", "risk_score": 70},
}

for name, guid in {**svcs, **dbs, **hosts}.items():
    if name in health_data:
        hd = health_data[name]
        r = req.put(f"{BASE}/entities/{guid}", json=hd)
        print(f"  {name}: health={hd['health_score']} risk={hd['risk_score']} → {r.status_code}")

# 特别处理 db-master
for name, guid in hosts.items():
    if name == "db-master" and name in health_data:
        hd = health_data[name]
        r = req.put(f"{BASE}/entities/{guid}", json=hd)
        print(f"  {name}: health={hd['health_score']} risk={hd['risk_score']} → {r.status_code}")

print("\n✅ 演示数据加载完成！")
print(f"   共创建: {len(svcs)} 服务 + {len(hosts)} 主机 + {len(dbs)} 数据库/缓存 + 1 网络设备 + 2 业务")
