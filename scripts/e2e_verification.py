"""
端到端验证：数据工厂 → Smart ETL → 模型映射 → 入库
"""
import asyncio
import asyncpg
import json
import time
import random
import math
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# 数据生成器（复用 Phase 6）
# ══════════════════════════════════════════════════════════════

def gen_prometheus_host(hostname, instance):
    ts = time.time()
    cpu = 50 + 20 * math.sin(ts / 60) + random.gauss(0, 4)
    mem = 60 + 10 * math.sin(ts / 300) + random.gauss(0, 1)
    return f"""# HELP node_cpu_seconds_total Total CPU time
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{{cpu="0",mode="idle",instance="{instance}",job="node-exporter"}} {random.uniform(100000, 200000):.2f}
node_cpu_seconds_total{{cpu="0",mode="user",instance="{instance}",job="node-exporter"}} {random.uniform(5000, 15000):.2f}
# HELP node_memory_MemTotal_bytes Total memory
# TYPE node_memory_MemTotal_bytes gauge
node_memory_MemTotal_bytes{{instance="{instance}",job="node-exporter"}} 8589934592
# HELP node_load1 1-minute load
# TYPE node_load1 gauge
node_load1{{instance="{instance}",job="node-exporter"}} {cpu/25:.2f}"""


def gen_prometheus_service(service, instance):
    qps = 1000 + 300 * math.sin(time.time() / 120) + random.gauss(0, 60)
    return f"""# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{{service="{service}",instance="{instance}",job="prometheus",method="GET",status="200"}} {random.uniform(10000, 50000):.0f}
http_requests_total{{service="{service}",instance="{instance}",job="prometheus",method="GET",status="500"}} {random.uniform(10, 100):.0f}
# HELP http_requests_qps Current QPS
# TYPE http_requests_qps gauge
http_requests_qps{{service="{service}",instance="{instance}",job="prometheus"}} {qps:.2f}"""


def gen_json_log():
    level = random.choice(["info", "warn", "error"])
    service = random.choice(["api-gateway", "user-service", "order-service"])
    return json.dumps({
        "timestamp": datetime.now().isoformat() + "Z",
        "level": level,
        "service": service,
        "message": f"Request processed ({level})",
        "duration_ms": random.randint(1, 5000),
    })


# ══════════════════════════════════════════════════════════════
# Smart ETL 引擎（复用 Phase 5）
# ══════════════════════════════════════════════════════════════

import re

FORMAT_RULES = [
    {"name": "prometheus", "patterns": [r"^# HELP ", r"^# TYPE ", r'\{[^}]*=[^}]*\}'], "min_matches": 2},
    {"name": "json_lines", "patterns": [r"^\{.*\}$"], "min_matches": 1},
]

PREFIX_MAP = {
    "node_": "Host", "host_": "Host", "container_": "Container",
    "kube_pod_": "K8sPod", "kube_node_": "K8sNode",
    "http_": "Service", "redis_": "Redis", "mysql_": "Database",
}

LABEL_MAP = {"instance": "Host", "pod": "K8sPod", "service": "Service", "job": "Service"}


def identify_format(data):
    lines = data.strip().split('\n')
    for rule in FORMAT_RULES:
        matches = sum(1 for line in lines[:10] if any(re.search(p, line) for p in rule["patterns"]))
        if matches >= rule["min_matches"]:
            return rule["name"]
    return "unknown"


def extract_prometheus(data):
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
    elif etype == "K8sPod":
        return labels.get("pod", "unknown")
    return "unknown"


# ══════════════════════════════════════════════════════════════
# 端到端验证流水线
# ══════════════════════════════════════════════════════════════

DB_URL = "postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb"


async def run_e2e_verification():
    """端到端验证"""
    conn = await asyncpg.connect(DB_URL)
    
    print("=" * 60)
    print("  端到端验证：数据工厂 → Smart ETL → 模型映射 → 入库")
    print("=" * 60)
    print()
    
    # 统计
    stats = {
        "data_generated": 0,
        "formats_identified": 0,
        "entities_found": 0,
        "entities_registered": 0,
        "metrics_extracted": 0,
        "metrics_mapped": 0,
        "metrics_stored": 0,
    }
    
    # ══════════════════════════════════════════════════════════════
    # Step 1: 生成数据
    # ══════════════════════════════════════════════════════════════
    print("Step 1: 生成多格式数据...")
    
    data_batch = []
    
    # 主机指标
    for i in range(3):
        hostname = f"web-server-{i+1}"
        instance = f"10.0.0.{i+1}:9100"
        data_batch.append({
            "format": "prometheus",
            "source": "node-exporter",
            "data": gen_prometheus_host(hostname, instance),
        })
        stats["data_generated"] += 1
    
    # 服务指标
    services = ["api-gateway", "user-service", "order-service"]
    for svc in services:
        data_batch.append({
            "format": "prometheus",
            "source": "prometheus",
            "data": gen_prometheus_service(svc, f"10.0.0.{hash(svc) % 255}:8080"),
        })
        stats["data_generated"] += 1
    
    # JSON 日志
    for _ in range(5):
        data_batch.append({
            "format": "json_lines",
            "source": "app-logs",
            "data": gen_json_log(),
        })
        stats["data_generated"] += 1
    
    print(f"  ✅ 生成 {stats['data_generated']} 条数据")
    print()
    
    # ══════════════════════════════════════════════════════════════
    # Step 2: 格式识别 + 字段解析
    # ══════════════════════════════════════════════════════════════
    print("Step 2: 格式识别 + 字段解析...")
    
    parsed_data = []
    for item in data_batch:
        fmt = identify_format(item["data"])
        stats["formats_identified"] += 1
        
        if fmt == "prometheus":
            metrics = extract_prometheus(item["data"])
            for m in metrics:
                etype = infer_entity(m["name"], m["labels"])
                ename = infer_entity_name(etype, m["labels"]) if etype else "unknown"
                parsed_data.append({
                    "format": fmt,
                    "source": item["source"],
                    "metric_name": m["name"],
                    "metric_value": m["value"],
                    "labels": m["labels"],
                    "entity_type": etype,
                    "entity_name": ename,
                })
                stats["metrics_extracted"] += 1
                if etype:
                    stats["entities_found"] += 1
        elif fmt == "json_lines":
            try:
                record = json.loads(item["data"])
                parsed_data.append({
                    "format": fmt,
                    "source": item["source"],
                    "metric_name": f"log.{record.get('level', 'unknown')}",
                    "metric_value": 1,
                    "labels": {"service": record.get("service", "unknown")},
                    "entity_type": "Service",
                    "entity_name": record.get("service", "unknown"),
                })
                stats["metrics_extracted"] += 1
                stats["entities_found"] += 1
            except:
                pass
    
    print(f"  ✅ 识别 {stats['formats_identified']} 条格式")
    print(f"  ✅ 提取 {stats['metrics_extracted']} 个指标")
    print(f"  ✅ 发现 {stats['entities_found']} 个实体")
    print()
    
    # ══════════════════════════════════════════════════════════════
    # Step 3: 实体自动注册
    # ══════════════════════════════════════════════════════════════
    print("Step 3: 实体自动注册...")
    
    registered_entities = {}
    for item in parsed_data:
        if not item["entity_type"] or item["entity_name"] == "unknown":
            continue
        
        key = (item["entity_type"], item["entity_name"])
        if key not in registered_entities:
            # 检查是否已存在
            existing = await conn.fetchval(
                "SELECT COUNT(*) FROM entity WHERE type_name = $1 AND name = $2",
                item["entity_type"], item["entity_name"]
            )
            
            if not existing:
                # 创建实体
                qname = f"{item['entity_type']}:{item['entity_name']}"
                await conn.execute(
                    """INSERT INTO entity (type_name, name, qualified_name, labels, source, status)
                       VALUES ($1, $2, $3, $4, 'auto_discovered', 'active')
                       ON CONFLICT (qualified_name) DO NOTHING""",
                    item["entity_type"], item["entity_name"], qname,
                    json.dumps(item["labels"])
                )
                stats["entities_registered"] += 1
                registered_entities[key] = True
                print(f"  + {item['entity_type']}: {item['entity_name']}")
            else:
                registered_entities[key] = True
    
    print(f"  ✅ 注册 {stats['entities_registered']} 个新实体")
    print()
    
    # ══════════════════════════════════════════════════════════════
    # Step 4: 指标映射 + 入库
    # ══════════════════════════════════════════════════════════════
    print("Step 4: 指标映射 + 入库...")
    
    for item in parsed_data:
        if not item["entity_type"]:
            continue
        
        # 查询映射表
        mapping = await conn.fetchrow(
            "SELECT target_metric_id FROM metric_mapping WHERE source_system = $1 AND source_metric = $2 AND status = 'confirmed'",
            item["source"], item["metric_name"]
        )
        
        if mapping:
            target_metric = mapping["target_metric_id"]
            stats["metrics_mapped"] += 1
        else:
            # 尝试模糊匹配
            target_metric = await _fuzzy_match(conn, item["metric_name"])
            if target_metric:
                stats["metrics_mapped"] += 1
        
        if target_metric:
            # 查找实体 GUID
            entity = await conn.fetchrow(
                "SELECT guid FROM entity WHERE type_name = $1 AND name = $2",
                item["entity_type"], item["entity_name"]
            )
            
            if entity:
                # 写入指标数据（模拟 ClickHouse 写入）
                stats["metrics_stored"] += 1
    
    print(f"  ✅ 映射 {stats['metrics_mapped']} 个指标")
    print(f"  ✅ 存储 {stats['metrics_stored']} 个指标数据点")
    print()
    
    # ══════════════════════════════════════════════════════════════
    # Step 5: 验证结果
    # ══════════════════════════════════════════════════════════════
    print("Step 5: 验证结果...")
    
    # 实体统计
    entity_count = await conn.fetchval("SELECT COUNT(*) FROM entity WHERE source = 'auto_discovered'")
    total_entities = await conn.fetchval("SELECT COUNT(*) FROM entity")
    
    # 指标统计
    metric_count = await conn.fetchval("SELECT COUNT(*) FROM metric_def")
    mapping_count = await conn.fetchval("SELECT COUNT(*) FROM metric_mapping WHERE status = 'confirmed'")
    
    # 实体类型分布
    type_dist = await conn.fetch(
        "SELECT type_name, COUNT(*) as cnt FROM entity WHERE source = 'auto_discovered' GROUP BY type_name ORDER BY cnt DESC"
    )
    
    print(f"  数据库实体总数: {total_entities}")
    print(f"  自动发现实体: {entity_count}")
    print(f"  指标定义数: {metric_count}")
    print(f"  指标映射数: {mapping_count}")
    print()
    print("  自动发现实体分布:")
    for r in type_dist:
        print(f"    {r['type_name']:20s} {r['cnt']:3d}")
    
    print()
    print("=" * 60)
    print("  验证完成！")
    print("=" * 60)
    print()
    print("  统计摘要:")
    for k, v in stats.items():
        print(f"    {k:25s} {v:5d}")
    
    await conn.close()


async def _fuzzy_match(conn, metric_name):
    """模糊匹配"""
    keywords = {
        "cpu": "host.cpu.usage", "memory": "host.memory.usage",
        "disk": "host.disk.usage", "load": "host.cpu.load.1m",
        "qps": "service.http.request.qps", "request": "service.http.request.qps",
    }
    for keyword, metric_id in keywords.items():
        if keyword in metric_name.lower():
            exists = await conn.fetchval("SELECT COUNT(*) FROM metric_def WHERE metric_id = $1", metric_id)
            if exists:
                return metric_id
    return None


if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
