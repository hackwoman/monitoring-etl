#!/usr/bin/env python3
"""
监控 ETL 平台 - Demo 数据工厂

统一入口：CMDB 实体 + 日志 + Trace Span 从一份拓扑定义生成。

用法:
  python factory.py init              # 创建 CMDB 实体和关系
  python factory.py run               # 启动日志模拟器
  python factory.py trace             # 产生 trace span 数据写入 ClickHouse
  python factory.py trace --count 200 # 产生 200 条 trace
  python factory.py clear             # 清空 CMDB 数据
  python factory.py reset             # 清空 + 重建
  python factory.py status            # 查看当前数据状态
"""

import json
import time
import random
import uuid
import os
import sys
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import (
    BUSINESSES, HOSTS, SERVICES, MIDDLEWARES, NETWORK_DEVICES,
    RELATIONS, CALL_CHAINS, SCENARIOS, HEALTH_OVERRIDES, DB_BASE_LATENCY,
)

CMDB_API = os.getenv("CMDB_API_URL", "http://8.146.232.9:8001/api/v1/cmdb")
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://47.93.61.196:8123")
LOG_DIR = os.getenv("LOG_DIR", "/var/log/app")

# ============================================================
# CMDB 操作
# ============================================================

def cmdb_post(path, data):
    r = requests.post(f"{CMDB_API}{path}", json=data, timeout=10)
    if r.status_code == 409:
        qname = data.get("qualified_name") or f"{data['type_name']}:{data['name']}"
        existing = cmdb_get(f"/entities?search={data['name']}&type_name={data['type_name']}")
        if existing and existing.get("items"):
            return existing["items"][0]
    return r.json() if r.ok else None

def cmdb_put(path, data):
    r = requests.put(f"{CMDB_API}{path}", json=data, timeout=10)
    return r.ok

def cmdb_get(path):
    r = requests.get(f"{CMDB_API}{path}", timeout=10)
    return r.json() if r.ok else None


# ============================================================
# CMDB 初始化
# ============================================================

def clear_cmdb():
    print("🗑️  清空 CMDB 数据...")
    entities = cmdb_get("/entities?limit=500")
    if entities:
        for e in entities.get("items", []):
            r = requests.delete(f"{CMDB_API}/entities/{e['guid']}", timeout=10)
            status = "✅" if r.ok else "⚠️"
            print(f"  {status} 删除 {e['name']} ({e['type_name']})")
    print("  完成")


def init_cmdb():
    print("=" * 50)
    print("  🏗️  CMDB 初始化")
    print("=" * 50)

    print("\n🏢 业务实体...")
    biz_guids = {}
    for name, attrs in BUSINESSES.items():
        labels = attrs.pop("labels", {})
        result = cmdb_post("/entities", {
            "type_name": "Business", "name": name,
            "attributes": attrs, "labels": labels,
            "biz_service": name, "source": "factory",
        })
        if result:
            biz_guids[name] = result["guid"]
            print(f"  ✅ {name}")

    print("\n🖥️  主机...")
    host_guids = {}
    for name, attrs in HOSTS.items():
        labels = attrs.pop("labels", {})
        biz = None
        for svc in SERVICES.values():
            if svc["host"] == name: biz = svc["business"]; break
        for mw in MIDDLEWARES.values():
            if mw["host"] == name: biz = mw["business"]; break
        result = cmdb_post("/entities", {
            "type_name": "Host", "name": name,
            "attributes": attrs, "labels": labels,
            "biz_service": biz, "source": "factory",
        })
        if result:
            host_guids[name] = result["guid"]
            print(f"  ✅ {name} ({attrs['ip']})")

    print("\n⚙️  服务...")
    svc_guids = {}
    for name, conf in SERVICES.items():
        result = cmdb_post("/entities", {
            "type_name": "Service", "name": name,
            "attributes": conf["attrs"], "labels": conf["labels"],
            "biz_service": conf["business"], "source": "factory",
        })
        if result:
            svc_guids[name] = result["guid"]
            print(f"  ✅ {name}")

    print("\n🗄️  数据库/缓存...")
    mw_guids = {}
    for name, conf in MIDDLEWARES.items():
        result = cmdb_post("/entities", {
            "type_name": conf["type"], "name": name,
            "attributes": conf["attrs"], "labels": conf["labels"],
            "biz_service": conf["business"], "source": "factory",
        })
        if result:
            mw_guids[name] = result["guid"]
            print(f"  ✅ {name} ({conf['type']})")

    print("\n🌐 网络设备...")
    net_guids = {}
    for name, conf in NETWORK_DEVICES.items():
        result = cmdb_post("/entities", {
            "type_name": "NetworkDevice", "name": name,
            "attributes": conf["attrs"], "labels": conf["labels"],
            "source": "factory",
        })
        if result:
            net_guids[name] = result["guid"]
            print(f"  ✅ {name}")

    print("\n🔗 关系...")
    all_guids = {**biz_guids, **svc_guids, **mw_guids, **host_guids, **net_guids}
    pools = {"businesses": biz_guids, "services": svc_guids, "middlewares": mw_guids}
    rel_count = 0

    for src_key, tgt_key, rel_type, src_pool, tgt_pool in RELATIONS:
        src_guid = pools.get(src_pool, {}).get(src_key) or all_guids.get(src_key)
        tgt_guid = pools.get(tgt_pool, {}).get(tgt_key) or all_guids.get(tgt_key)
        if src_guid and tgt_guid:
            r = cmdb_post(f"/entities/{src_guid}/relations", {
                "type_name": rel_type, "end2_guid": tgt_guid, "source": "factory",
            })
            if r: rel_count += 1

    # runs_on 关系
    for svc_name, conf in SERVICES.items():
        h = host_guids.get(conf["host"])
        s = svc_guids.get(svc_name)
        if h and s:
            r = cmdb_post(f"/entities/{s}/relations", {"type_name": "runs_on", "end2_guid": h, "source": "factory"})
            if r: rel_count += 1
    for mw_name, conf in MIDDLEWARES.items():
        h = host_guids.get(conf["host"])
        m = mw_guids.get(mw_name)
        if h and m:
            r = cmdb_post(f"/entities/{m}/relations", {"type_name": "runs_on", "end2_guid": h, "source": "factory"})
            if r: rel_count += 1

    print(f"  ✅ {rel_count} 条关系")

    print("\n💚 健康度设置...")
    all_entity_guids = {**svc_guids, **mw_guids, **host_guids}
    for name, health in HEALTH_OVERRIDES.items():
        guid = all_entity_guids.get(name)
        if guid:
            cmdb_put(f"/entities/{guid}", health)
            print(f"  🔴 {name}: health={health['health_score']} risk={health['risk_score']}")
    for name, guid in all_entity_guids.items():
        if name not in HEALTH_OVERRIDES:
            cmdb_put(f"/entities/{guid}", {"health_score": random.randint(88, 100), "health_level": "healthy"})
    print("  ✅ 其余实体 healthy")

    print(f"\n{'=' * 50}")
    print(f"  ✅ CMDB 初始化完成")
    print(f"     业务:{len(biz_guids)} 主机:{len(host_guids)} 服务:{len(svc_guids)} 中间件:{len(mw_guids)} 关系:{rel_count}")
    print(f"{'=' * 50}")


# ============================================================
# Trace Span 模拟器
# ============================================================

def _gen_trace_spans(chain_name, scenario="normal"):
    """生成一条完整调用链的所有 span。"""
    chain = CALL_CHAINS[chain_name]
    fault_config = SCENARIOS[scenario]["faults"]
    trace_id = uuid.uuid4().hex
    now_us = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
    spans = []

    def _build_spans(span_defs, parent_span_id, start_offset_us):
        local_offset = start_offset_us
        for service, endpoint, kind, children in span_defs:
            svc_conf = SERVICES.get(service, {})
            mw_conf = MIDDLEWARES.get(service, {})
            fault = fault_config.get(service)

            # 基础延迟
            if service in DB_BASE_LATENCY:
                op = endpoint.split()[0] if endpoint else "default"
                base_lat = DB_BASE_LATENCY[service].get(op, DB_BASE_LATENCY[service].get("default", 3))
            else:
                ep = next((e for e in svc_conf.get("endpoints", []) if f"{e['method']} {e['path']}" == endpoint), None)
                base_lat = ep["base_latency"] if ep else 20

            # 故障影响
            if fault:
                latency_us = int(base_lat * fault.get("latency_multiplier", 1) * random.uniform(0.8, 1.2) * 1000)
                is_error = random.random() < fault.get("error_rate", 0)
            else:
                latency_us = int(base_lat * random.uniform(0.7, 1.3) * 1000)
                is_error = False

            span_id = uuid.uuid4().hex[:16]
            start_us = now_us + local_offset
            end_us = start_us + latency_us

            parts = endpoint.split(" ", 1)
            method = parts[0] if len(parts) > 1 else ""
            url = parts[1] if len(parts) > 1 else endpoint

            host_name = svc_conf.get("host", mw_conf.get("host", ""))
            peer_service = ""

            # DB span
            db_system = ""
            db_op = ""
            if service in MIDDLEWARES:
                db_system = MIDDLEWARES[service]["attrs"].get("db_type", "").lower()
                db_op = method if method else "query"

            span = {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "span_name": endpoint,
                "start_time_us": start_us,
                "end_time_us": end_us,
                "duration_us": latency_us,
                "service_name": service,
                "host_name": host_name,
                "endpoint": endpoint,
                "peer_service": peer_service,
                "span_kind": kind,
                "status_code": "error" if is_error else "ok",
                "status_message": fault.get("error_msg", "") if is_error and fault else "",
                "http_method": method,
                "http_status_code": 500 if is_error else 200,
                "http_url": url,
                "db_system": db_system,
                "db_operation": db_op,
                "attributes": {"trace_id": trace_id},
                "labels": {"env": "prod"},
            }
            spans.append(span)

            # 递归子 span
            child_end = local_offset + latency_us
            if children:
                child_spans, child_end = _build_spans(children, span_id, local_offset)
                spans.extend(child_spans)
                # 父 span 的 end_time 覆盖所有子 span
                span["end_time_us"] = max(end_us, child_end)
                span["duration_us"] = span["end_time_us"] - start_us

            local_offset = child_end

        return spans, local_offset

    root_spans = chain["spans"]
    all_spans, _ = _build_spans(root_spans, "", 0)
    return trace_id, all_spans


def write_traces_to_clickhouse(count=100, scenario="normal"):
    """批量生成 trace span 并写入 ClickHouse。"""
    print(f"\n🔗 生成 Trace Span 数据")
    print(f"   数量: {count} | 场景: {scenario}")

    chain_names = list(CALL_CHAINS.keys())
    total_spans = 0
    batch = []

    for i in range(count):
        chain_name = random.choice(chain_names)
        trace_id, spans = _gen_trace_spans(chain_name, scenario)
        batch.extend(spans)
        total_spans += len(spans)

        # 每 20 条 trace 批量写入
        if len(batch) >= 60:
            _flush_spans(batch)
            batch = []

    if batch:
        _flush_spans(batch)

    print(f"   ✅ 完成: {count} 条 trace, {total_spans} 个 span")


def _flush_spans(spans):
    """批量写入 ClickHouse traces.spans 表。"""
    if not spans:
        return

    columns = [
        "trace_id", "span_id", "parent_span_id", "span_name",
        "start_time", "end_time", "duration_ms",
        "start_time_us", "duration_us",
        "service_name", "host_name", "endpoint",
        "peer_service", "span_kind",
        "status_code", "status_message",
        "http_method", "http_status_code", "http_url",
        "db_system", "db_operation",
        "attributes", "labels",
    ]

    def _us_to_dt(us):
        """微秒时间戳 → DateTime 字符串"""
        ts = us / 1_000_000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    for s in spans:
        row_data = {
            "trace_id": s.get("trace_id", ""),
            "span_id": s.get("span_id", ""),
            "parent_span_id": s.get("parent_span_id", ""),
            "span_name": s.get("span_name", ""),
            "start_time": _us_to_dt(s.get("start_time_us", 0)),
            "end_time": _us_to_dt(s.get("end_time_us", 0)),
            "duration_ms": str(s.get("duration_us", 0) // 1000),
            "start_time_us": str(s.get("start_time_us", 0)),
            "duration_us": str(s.get("duration_us", 0)),
            "service_name": s.get("service_name", ""),
            "host_name": s.get("host_name", ""),
            "endpoint": s.get("endpoint", ""),
            "peer_service": s.get("peer_service", ""),
            "span_kind": s.get("span_kind", "internal"),
            "status_code": s.get("status_code", "ok"),
            "status_message": (s.get("status_message") or "").replace("'", "\\'"),
            "http_method": s.get("http_method", ""),
            "http_status_code": str(s.get("http_status_code", 0)),
            "http_url": s.get("http_url", ""),
            "db_system": s.get("db_system", ""),
            "db_operation": s.get("db_operation", ""),
            "attributes": json.dumps({"trace_id": s.get("trace_id","")}, ensure_ascii=False).replace("'", "\\'"),
            "labels": json.dumps({"env": "prod"}, ensure_ascii=False).replace("'", "\\'"),
        }
        values = ",".join(f"'{row_data.get(c, '')}'" for c in columns)
        lines.append(f"({values})")

    sql = f"INSERT INTO traces.spans ({','.join(columns)}) VALUES {','.join(lines)}"
    try:
        r = requests.post(CLICKHOUSE_URL, data=sql.encode('utf-8'), timeout=30)
        if r.status_code != 200:
            print(f"   ⚠️ ClickHouse 写入失败({len(spans)} spans): {r.status_code} {r.text[:200]}")
        else:
            pass  # 成功
    except Exception as e:
        print(f"   ⚠️ ClickHouse 异常({len(spans)} spans): {e}")


# ============================================================
# 链路查询 API（直接查 ClickHouse）
# ============================================================

def query_trace(trace_id):
    """按 trace_id 查询完整调用链。"""
    sql = f"SELECT * FROM traces.spans WHERE trace_id = '{trace_id}' ORDER BY start_time_us FORMAT JSON"
    r = requests.post(CLICKHOUSE_URL, data=sql, timeout=10)
    if r.ok:
        return r.json()
    return None


def query_slowest_traces(limit=10):
    """查询最慢的 trace。"""
    sql = f"""
    SELECT trace_id, service_name, span_name, duration_us, http_status_code
    FROM traces.spans
    WHERE parent_span_id = ''
    ORDER BY duration_us DESC
    LIMIT {limit}
    FORMAT JSON
    """
    r = requests.post(CLICKHOUSE_URL, data=sql, timeout=10)
    if r.ok:
        return r.json()
    return None


def query_service_topology():
    """从 trace 数据中提取服务调用拓扑（自动发现关系）。"""
    sql = """
    SELECT
        p.service_name as caller,
        s.service_name as callee,
        count() as call_count,
        round(avg(s.duration_ms), 2) as avg_latency_ms,
        round(quantile(0.99)(s.duration_ms), 2) as p99_latency_ms,
        round(countIf(s.status_code = 'error') * 100.0 / count(), 2) as error_rate
    FROM traces.spans p
    INNER JOIN traces.spans s ON p.trace_id = s.trace_id AND s.parent_span_id = p.span_id
    GROUP BY caller, callee
    ORDER BY call_count DESC
    FORMAT JSON
    """
    r = requests.post(CLICKHOUSE_URL, data=sql, timeout=10)
    if r.ok:
        return r.json()
    return None


def show_trace(trace_id):
    """格式化展示一条 trace 的调用链。"""
    data = query_trace(trace_id)
    if not data or not data.get("data"):
        print(f"  ❌ trace_id={trace_id} 未找到")
        return

    spans = data["data"]
    # 建立 span 索引
    span_map = {s["span_id"]: s for s in spans}
    roots = [s for s in spans if not s.get("parent_span_id")]

    print(f"\n{'=' * 60}")
    print(f"  🔍 Trace: {trace_id[:16]}...")
    print(f"  总 Span 数: {len(spans)}")
    print(f"{'=' * 60}")

    def _print_span(span, depth=0):
        indent = "  " + "  │ " * depth
        prefix = "  ├─ " if depth > 0 else ""
        dur_ms = span["duration_us"] / 1000
        status = "❌" if span["status_code"] == "error" else "✅"
        db_tag = f" [{span['db_system']}]" if span.get("db_system") else ""

        print(f"{indent}{prefix}{status} {span['service_name']}: {span['span_name']}{db_tag} ({dur_ms:.1f}ms)")

        if span.get("status_message"):
            print(f"{indent}  │   ⚠️ {span['status_message']}")

        # 找子 span
        children = [s for s in spans if s.get("parent_span_id") == span["span_id"]]
        children.sort(key=lambda x: x["start_time_us"])
        for child in children:
            _print_span(child, depth + 1)

    for root in roots:
        _print_span(root)

    # 总耗时
    total_dur = max(s["duration_us"] for s in spans) if spans else 0
    has_error = any(s["status_code"] == "error" for s in spans)
    print(f"\n  📊 总耗时: {total_dur / 1000:.1f}ms {'🔴 含错误' if has_error else '🟢 正常'}")


def show_topology():
    """展示从 trace 数据自动发现的服务拓扑。"""
    data = query_service_topology()
    if not data or not data.get("data"):
        print("  ⚠️ 无 trace 数据，请先运行: python factory.py trace")
        return

    print(f"\n{'=' * 60}")
    print("  🌐 服务调用拓扑（从 Trace 数据自动发现）")
    print(f"{'=' * 60}")
    print(f"  {'调用方':<25} → {'被调方':<25} {'调用数':>6} {'平均延迟':>10} {'P99':>10} {'错误率':>8}")
    print(f"  {'-' * 95}")

    for row in data["data"]:
        err = f"{row['error_rate']}%"
        print(f"  {row['caller']:<25} → {row['callee']:<25} {row['call_count']:>6} {row['avg_latency_ms']:>8}ms {row['p99_latency_ms']:>8}ms {err:>8}")


# ============================================================
# 日志模拟器（引用共享拓扑）
# ============================================================

LOG_MESSAGES = {
    "gateway": ["Request received: {method} {path} from {ip}", "Upstream responded: {status} in {lat}ms", "Forwarded to {svc}"],
    "order-service": ["Processing order for user_{uid}", "Order created: order_{oid}", "Calling payment-service"],
    "payment-service": ["Processing payment for order_{oid}", "Payment recorded: pay_{pid}", "Calling alipay-gateway"],
    "inventory-service": ["Stock queried: product_{pid} = {stock}", "Stock deducted: product_{pid}"],
    "user-service": ["User registered: user_{uid}", "Profile queried: user_{uid}", "Session created for user_{uid}"],
}

class LogWriter:
    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.handles = {}
    def get(self, svc):
        if svc not in self.handles:
            self.handles[svc] = open(self.log_dir / f"{svc}.log", "a")
        return self.handles[svc]
    def write(self, svc, entry):
        self.get(svc).write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.get(svc).flush()
    def close(self):
        for h in self.handles.values(): h.close()

def run_simulator(rps=1.0, scenario="normal", log_dir=LOG_DIR, switch_after=0):
    print("=" * 50)
    print("  🚀 日志模拟器")
    print("=" * 50)
    writer = LogWriter(log_dir)
    current = SCENARIOS[scenario]
    sc_name = scenario
    req_count = err_count = 0
    sc_list = list(SCENARIOS.keys())
    sc_idx = sc_list.index(scenario)
    last_sw = time.time()

    try:
        while True:
            if switch_after > 0 and time.time() - last_sw > switch_after:
                sc_idx = (sc_idx + 1) % len(sc_list)
                sc_name = sc_list[sc_idx]
                current = SCENARIOS[sc_name]
                last_sw = time.time()
                print(f"  🎬 场景: {sc_name} - {current['description']}")

            chain_name = random.choice(list(CALL_CHAINS.keys()))
            trace_id = uuid.uuid4().hex
            uid = f"user_{random.randint(10000, 99999)}"
            oid = f"ord_{random.randint(100000, 999999)}"

            # 递归遍历 span 树产生日志
            def _emit_spans(span_defs):
                for svc, endpoint, kind, children in span_defs:
                    if svc not in SERVICES:
                        if children: _emit_spans(children)
                        continue
                    conf = SERVICES[svc]
                    fault = current["faults"].get(svc)
                    ep = next((e for e in conf["endpoints"] if f"{e['method']} {e['path']}" == endpoint), conf["endpoints"][0])
                    base = ep["base_latency"]
                    lat = int(base * (fault["latency_multiplier"] if fault else 1) * random.uniform(0.8, 1.3))
                    is_err = fault and random.random() < fault["error_rate"]
                    status = 500 if is_err else 200
                    level = "error" if is_err else ("warn" if lat > base * 3 else "info")
                    msg = fault["error_msg"] if is_err and fault else random.choice(LOG_MESSAGES.get(svc, ["Request processed"])).format(
                        method=ep["method"], path=ep["path"], ip=f"10.0.{random.randint(0,255)}.{random.randint(1,254)}",
                        status=status, lat=lat, svc=random.choice(list(SERVICES.keys())),
                        uid=uid, oid=oid, pid=f"pay_{random.randint(100000,999999)}",
                        product_id=f"prod_{random.randint(1000,9999)}", stock=random.randint(10, 500))
                    writer.write(svc, {
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                        "level": level, "service_name": svc, "host_name": conf["host"],
                        "message": msg, "trace_id": trace_id, "span_id": uuid.uuid4().hex[:16],
                        "endpoint": endpoint, "http_status": status, "labels": conf["labels"],
                    })
                    if is_err: nonlocal_err()
                    if children: _emit_spans(children)

            def nonlocal_err():
                nonlocal err_count
                err_count += 1

            _emit_spans(CALL_CHAINS[chain_name]["spans"])
            req_count += 1
            if req_count % 100 == 0:
                print(f"  📊 请求: {req_count} | 错误: {err_count} | 场景: {sc_name}")
            time.sleep(max(0.01, 1.0 / rps + random.uniform(-0.1, 0.1) / rps))
    except KeyboardInterrupt:
        print(f"\n  ✅ 停止。总请求: {req_count}, 错误: {err_count}")
    finally:
        writer.close()


# ============================================================
# CLI
# ============================================================

def show_status():
    types = cmdb_get("/types")
    if types:
        print("📦 类型定义:")
        for t in types.get("items", []):
            metrics = (t.get("definition") or {}).get("metrics", [])
            print(f"  {t['type_name']:20s} ({t['category']}) - {len(metrics)} 指标")

    r = requests.get(f"{CMDB_API.replace('/cmdb', '')}/overview", timeout=10)
    if r.ok:
        ov = r.json()
        print(f"\n📊 总览:")
        print(f"  实体总数: {ov.get('total_entities', 0)}")
        print(f"  资源分布: {ov.get('resource_size', {})}")
        print(f"  健康分布: {ov.get('health_distribution', {})}")

    # Trace 统计
    try:
        r = requests.post(CLICKHOUSE_URL, data="SELECT count() as total, uniq(trace_id) as traces FROM traces.spans FORMAT JSON", timeout=5)
        if r.ok:
            d = r.json().get("data", [{}])[0]
            print(f"\n🔗 Trace 数据:")
            print(f"  Span 总数: {d.get('total', 0)}")
            print(f"  Trace 数: {d.get('traces', 0)}")
    except:
        pass


def main():
    parser = argparse.ArgumentParser(description="Demo 数据工厂")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="创建 CMDB 实体和关系")
    sub.add_parser("clear", help="清空 CMDB 数据")
    sub.add_parser("reset", help="清空 CMDB 并重建")
    sub.add_parser("status", help="查看当前数据状态")

    run_p = sub.add_parser("run", help="启动日志模拟器")
    run_p.add_argument("--rps", type=float, default=1.0)
    run_p.add_argument("--scenario", default="normal", choices=list(SCENARIOS.keys()))
    run_p.add_argument("--log-dir", default=LOG_DIR)
    run_p.add_argument("--switch-after", type=int, default=0)

    trace_p = sub.add_parser("trace", help="生成 Trace Span 数据")
    trace_p.add_argument("--count", type=int, default=100, help="trace 数量")
    trace_p.add_argument("--scenario", default="normal", choices=list(SCENARIOS.keys()))
    trace_p.add_argument("--show", type=str, default="", help="展示指定 trace_id")
    trace_p.add_argument("--topology", action="store_true", help="展示从 trace 发现的拓扑")

    args = parser.parse_args()

    if args.command == "init": init_cmdb()
    elif args.command == "clear": clear_cmdb()
    elif args.command == "reset": clear_cmdb(); init_cmdb()
    elif args.command == "status": show_status()
    elif args.command == "run":
        run_simulator(rps=args.rps, scenario=args.scenario, log_dir=args.log_dir, switch_after=args.switch_after)
    elif args.command == "trace":
        if args.show:
            show_trace(args.show)
        elif args.topology:
            show_topology()
        else:
            write_traces_to_clickhouse(count=args.count, scenario=args.scenario)
            print("\n💡 试试:")
            print("   python factory.py trace --topology  # 查看调用拓扑")
            print("   python factory.py status             # 查看总览")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
