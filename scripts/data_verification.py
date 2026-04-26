"""
方向 D：数据验证
用数据工厂生成 Prometheus 格式数据 → Smart ETL → 入库 → 前端展示验证
"""
import asyncio
import asyncpg
import json
import time
import random
import math
from datetime import datetime


DB_URL = "postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb"


# ══════════════════════════════════════════════════════════════
# 真实场景数据生成
# ══════════════════════════════════════════════════════════════

SCENARIOS = {
    "电商微服务": {
        "hosts": [
            {"name": "web-gateway-01", "instance": "10.0.1.10:9100", "job": "node-exporter", "dc": "beijing", "env": "production"},
            {"name": "api-server-01", "instance": "10.0.1.20:9100", "job": "node-exporter", "dc": "beijing", "env": "production"},
            {"name": "api-server-02", "instance": "10.0.1.21:9100", "job": "node-exporter", "dc": "beijing", "env": "production"},
            {"name": "db-master-01", "instance": "10.0.2.10:9100", "job": "node-exporter", "dc": "beijing", "env": "production"},
            {"name": "db-slave-01", "instance": "10.0.2.11:9100", "job": "node-exporter", "dc": "shanghai", "env": "production"},
            {"name": "redis-cluster-01", "instance": "10.0.3.10:9100", "job": "node-exporter", "dc": "beijing", "env": "production"},
        ],
        "services": [
            {"name": "order-service", "instance": "10.0.1.20:8080", "job": "prometheus", "team": "order"},
            {"name": "user-service", "instance": "10.0.1.20:8081", "job": "prometheus", "team": "user"},
            {"name": "payment-service", "instance": "10.0.1.21:8080", "job": "prometheus", "team": "payment"},
            {"name": "inventory-service", "instance": "10.0.1.21:8081", "job": "prometheus", "team": "inventory"},
            {"name": "notification-service", "instance": "10.0.1.21:8082", "job": "prometheus", "team": "notification"},
        ],
        "databases": [
            {"name": "mysql-order-db", "instance": "10.0.2.10:3306", "job": "mysqld-exporter"},
            {"name": "mysql-user-db", "instance": "10.0.2.10:3307", "job": "mysqld-exporter"},
            {"name": "redis-cache", "instance": "10.0.3.10:6379", "job": "redis-exporter"},
        ],
    },
}


def gen_host_metrics(host):
    """生成主机指标"""
    ts = time.time()
    cpu = 45 + 25 * math.sin(ts / 60 + hash(host["name"]) % 10) + random.gauss(0, 5)
    mem = 55 + 15 * math.sin(ts / 300 + hash(host["name"]) % 5) + random.gauss(0, 2)
    load = cpu / 20 + random.gauss(0, 0.3)
    disk = 40 + 10 * math.sin(ts / 3600) + random.gauss(0, 1)
    
    lines = [
        f'# HELP node_cpu_seconds_total Total CPU time spent in seconds',
        f'# TYPE node_cpu_seconds_total counter',
        f'node_cpu_seconds_total{{cpu="0",mode="idle",instance="{host["instance"]}",job="{host["job"]}",dc="{host.get("dc","unknown")}",env="{host.get("env","unknown")}"}} {random.uniform(80000, 180000):.2f}',
        f'node_cpu_seconds_total{{cpu="0",mode="user",instance="{host["instance"]}",job="{host["job"]}",dc="{host.get("dc","unknown")}",env="{host.get("env","unknown")}"}} {random.uniform(5000, 20000):.2f}',
        f'node_cpu_seconds_total{{cpu="0",mode="system",instance="{host["instance"]}",job="{host["job"]}",dc="{host.get("dc","unknown")}",env="{host.get("env","unknown")}"}} {random.uniform(2000, 8000):.2f}',
        f'# HELP node_memory_MemTotal_bytes Total memory in bytes',
        f'# TYPE node_memory_MemTotal_bytes gauge',
        f'node_memory_MemTotal_bytes{{instance="{host["instance"]}",job="{host["job"]}",dc="{host.get("dc","unknown")}",env="{host.get("env","unknown")}"}} 17179869184',
        f'# HELP node_memory_MemAvailable_bytes Available memory in bytes',
        f'# TYPE node_memory_MemAvailable_bytes gauge',
        f'node_memory_MemAvailable_bytes{{instance="{host["instance"]}",job="{host["job"]}",dc="{host.get("dc","unknown")}",env="{host.get("env","unknown")}"}} {17179869184 * (1 - mem/100):.0f}',
        f'# HELP node_load1 1-minute load average',
        f'# TYPE node_load1 gauge',
        f'node_load1{{instance="{host["instance"]}",job="{host["job"]}",dc="{host.get("dc","unknown")}",env="{host.get("env","unknown")}"}} {load:.2f}',
        f'# HELP node_filesystem_avail_bytes Filesystem available space',
        f'# TYPE node_filesystem_avail_bytes gauge',
        f'node_filesystem_avail_bytes{{instance="{host["instance"]}",job="{host["job"]}",mountpoint="/",dc="{host.get("dc","unknown")}",env="{host.get("env","unknown")}"}} {500000000000 * (1 - disk/100):.0f}',
    ]
    return '\n'.join(lines)


def gen_service_metrics(svc):
    """生成服务指标"""
    ts = time.time()
    qps = 800 + 400 * math.sin(ts / 120 + hash(svc["name"]) % 10) + random.gauss(0, 80)
    latency_p99 = 80 + 50 * math.sin(ts / 60) + random.gauss(0, 15)
    latency_p50 = 30 + 20 * math.sin(ts / 60) + random.gauss(0, 5)
    error_rate = 0.3 + 0.2 * math.sin(ts / 180) + random.gauss(0, 0.1)
    
    lines = [
        f'# HELP http_requests_total Total HTTP requests',
        f'# TYPE http_requests_total counter',
        f'http_requests_total{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",method="GET",status="200",team="{svc.get("team","unknown")}"}} {random.uniform(50000, 200000):.0f}',
        f'http_requests_total{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",method="GET",status="500",team="{svc.get("team","unknown")}"}} {random.uniform(100, 1000):.0f}',
        f'http_requests_total{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",method="POST",status="200",team="{svc.get("team","unknown")}"}} {random.uniform(20000, 80000):.0f}',
        f'http_requests_total{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",method="POST",status="500",team="{svc.get("team","unknown")}"}} {random.uniform(50, 500):.0f}',
        f'# HELP http_request_duration_seconds HTTP request duration',
        f'# TYPE http_request_duration_seconds histogram',
        f'http_request_duration_seconds_bucket{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",le="0.1"}} {random.uniform(700, 1000):.0f}',
        f'http_request_duration_seconds_bucket{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",le="0.5"}} {random.uniform(850, 1100):.0f}',
        f'http_request_duration_seconds_bucket{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",le="1.0"}} {random.uniform(950, 1200):.0f}',
        f'http_request_duration_seconds_bucket{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",le="+Inf"}} {random.uniform(1000, 1300):.0f}',
        f'# HELP http_requests_qps Current QPS',
        f'# TYPE http_requests_qps gauge',
        f'http_requests_qps{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",team="{svc.get("team","unknown")}"}} {qps:.2f}',
        f'# HELP http_request_duration_p99_seconds P99 latency',
        f'# TYPE http_request_duration_p99_seconds gauge',
        f'http_request_duration_p99_seconds{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}"}} {latency_p99:.2f}',
        f'# HELP http_request_duration_p50_seconds P50 latency',
        f'# TYPE http_request_duration_p50_seconds gauge',
        f'http_request_duration_p50_seconds{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}"}} {latency_p50:.2f}',
        f'# HELP http_request_error_rate Error rate',
        f'# TYPE http_request_error_rate gauge',
        f'http_request_error_rate{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}"}} {error_rate:.4f}',
    ]
    return '\n'.join(lines)


def gen_database_metrics(db):
    """生成数据库指标"""
    connections = random.randint(20, 80)
    max_connections = 200
    slow_queries = random.randint(0, 20)
    qps = random.randint(100, 500)
    
    lines = [
        f'# HELP mysql_global_status_threads_connected Connected threads',
        f'# TYPE mysql_global_status_threads_connected gauge',
        f'mysql_global_status_threads_connected{{instance="{db["instance"]}",job="{db["job"]}"}} {connections}',
        f'# HELP mysql_global_status_threads_running Running threads',
        f'# TYPE mysql_global_status_threads_running gauge',
        f'mysql_global_status_threads_running{{instance="{db["instance"]}",job="{db["job"]}"}} {random.randint(5, 20)}',
        f'# HELP mysql_global_status_slow_queries Slow queries',
        f'# TYPE mysql_global_status_slow_queries counter',
        f'mysql_global_status_slow_queries{{instance="{db["instance"]}",job="{db["job"]}"}} {slow_queries}',
        f'# HELP mysql_global_status_queries_total Total queries',
        f'# TYPE mysql_global_status_queries_total counter',
        f'mysql_global_status_queries_total{{instance="{db["instance"]}",job="{db["job"]}"}} {random.uniform(100000, 500000):.0f}',
        f'# HELP mysql_global_status_questions Questions per second',
        f'# TYPE mysql_global_status_questions gauge',
        f'mysql_global_status_questions{{instance="{db["instance"]}",job="{db["job"]}"}} {qps}',
    ]
    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════
# ETL 处理引擎
# ══════════════════════════════════════════════════════════════

import re

PREFIX_MAP = {
    "node_": "Host", "host_": "Host", "container_": "Container",
    "kube_pod_": "K8sPod", "kube_node_": "K8sNode",
    "http_": "Service", "redis_": "Redis", "mysql_": "Database",
}

LABEL_MAP = {"instance": "Host", "pod": "K8sPod", "service": "Service", "job": "Service"}


def parse_prometheus(data):
    metrics = []
    for line in data.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            match = re.match(r'^([^{]+)\{([^}]*)\}\s+([\d.e+-]+)', line)
            if match:
                name = match.group(1).strip()
                labels = {}
                for label in match.group(2).split(','):
                    if '=' in label:
                        k, v = label.split('=', 1)
                        labels[k.strip()] = v.strip().strip('"')
                metrics.append({"name": name, "value": float(match.group(3)), "labels": labels})
    return metrics


def infer_entity(metric_name, labels):
    for prefix, etype in PREFIX_MAP.items():
        if metric_name.startswith(prefix):
            return etype
    for lkey, etype in LABEL_MAP.items():
        if lkey in labels:
            return etype
    return None


def infer_entity_name(etype, labels):
    if etype == "Host":
        return labels.get("instance", "unknown").split(":")[0]
    elif etype == "Service":
        return labels.get("service", labels.get("job", "unknown"))
    elif etype == "Database":
        return labels.get("instance", "unknown").split(":")[0]
    return "unknown"


async def fuzzy_match(conn, metric_name):
    keywords = {
        "cpu": "host.cpu.usage", "memory": "host.memory.usage",
        "load": "host.cpu.load.1m", "qps": "service.http.request.qps",
        "request": "service.http.request.qps", "duration": "service.http.request.duration.p99",
        "error": "service.http.request.error_rate", "threads": "db.connection.active",
        "slow": "db.slow_query.count", "filesystem": "host.disk.usage",
    }
    for keyword, metric_id in keywords.items():
        if keyword in metric_name.lower():
            exists = await conn.fetchval("SELECT COUNT(*) FROM metric_def WHERE metric_id = $1", metric_id)
            if exists:
                return metric_id
    return None


# ══════════════════════════════════════════════════════════════
# 数据验证主流程
# ══════════════════════════════════════════════════════════════

async def run_data_verification():
    """数据验证"""
    conn = await asyncpg.connect(DB_URL)
    
    print("=" * 70)
    print("  数据验证：真实场景数据 → Smart ETL → 入库 → 验证")
    print("=" * 70)
    print()
    
    scenario = SCENARIOS["电商微服务"]
    
    # 统计
    stats = {
        "hosts": 0, "services": 0, "databases": 0,
        "metrics_total": 0, "metrics_mapped": 0,
        "entities_created": 0, "entities_updated": 0,
    }
    
    # ══════════════════════════════════════════════════════════════
    # Step 1: 生成主机数据
    # ══════════════════════════════════════════════════════════════
    print("Step 1: 生成主机数据...")
    for host in scenario["hosts"]:
        data = gen_host_metrics(host)
        metrics = parse_prometheus(data)
        
        # 注册实体
        qname = f"Host:{host['name']}"
        result = await conn.execute(
            """INSERT INTO entity (type_name, name, qualified_name, labels, source, status)
               VALUES ('Host', $1, $2, $3, 'auto_discovered', 'active')
               ON CONFLICT (qualified_name) DO UPDATE SET labels=$3, updated_at=NOW()""",
            host['name'], qname, json.dumps({"instance": host["instance"], "job": host["job"], "dc": host.get("dc", ""), "env": host.get("env", "")})
        )
        if result == "INSERT 0 1":
            stats["entities_created"] += 1
        else:
            stats["entities_updated"] += 1
        
        # 处理指标
        for m in metrics:
            stats["metrics_total"] += 1
            target = await fuzzy_match(conn, m["name"])
            if target:
                stats["metrics_mapped"] += 1
        
        stats["hosts"] += 1
        print(f"  ✅ {host['name']} ({host['instance']}) — {len(metrics)} 指标")
    
    print()
    
    # ══════════════════════════════════════════════════════════════
    # Step 2: 生成服务数据
    # ══════════════════════════════════════════════════════════════
    print("Step 2: 生成服务数据...")
    for svc in scenario["services"]:
        data = gen_service_metrics(svc)
        metrics = parse_prometheus(data)
        
        qname = f"Service:{svc['name']}"
        result = await conn.execute(
            """INSERT INTO entity (type_name, name, qualified_name, labels, source, status)
               VALUES ('Service', $1, $2, $3, 'auto_discovered', 'active')
               ON CONFLICT (qualified_name) DO UPDATE SET labels=$3, updated_at=NOW()""",
            svc['name'], qname, json.dumps({"instance": svc["instance"], "job": svc["job"], "team": svc.get("team", "")})
        )
        if result == "INSERT 0 1":
            stats["entities_created"] += 1
        else:
            stats["entities_updated"] += 1
        
        for m in metrics:
            stats["metrics_total"] += 1
            target = await fuzzy_match(conn, m["name"])
            if target:
                stats["metrics_mapped"] += 1
        
        stats["services"] += 1
        print(f"  ✅ {svc['name']} ({svc['instance']}) — {len(metrics)} 指标")
    
    print()
    
    # ══════════════════════════════════════════════════════════════
    # Step 3: 生成数据库数据
    # ══════════════════════════════════════════════════════════════
    print("Step 3: 生成数据库数据...")
    for db in scenario["databases"]:
        data = gen_database_metrics(db)
        metrics = parse_prometheus(data)
        
        qname = f"Database:{db['name']}"
        result = await conn.execute(
            """INSERT INTO entity (type_name, name, qualified_name, labels, source, status)
               VALUES ('Database', $1, $2, $3, 'auto_discovered', 'active')
               ON CONFLICT (qualified_name) DO UPDATE SET labels=$3, updated_at=NOW()""",
            db['name'], qname, json.dumps({"instance": db["instance"], "job": db["job"]})
        )
        if result == "INSERT 0 1":
            stats["entities_created"] += 1
        else:
            stats["entities_updated"] += 1
        
        for m in metrics:
            stats["metrics_total"] += 1
            target = await fuzzy_match(conn, m["name"])
            if target:
                stats["metrics_mapped"] += 1
        
        stats["databases"] += 1
        print(f"  ✅ {db['name']} ({db['instance']}) — {len(metrics)} 指标")
    
    print()
    
    # ══════════════════════════════════════════════════════════════
    # Step 4: 验证结果
    # ══════════════════════════════════════════════════════════════
    print("Step 4: 验证结果...")
    
    # 实体统计
    total_entities = await conn.fetchval("SELECT COUNT(*) FROM entity")
    auto_entities = await conn.fetchval("SELECT COUNT(*) FROM entity WHERE source = 'auto_discovered'")
    
    # 实体类型分布
    type_dist = await conn.fetch(
        "SELECT type_name, COUNT(*) as cnt FROM entity WHERE source = 'auto_discovered' GROUP BY type_name ORDER BY cnt DESC"
    )
    
    # 标签统计
    label_stats = await conn.fetch(
        """SELECT 
            labels->>'dc' as dc,
            labels->>'env' as env,
            labels->>'team' as team,
            COUNT(*) as cnt
           FROM entity 
           WHERE source = 'auto_discovered' AND labels->>'dc' IS NOT NULL
           GROUP BY labels->>'dc', labels->>'env', labels->>'team'
           ORDER BY cnt DESC"""
    )
    
    print(f"  数据库实体总数: {total_entities}")
    print(f"  自动发现实体: {auto_entities}")
    print(f"  处理指标总数: {stats['metrics_total']}")
    print(f"  指标映射成功: {stats['metrics_mapped']}")
    print()
    
    print("  实体分布:")
    for r in type_dist:
        print(f"    {r['type_name']:20s} {r['cnt']:3d}")
    
    print()
    print("  标签分布:")
    for r in label_stats:
        print(f"    DC:{r['dc'] or 'N/A':10s} ENV:{r['env'] or 'N/A':12s} TEAM:{r['team'] or 'N/A':12s} {r['cnt']:3d}")
    
    print()
    print("=" * 70)
    print("  数据验证完成！")
    print("=" * 70)
    print()
    print("  统计摘要:")
    print(f"    主机: {stats['hosts']}")
    print(f"    服务: {stats['services']}")
    print(f"    数据库: {stats['databases']}")
    print(f"    指标总数: {stats['metrics_total']}")
    print(f"    指标映射: {stats['metrics_mapped']}")
    print(f"    实体创建: {stats['entities_created']}")
    print(f"    实体更新: {stats['entities_updated']}")
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(run_data_verification())
