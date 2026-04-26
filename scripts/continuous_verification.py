"""
持续验证：模拟真实运维场景
持续造数据 + 实体发现 + 指标入库 + 状态监控
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
# 持续数据生成 + 处理
# ══════════════════════════════════════════════════════════════

# 预定义的实体清单（模拟真实环境）
HOSTS = [
    {"name": "web-server-01", "instance": "10.0.0.1:9100", "job": "node-exporter"},
    {"name": "web-server-02", "instance": "10.0.0.2:9100", "job": "node-exporter"},
    {"name": "db-server-01", "instance": "10.0.0.3:9100", "job": "node-exporter"},
    {"name": "redis-server-01", "instance": "10.0.0.4:9100", "job": "node-exporter"},
]

SERVICES = [
    {"name": "api-gateway", "instance": "10.0.0.1:8080", "job": "prometheus"},
    {"name": "user-service", "instance": "10.0.0.2:8081", "job": "prometheus"},
    {"name": "order-service", "instance": "10.0.0.3:8082", "job": "prometheus"},
    {"name": "payment-service", "instance": "10.0.0.4:8083", "job": "prometheus"},
]


def gen_host_prom(host):
    ts = time.time()
    cpu = 50 + 20 * math.sin(ts / 60 + hash(host["name"]) % 10) + random.gauss(0, 4)
    mem = 60 + 10 * math.sin(ts / 300 + hash(host["name"]) % 5) + random.gauss(0, 1)
    load = cpu / 25 + random.gauss(0, 0.2)
    
    return f"""# HELP node_cpu_seconds_total Total CPU time
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{{cpu="0",mode="idle",instance="{host["instance"]}",job="{host["job"]}"}} {random.uniform(100000, 200000):.2f}
node_cpu_seconds_total{{cpu="0",mode="user",instance="{host["instance"]}",job="{host["job"]}"}} {random.uniform(5000, 15000):.2f}
# HELP node_memory_MemTotal_bytes Total memory
# TYPE node_memory_MemTotal_bytes gauge
node_memory_MemTotal_bytes{{instance="{host["instance"]}",job="{host["job"]}"}} 8589934592
# HELP node_load1 1-minute load
# TYPE node_load1 gauge
node_load1{{instance="{host["instance"]}",job="{host["job"]}"}} {load:.2f}"""


def gen_service_prom(svc):
    ts = time.time()
    qps = 1000 + 300 * math.sin(ts / 120 + hash(svc["name"]) % 10) + random.gauss(0, 60)
    latency = 50 + 30 * math.sin(ts / 60) + random.gauss(0, 10)
    
    return f"""# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",method="GET",status="200"}} {random.uniform(10000, 50000):.0f}
http_requests_total{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}",method="GET",status="500"}} {random.uniform(10, 100):.0f}
# HELP http_requests_qps Current QPS
# TYPE http_requests_qps gauge
http_requests_qps{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}"}} {qps:.2f}
# HELP http_request_duration_seconds Request duration
# TYPE http_request_duration_seconds gauge
http_request_duration_seconds{{service="{svc["name"]}",instance="{svc["instance"]}",job="{svc["job"]}"}} {latency:.2f}"""


def gen_json_log():
    level = random.choices(["info", "warn", "error"], weights=[80, 15, 5])[0]
    svc = random.choice(SERVICES)["name"]
    return json.dumps({
        "timestamp": datetime.now().isoformat() + "Z",
        "level": level,
        "service": svc,
        "message": f"Request processed ({level})",
        "duration_ms": random.randint(1, 5000),
    })


# ══════════════════════════════════════════════════════════════
# ETL 处理
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
    return "unknown"


async def fuzzy_match(conn, metric_name):
    keywords = {
        "cpu": "host.cpu.usage", "memory": "host.memory.usage",
        "load": "host.cpu.load.1m", "qps": "service.http.request.qps",
        "request": "service.http.request.qps", "duration": "service.http.request.duration.p99",
    }
    for keyword, metric_id in keywords.items():
        if keyword in metric_name.lower():
            exists = await conn.fetchval("SELECT COUNT(*) FROM metric_def WHERE metric_id = $1", metric_id)
            if exists:
                return metric_id
    return None


# ══════════════════════════════════════════════════════════════
# 持续验证主循环
# ══════════════════════════════════════════════════════════════

async def run_continuous_verification(duration_seconds: int = 60, interval: int = 10):
    """持续验证"""
    conn = await asyncpg.connect(DB_URL)
    
    print("=" * 70)
    print("  持续验证：模拟真实运维场景")
    print(f"  时长: {duration_seconds}秒 | 间隔: {interval}秒")
    print("=" * 70)
    print()
    
    start_time = time.time()
    round_num = 0
    total_entities = 0
    total_metrics = 0
    
    while time.time() - start_time < duration_seconds:
        round_num += 1
        elapsed = int(time.time() - start_time)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"[{timestamp}] 第{round_num}轮 (已运行{elapsed}秒)")
        
        # 生成数据
        data_batch = []
        
        # 主机指标
        for host in HOSTS:
            data_batch.append(gen_host_prom(host))
        
        # 服务指标
        for svc in SERVICES:
            data_batch.append(gen_service_prom(svc))
        
        # JSON 日志
        for _ in range(3):
            data_batch.append(gen_json_log())
        
        # 处理数据
        round_entities = 0
        round_metrics = 0
        
        for data in data_batch:
            # 解析 Prometheus
            if data.startswith('#') or '{' in data:
                metrics = parse_prometheus(data)
                for m in metrics:
                    etype = infer_entity(m["name"], m["labels"])
                    ename = infer_entity_name(etype, m["labels"]) if etype else None
                    
                    if etype and ename and ename != "unknown":
                        # 实体注册
                        qname = f"{etype}:{ename}"
                        result = await conn.execute(
                            """INSERT INTO entity (type_name, name, qualified_name, labels, source, status)
                               VALUES ($1, $2, $3, $4, 'auto_discovered', 'active')
                               ON CONFLICT (qualified_name) DO UPDATE SET updated_at = NOW()""",
                            etype, ename, qname, json.dumps(m["labels"])
                        )
                        if result == "INSERT 0 1":
                            round_entities += 1
                        
                        # 指标映射
                        target = await fuzzy_match(conn, m["name"])
                        if target:
                            round_metrics += 1
                            total_metrics += 1
            
            # 解析 JSON 日志
            elif data.startswith('{'):
                try:
                    record = json.loads(data)
                    svc_name = record.get("service", "unknown")
                    qname = f"Service:{svc_name}"
                    await conn.execute(
                        """INSERT INTO entity (type_name, name, qualified_name, labels, source, status)
                           VALUES ('Service', $1, $2, $3, 'auto_discovered', 'active')
                           ON CONFLICT (qualified_name) DO UPDATE SET updated_at = NOW()""",
                        svc_name, qname, json.dumps({"service": svc_name})
                    )
                    round_metrics += 1
                    total_metrics += 1
                except:
                    pass
        
        total_entities += round_entities
        print(f"  新实体: {round_entities} | 指标: {round_metrics} | 累计实体: {total_entities} | 累计指标: {total_metrics}")
        
        await asyncio.sleep(interval)
    
    # 最终统计
    print()
    print("=" * 70)
    print("  持续验证完成！")
    print("=" * 70)
    
    entity_count = await conn.fetchval("SELECT COUNT(*) FROM entity WHERE source = 'auto_discovered'")
    total_db_entities = await conn.fetchval("SELECT COUNT(*) FROM entity")
    
    type_dist = await conn.fetch(
        "SELECT type_name, COUNT(*) as cnt FROM entity WHERE source = 'auto_discovered' GROUP BY type_name ORDER BY cnt DESC"
    )
    
    print(f"  总轮次: {round_num}")
    print(f"  数据库实体总数: {total_db_entities}")
    print(f"  自动发现实体: {entity_count}")
    print(f"  累计处理指标: {total_metrics}")
    print()
    print("  实体分布:")
    for r in type_dist:
        print(f"    {r['type_name']:20s} {r['cnt']:3d}")
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(run_continuous_verification(duration_seconds=60, interval=10))
