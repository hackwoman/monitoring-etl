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
    USER_POOL, USER_PREFERENCES,
)

CMDB_API = os.getenv("CMDB_API_URL", "http://8.146.232.9:8001/api/v1/cmdb")
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://47.93.61.196:8123")
LOG_DIR = os.getenv("LOG_DIR", "/var/log/app")

# ============================================================
# 堆栈模板（模拟不同语言的错误堆栈）
# ============================================================

STACK_TEMPLATES = {
    "Java": {
        "exceptions": [
            "java.lang.NullPointerException",
            "java.sql.SQLTimeoutException",
            "org.springframework.dao.DataAccessResourceFailureException",
            "java.net.ConnectException",
            "java.util.concurrent.TimeoutException",
        ],
        "frames": [
            {"class": "com.example.{service}.controller.{Controller}", "method": "{method}", "file": "{Controller}.java", "line": 42},
            {"class": "com.example.{service}.service.{Service}", "method": "process{Operation}", "file": "{Service}.java", "line": 78},
            {"class": "com.example.{service}.repository.{Repository}", "method": "findBy{Field}", "file": "{Repository}.java", "line": 35},
            {"class": "org.springframework.jdbc.core.JdbcTemplate", "method": "query", "file": "JdbcTemplate.java", "line": 375},
            {"class": "com.zaxxer.hikari.pool.HikariPool", "method": "getConnection", "file": "HikariPool.java", "line": 187},
        ],
    },
    "Go": {
        "exceptions": [
            "runtime.errorString",
            "context.deadlineExceededError",
            "net.OpError",
            "errors.errorString",
            "syscall.Errno",
        ],
        "frames": [
            {"function": "main.{Controller}.{Method}", "file": "/app/controller/{controller}.go", "line": 42},
            {"function": "main.{Service}.{Method}", "file": "/app/service/{service}.go", "line": 78},
            {"function": "main.{Repository}.{Method}", "file": "/app/repository/{repository}.go", "line": 35},
            {"function": "database/sql.(*DB).QueryContext", "file": "/usr/local/go/src/database/sql/sql.go", "line": 1825},
            {"function": "github.com/go-redis/redis.(*Client).Get", "file": "/go/pkg/mod/github.com/go-redis/redis@v8.11/redis.go", "line": 245},
        ],
    },
}


def _gen_method_stack(service_name, total_duration_ms, lang="Java"):
    """生成方法级调用栈（带耗时分布）。"""
    template = STACK_TEMPLATES.get(lang, STACK_TEMPLATES["Java"])
    
    # 提取服务名中的组件名
    svc_parts = service_name.replace("-service", "").replace("-db", "").replace("-cache", "").split("-")
    svc_name = svc_parts[0] if svc_parts else "app"
    
    # 生成调用栈（耗时分配：越底层耗时越长）
    depth = random.randint(3, 5)
    frames = []
    remaining_ms = total_duration_ms
    
    # 耗时分配比例（从上到下递增）
    ratios = [0.05, 0.10, 0.20, 0.30, 0.35]
    
    for i in range(depth):
        frame = template["frames"][i % len(template["frames"])].copy()
        
        # 替换占位符
        for key in frame:
            if isinstance(frame[key], str):
                frame[key] = frame[key].replace("{service}", svc_name.title())
                frame[key] = frame[key].replace("{Controller}", svc_name.title() + "Controller")
                frame[key] = frame[key].replace("{Service}", svc_name.title() + "Service")
                frame[key] = frame[key].replace("{Repository}", svc_name.title() + "Repository")
                frame[key] = frame[key].replace("{controller}", svc_name)
                frame[key] = frame[key].replace("{repository}", svc_name)
                frame[key] = frame[key].replace("{method}", random.choice(["Handle", "Process", "Query", "Execute", "Get"]))
                frame[key] = frame[key].replace("{Operation}", random.choice(["Order", "Payment", "User", "Query"]))
                frame[key] = frame[key].replace("{Field}", random.choice(["Id", "Name", "Status"]))
        
        # 计算该方法的耗时
        ratio = ratios[i] if i < len(ratios) else 0.35
        method_ms = max(1, int(total_duration_ms * ratio * random.uniform(0.8, 1.2)))
        remaining_ms -= method_ms
        
        # 行号
        if "line" in frame:
            frame["line"] = frame["line"] + random.randint(-10, 10)
        
        # 添加耗时信息
        frame["duration_ms"] = method_ms
        frame["self_ms"] = max(0, method_ms - (method_ms * 0.3))  # 自身耗时（不含子调用）
        
        frames.append(frame)
    
    return frames


def _gen_stack_trace(service_name, total_duration_ms, error_type="exception", lang="Java"):
    """生成完整的堆栈记录（方法调用耗时 + 错误堆栈）。"""
    template = STACK_TEMPLATES.get(lang, STACK_TEMPLATES["Java"])
    
    # 提取服务名中的组件名
    svc_parts = service_name.replace("-service", "").replace("-db", "").replace("-cache", "").split("-")
    svc_name = svc_parts[0] if svc_parts else "app"
    
    # 生成方法级调用栈（带耗时）
    method_stack = _gen_method_stack(service_name, total_duration_ms, lang)
    
    # 生成错误堆栈（如果需要）
    error_frames = []
    exception = ""
    error_message = ""
    
    if error_type == "exception":
        # 错误堆栈 = 方法栈的子集（从某个方法开始出错）
        error_depth = random.randint(2, len(method_stack))
        error_frames = method_stack[:error_depth]
        
        # 选择异常类型
        exception = random.choice(template["exceptions"])
        
        # 生成错误消息
        error_messages = {
            "java.lang.NullPointerException": "Cannot invoke method on null object",
            "java.sql.SQLTimeoutException": f"Query timeout after {random.randint(30, 300)} seconds",
            "org.springframework.dao.DataAccessResourceFailureException": "Could not open JDBC Connection",
            "java.net.ConnectException": f"Connection refused: {service_name}:{random.choice([3306, 6379, 8080])}",
            "java.util.concurrent.TimeoutException": f"Future timed out after {random.randint(30, 60)} seconds",
            "runtime.errorString": "nil pointer dereference",
            "context.deadlineExceededError": "context deadline exceeded",
            "net.OpError": f"dial tcp {service_name}:{random.choice([3306, 6379])}: connect: connection refused",
            "errors.errorString": "redis: connection pool exhausted",
            "syscall.Errno": "connection reset by peer",
        }
        error_message = error_messages.get(exception, "Unknown error")
    
    return {
        "method_stack": method_stack,        # 方法调用栈（带耗时）
        "error_type": exception,             # 错误类型
        "error_message": error_message,      # 错误消息
        "error_frames": error_frames,        # 错误堆栈帧
        "total_duration_ms": total_duration_ms,
    }


def _flush_stacktraces(stacktraces):
    """批量写入 ClickHouse traces.stacktraces 表。"""
    if not stacktraces:
        return
    
    columns = [
        "trace_id", "span_id", "error_type", "error_message",
        "stack_frames", "error_frames", "service_name", "endpoint",
        "timestamp", "total_duration_ms", "has_error",
        "attributes", "labels"
    ]
    
    def _us_to_dt(us):
        ts = us / 1_000_000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    lines = []
    for s in stacktraces:
        row_data = {
            "trace_id": s.get("trace_id", ""),
            "span_id": s.get("span_id", ""),
            "error_type": s.get("error_type", ""),
            "error_message": (s.get("error_message") or "").replace("'", "\\'"),
            "stack_frames": (s.get("stack_frames") or "[]").replace("'", "\\'"),
            "error_frames": (s.get("error_frames") or "[]").replace("'", "\\'"),
            "service_name": s.get("service_name", ""),
            "endpoint": s.get("endpoint", ""),
            "timestamp": _us_to_dt(s.get("timestamp_us", 0)),
            "total_duration_ms": str(s.get("total_duration_ms", 0)),
            "has_error": "1" if s.get("has_error") else "0",
            "attributes": json.dumps(s.get("attributes", {}), ensure_ascii=False).replace("'", "\\'"),
            "labels": json.dumps(s.get("labels", {}), ensure_ascii=False).replace("'", "\\'"),
        }
        values = ",".join(f"'{row_data.get(c, '')}'" for c in columns)
        lines.append(f"({values})")
    
    sql = f"INSERT INTO traces.stacktraces ({','.join(columns)}) VALUES {','.join(lines)}"
    try:
        r = requests.post(CLICKHOUSE_URL, data=sql.encode('utf-8'), timeout=30)
        if r.status_code != 200:
            print(f"   ⚠️ 堆栈写入失败({len(stacktraces)} records): {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"   ⚠️ 堆栈写入异常({len(stacktraces)} records): {e}")

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


# ============================================================
# APM 数据生成器（支持 user_id + trace_id 关联）
# ============================================================

def _get_user_type(user_id):
    """根据 user_id 确定用户类型（用于模拟不同用户行为）"""
    num = int(user_id.split("_")[1])
    if num <= 10:
        return "high_value"
    elif num <= 80:
        return "normal"
    else:
        return "new_user"


def _select_chain_by_user(user_id):
    """根据用户类型选择调用链（模拟用户行为偏好）"""
    user_type = _get_user_type(user_id)
    prefs = USER_PREFERENCES[user_type]
    
    chain_weights = {
        "create_order": int(prefs["pay_weight"] * 100),
        "check_payment": int(prefs["pay_weight"] * 50),
        "search_products": int(prefs["search_weight"] * 100),
        "user_register": int(prefs["register_weight"] * 100),
        "user_login": int(prefs["register_weight"] * 80),
        "query_inventory": int(prefs["pay_weight"] * 30),
    }
    
    chains = list(chain_weights.keys())
    weights = [chain_weights[c] for c in chains]
    return random.choices(chains, weights=weights, k=1)[0]


def _gen_apm_spans(chain_name, user_id, biz_id=None, timestamp=None):
    """生成一条完整的 APM 调用链，包含 user_id 和 biz_id 关联。"""
    chain = CALL_CHAINS[chain_name]
    trace_id = uuid.uuid4().hex
    
    # 使用指定时间戳或当前时间
    if timestamp:
        now_us = int(timestamp.timestamp() * 1_000_000)
    else:
        now_us = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
    
    # 生成 biz_id（如果未指定）
    if not biz_id:
        biz_id = f"{chain_name}_{uuid.uuid4().hex[:8]}"
    
    spans = []
    stacktraces = []  # 存储堆栈记录
    
    def _build_spans(span_defs, parent_span_id, start_offset_us):
        local_offset = start_offset_us
        for service, endpoint, kind, children in span_defs:
            svc_conf = SERVICES.get(service, {})
            mw_conf = MIDDLEWARES.get(service, {})
            
            # 基础延迟（添加随机波动）
            if service in DB_BASE_LATENCY:
                op = endpoint.split()[0] if endpoint else "default"
                base_lat = DB_BASE_LATENCY[service].get(op, DB_BASE_LATENCY[service].get("default", 3))
            else:
                ep = next((e for e in svc_conf.get("endpoints", []) if f"{e['method']} {e['path']}" == endpoint), None)
                base_lat = ep["base_latency"] if ep else 20
            
            # 添加随机波动 ±30%
            latency_us = int(base_lat * random.uniform(0.7, 1.3) * 1000)
            is_error = random.random() < 0.02  # 2% 基础错误率
            
            span_id = uuid.uuid4().hex[:16]
            start_us = now_us + local_offset
            end_us = start_us + latency_us
            
            parts = endpoint.split(" ", 1)
            method = parts[0] if len(parts) > 1 else ""
            url = parts[1] if len(parts) > 1 else endpoint
            
            host_name = svc_conf.get("host", mw_conf.get("host", ""))
            
            # DB span 信息
            db_system = ""
            db_op = ""
            if service in MIDDLEWARES:
                db_system = MIDDLEWARES[service]["attrs"].get("db_type", "").lower()
                db_op = method if method else "query"
            
            # 确定语言
            lang = svc_conf.get("attrs", {}).get("language", "Java")
            if lang == "Go":
                lang = "Go"
            else:
                lang = "Java"
            
            # 错误消息
            error_msg = ""
            if is_error:
                error_msgs = [
                    f"ConnectionTimeout: {service}:3306 after {random.randint(30, 300)}s",
                    f"NullPointerException in {service}",
                    f"Upstream {service} returned 500",
                    f"Database query timeout: {endpoint}",
                ]
                error_msg = random.choice(error_msgs)
            
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
                "peer_service": "",
                "span_kind": kind,
                "status_code": "error" if is_error else "ok",
                "status_message": error_msg,
                "http_method": method,
                "http_status_code": 500 if is_error else 200,
                "http_url": url,
                "db_system": db_system,
                "db_operation": db_op,
                "attributes": {
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "biz_id": biz_id,
                    "business": chain.get("business", ""),
                },
                "labels": {
                    "env": "prod",
                    "user_id": user_id,
                    "biz_id": biz_id,
                },
            }
            spans.append(span)
            
            # 生成堆栈记录（对所有 span 生成方法调用栈，对错误 span 额外生成错误堆栈）
            stack = _gen_stack_trace(service, latency_us // 1000, "exception" if is_error else "normal", lang)
            stacktraces.append({
                "trace_id": trace_id,
                "span_id": span_id,
                "error_type": stack["error_type"] if is_error else "",
                "error_message": stack["error_message"] if is_error else "",
                "stack_frames": json.dumps(stack["method_stack"]),  # 方法调用栈（带耗时）
                "error_frames": json.dumps(stack["error_frames"]) if is_error else "[]",  # 错误堆栈帧
                "service_name": service,
                "endpoint": endpoint,
                "timestamp_us": start_us,
                "total_duration_ms": stack["total_duration_ms"],
                "has_error": is_error,
                "attributes": {
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "biz_id": biz_id,
                },
                "labels": {
                    "env": "prod",
                    "service": service,
                },
            })
            
            # 递归子 span
            child_end = local_offset + latency_us
            if children:
                child_spans, child_end = _build_spans(children, span_id, local_offset + int(latency_us * 0.1))
                spans.extend(child_spans)
                span["end_time_us"] = max(end_us, child_end)
                span["duration_us"] = span["end_time_us"] - start_us
            
            local_offset = span["end_time_us"]
        
        return spans, local_offset
    
    root_spans = chain["spans"]
    all_spans, _ = _build_spans(root_spans, "", 0)
    return trace_id, user_id, biz_id, all_spans, stacktraces


def write_apm_data(hours=24, rps=1):
    """生成 APM 连续历史数据（每秒都有数据）。
    
    Args:
        hours: 生成多少小时的历史数据
        rps: 每秒请求数（基准值，实际按流量曲线波动）
    """
    print(f"\n🔗 生成 APM 连续历史数据")
    print(f"   时间范围: {hours} 小时")
    print(f"   基准 RPS: {rps}")
    
    # 时间分布：模拟真实的流量曲线（白天高、夜间低）
    def get_traffic_multiplier(hour):
        if 0 <= hour < 6:
            return 0.3   # 凌晨低谷
        elif 6 <= hour < 9:
            return 0.6   # 早高峰
        elif 9 <= hour < 12:
            return 0.9   # 上午
        elif 12 <= hour < 14:
            return 0.7   # 午休
        elif 14 <= hour < 18:
            return 1.0   # 下午（最高）
        elif 18 <= hour < 22:
            return 0.95  # 晚高峰
        else:
            return 0.5   # 晚间
    
    # 从过去 hours 小时开始，每秒生成数据
    now = datetime.now(timezone.utc)
    start_time = now - __import__('datetime').timedelta(hours=hours)
    
    batch = []
    stack_batch = []
    total_spans = 0
    total_stacks = 0
    total_seconds = hours * 3600
    user_traces = {}
    
    for sec_offset in range(0, total_seconds):
        target_time = start_time + __import__('datetime').timedelta(seconds=sec_offset)
        hour = target_time.hour
        
        # 根据流量曲线计算本秒的请求数
        multiplier = get_traffic_multiplier(hour)
        requests_this_sec = max(1, int(rps * multiplier * random.uniform(0.8, 1.2)))
        
        for _ in range(requests_this_sec):
            # 选择用户
            user_id = random.choice(USER_POOL)
            
            # 根据用户类型选择调用链
            chain_name = _select_chain_by_user(user_id)
            
            # 生成 biz_id
            biz_id = f"{chain_name}_{uuid.uuid4().hex[:8]}"
            
            # 生成 spans 和 stacktraces
            trace_id, user_id, biz_id, spans, stacktraces = _gen_apm_spans(chain_name, user_id, biz_id, target_time)
            
            batch.extend(spans)
            stack_batch.extend(stacktraces)
            total_spans += len(spans)
            total_stacks += len(stacktraces)
            user_traces[user_id] = user_traces.get(user_id, 0) + 1
        
        # 批量写入
        if len(batch) >= 500:
            _flush_spans(batch)
            batch = []
        if len(stack_batch) >= 100:
            _flush_stacktraces(stack_batch)
            stack_batch = []
        
        # 进度
        if (sec_offset + 1) % 3600 == 0:
            hours_done = (sec_offset + 1) // 3600
            print(f"   进度: {hours_done}/{hours} 小时, {total_spans} spans, {total_stacks} stacks")
    
    # 写入剩余数据
    if batch:
        _flush_spans(batch)
    if stack_batch:
        _flush_stacktraces(stack_batch)
    
    print(f"\n   ✅ 完成:")
    print(f"      时间范围: {hours} 小时")
    print(f"      Span 数: {total_spans}")
    print(f"      堆栈记录: {total_stacks}")
    print(f"      用户数: {len(user_traces)}")
    print(f"      平均 RPS: {total_spans / (hours * 3600):.2f}")


def generate_business_demo():
    """生成 Business 实体的 demo 数据，验证 user_id 追踪功能。"""
    print(f"\n📊 生成 Business Demo 数据")
    
    # 为每个 Business 生成一些带有特定 user_id 的 trace
    test_users = ["user_00001", "user_00002", "user_00050", "user_00090"]
    
    for user_id in test_users:
        user_type = _get_user_type(user_id)
        print(f"\n   用户: {user_id} (类型: {user_type})")
        
        # 为该用户生成各种调用链
        for chain_name in ["create_order", "search_products", "user_login"]:
            trace_id, uid, biz_id, spans, stacktraces = _gen_apm_spans(chain_name, user_id)
            _flush_spans(spans)
            if stacktraces:
                _flush_stacktraces(stacktraces)
            print(f"      {chain_name}: trace_id={trace_id[:16]}..., spans={len(spans)}, stacks={len(stacktraces)}")
    
    print(f"\n   ✅ Business Demo 数据生成完成")


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
            "attributes": json.dumps(s.get("attributes", {"trace_id": s.get("trace_id","")}), ensure_ascii=False).replace("'", "\\'"),
            "labels": json.dumps(s.get("labels", {"env": "prod"}), ensure_ascii=False).replace("'", "\\'"),
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

    # APM 数据生成
    apm_p = sub.add_parser("apm", help="生成 APM 历史数据")
    apm_p.add_argument("--hours", type=int, default=24, help="生成多少小时的数据")
    apm_p.add_argument("--rps", type=float, default=0.5, help="模拟每秒请求数")

    # Business Demo 数据
    sub.add_parser("business-demo", help="生成 Business Demo 数据（验证 user_id 追踪）")

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
    elif args.command == "apm":
        write_apm_data(hours=args.hours, rps=args.rps)
        print("\n💡 试试:")
        print("   python factory.py trace --topology  # 查看调用拓扑")
        print("   python factory.py status             # 查看总览")
    elif args.command == "business-demo":
        generate_business_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
