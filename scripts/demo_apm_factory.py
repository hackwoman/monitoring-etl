#!/usr/bin/env python3
"""
APM Demo 数据注入 — 模拟完整的调用链堆栈快照。

模拟场景：
1. 正常调用链：gateway → order-service → order-db (50-200ms)
2. 慢调用链：gateway → payment-service → payment-db (2000ms+, 有慢查询)
3. 错误调用链：gateway → user-service → user-cache (timeout error)
4. 正常调用链：gateway → inventory-service (30-80ms)

每个 trace 包含完整的 span 树（parent_span_id 关联）。
"""

import os
import uuid
import random
import json
from datetime import datetime, timedelta

import httpx

CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://47.93.61.196:8123")

# Demo 实体
GATEWAY = "gateway"
ORDER_SVC = "order-service"
ORDER_DB = "order-db"
PAYMENT_SVC = "payment-service"
PAYMENT_DB = "payment-db"
USER_SVC = "user-service"
USER_CACHE = "user-cache"
INVENTORY_SVC = "inventory-service"

SERVICES = [GATEWAY, ORDER_SVC, PAYMENT_SVC, USER_SVC, INVENTORY_SVC]
DB_SERVICES = {ORDER_DB: "mysql", PAYMENT_DB: "mysql", USER_CACHE: "redis"}

ENDPOINTS = {
    GATEWAY: ["/api/orders", "/api/payments", "/api/users", "/api/inventory"],
    ORDER_SVC: ["/orders/create", "/orders/list", "/orders/{id}"],
    PAYMENT_SVC: ["/payments/charge", "/payments/refund"],
    USER_SVC: ["/users/profile", "/users/auth"],
    INVENTORY_SVC: ["/inventory/check", "/inventory/reserve"],
}

HTTP_METHODS = {"/api/orders": "POST", "/api/payments": "POST", "/api/users": "GET", "/api/inventory": "GET",
                "/orders/create": "POST", "/orders/list": "GET", "/orders/{id}": "GET",
                "/payments/charge": "POST", "/payments/refund": "POST",
                "/users/profile": "GET", "/users/auth": "POST",
                "/inventory/check": "GET", "/inventory/reserve": "POST"}


def gen_trace_id():
    return uuid.uuid4().hex[:32]


def gen_span_id():
    return uuid.uuid4().hex[:16]


def make_span(trace_id, span_id, parent_span_id, service, endpoint, method,
              start_time, duration_ms, status="ok", status_msg="",
              peer_service="", db_system="", db_operation="",
              http_status=200, span_kind="internal"):
    end_time = start_time + timedelta(milliseconds=duration_ms)
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "span_name": f"{method} {endpoint}" if method else endpoint,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_ms": duration_ms,
        "service_name": service,
        "host_name": f"{service}-01",
        "endpoint": endpoint,
        "peer_service": peer_service,
        "span_kind": span_kind,
        "status_code": status,
        "status_message": status_msg,
        "http_method": method,
        "http_status_code": http_status,
        "http_url": f"http://{service}:8080{endpoint}",
        "db_system": db_system,
        "db_operation": db_operation,
        "attributes": json.dumps({"env": "prod", "version": "1.2.3"}),
        "labels": json.dumps({"team": "platform", "region": "cn-east-1"}),
    }


def gen_normal_trace(base_time):
    """正常调用链: gateway → order-service → order-db (80-150ms)"""
    trace_id = gen_trace_id()
    spans = []
    ep = random.choice(ENDPOINTS[GATEWAY])
    method = HTTP_METHODS[ep]

    # gateway span (总耗时)
    gw_dur = random.randint(80, 150)
    gw_span = gen_span_id()
    spans.append(make_span(trace_id, gw_span, "", GATEWAY, ep, method,
                           base_time, gw_dur, span_kind="server"))

    # order-service span
    svc_dur = gw_dur - random.randint(5, 15)
    svc_span = gen_span_id()
    svc_ep = random.choice(ENDPOINTS[ORDER_SVC])
    spans.append(make_span(trace_id, svc_span, gw_span, ORDER_SVC, svc_ep,
                           HTTP_METHODS[svc_ep], base_time + timedelta(milliseconds=random.randint(2, 8)),
                           svc_dur, peer_service=GATEWAY, span_kind="server"))

    # order-db span
    db_dur = svc_dur - random.randint(10, 30)
    db_span = gen_span_id()
    db_op = random.choice(["SELECT", "INSERT", "UPDATE"])
    spans.append(make_span(trace_id, db_span, svc_span, ORDER_DB, "",
                           db_op, base_time + timedelta(milliseconds=random.randint(10, 20)),
                           max(1, db_dur), peer_service=ORDER_SVC,
                           db_system="mysql", db_operation=db_op, span_kind="client"))

    return spans


def gen_slow_trace(base_time):
    """慢调用链: gateway → payment-service → payment-db (2000ms+，慢查询)"""
    trace_id = gen_trace_id()
    spans = []
    ep = random.choice(["/api/payments"])
    method = "POST"

    gw_dur = random.randint(2500, 5000)
    gw_span = gen_span_id()
    spans.append(make_span(trace_id, gw_span, "", GATEWAY, ep, method,
                           base_time, gw_dur, status="error",
                           status_msg="timeout", http_status=504, span_kind="server"))

    svc_dur = gw_dur - random.randint(5, 20)
    svc_span = gen_span_id()
    svc_ep = random.choice(ENDPOINTS[PAYMENT_SVC])
    spans.append(make_span(trace_id, svc_span, gw_span, PAYMENT_SVC, svc_ep,
                           HTTP_METHODS[svc_ep], base_time + timedelta(milliseconds=random.randint(3, 10)),
                           svc_dur, peer_service=GATEWAY, status="error",
                           status_msg="upstream timeout", http_status=504, span_kind="server"))

    # payment-db 慢查询
    db_dur = svc_dur - random.randint(5, 30)
    db_span = gen_span_id()
    db_op = random.choice(["SELECT * FROM payments WHERE...", "INSERT INTO payments..."])
    spans.append(make_span(trace_id, db_span, svc_span, PAYMENT_DB, "",
                           db_op, base_time + timedelta(milliseconds=random.randint(5, 15)),
                           max(1, db_dur), peer_service=PAYMENT_SVC,
                           db_system="mysql", db_operation=db_op,
                           status="error", status_msg="query timeout", span_kind="client"))

    return spans


def gen_error_trace(base_time):
    """错误调用链: gateway → user-service → user-cache (connection refused)"""
    trace_id = gen_trace_id()
    spans = []
    ep = "/api/users"
    method = "GET"

    gw_dur = random.randint(100, 300)
    gw_span = gen_span_id()
    spans.append(make_span(trace_id, gw_span, "", GATEWAY, ep, method,
                           base_time, gw_dur, status="error",
                           status_msg="upstream error", http_status=502, span_kind="server"))

    svc_dur = gw_dur - random.randint(5, 15)
    svc_span = gen_span_id()
    svc_ep = random.choice(ENDPOINTS[USER_SVC])
    spans.append(make_span(trace_id, svc_span, gw_span, USER_SVC, svc_ep,
                           HTTP_METHODS[svc_ep], base_time + timedelta(milliseconds=random.randint(2, 8)),
                           svc_dur, peer_service=GATEWAY, status="error",
                           status_msg="cache connection refused", http_status=500, span_kind="server"))

    # user-cache span (失败)
    db_dur = random.randint(50, 100)
    db_span = gen_span_id()
    spans.append(make_span(trace_id, db_span, svc_span, USER_CACHE, "",
                           "GET session", base_time + timedelta(milliseconds=random.randint(5, 15)),
                           db_dur, peer_service=USER_SVC,
                           db_system="redis", db_operation="GET",
                           status="error", status_msg="ConnectionRefusedError: [Errno 111] Connection refused",
                           span_kind="client"))

    return spans


def gen_fast_trace(base_time):
    """快速调用链: gateway → inventory-service (30-80ms)"""
    trace_id = gen_trace_id()
    spans = []
    ep = random.choice(["/api/inventory"])
    method = "GET"

    gw_dur = random.randint(30, 80)
    gw_span = gen_span_id()
    spans.append(make_span(trace_id, gw_span, "", GATEWAY, ep, method,
                           base_time, gw_dur, span_kind="server"))

    svc_dur = gw_dur - random.randint(3, 10)
    svc_span = gen_span_id()
    svc_ep = random.choice(ENDPOINTS[INVENTORY_SVC])
    spans.append(make_span(trace_id, svc_span, gw_span, INVENTORY_SVC, svc_ep,
                           HTTP_METHODS[svc_ep], base_time + timedelta(milliseconds=random.randint(2, 5)),
                           svc_dur, peer_service=GATEWAY, span_kind="server"))

    return spans


def main():
    print("📊 注入 APM Demo 数据...")

    now = datetime.now()
    all_spans = []

    # 生成 2 小时的 trace 数据，每分钟 5-15 个 trace
    for t in range(120):
        base = now - timedelta(minutes=120 - t)
        num_traces = random.randint(5, 15)

        for _ in range(num_traces):
            ts = base + timedelta(seconds=random.randint(0, 59), milliseconds=random.randint(0, 999))
            r = random.random()

            if r < 0.65:  # 65% 正常
                all_spans.extend(gen_normal_trace(ts))
            elif r < 0.75:  # 10% 快速
                all_spans.extend(gen_fast_trace(ts))
            elif r < 0.90:  # 15% 慢调用（集中在 T+20 ~ T+50）
                if 20 <= t <= 50:
                    all_spans.extend(gen_slow_trace(ts))
                else:
                    all_spans.extend(gen_normal_trace(ts))
            else:  # 10% 错误（集中在 T+30 ~ T+50）
                if 30 <= t <= 50:
                    all_spans.extend(gen_error_trace(ts))
                else:
                    all_spans.extend(gen_normal_trace(ts))

    print(f"  生成 {len(all_spans)} 条 spans")

    # 批量写入 (每 1000 行一批，用 VALUES 格式)
    columns = list(all_spans[0].keys())

    def escape(v):
        if v is None:
            return 'NULL'
        s = str(v).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{s}'"

    for i in range(0, len(all_spans), 1000):
        batch = all_spans[i:i + 1000]
        values_list = []
        for row in batch:
            vals = ", ".join(escape(row[c]) for c in columns)
            values_list.append(f"({vals})")
        sql = f"INSERT INTO traces.spans ({', '.join(columns)}) VALUES {','.join(values_list)}"
        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(CLICKHOUSE_URL, data=sql.encode("utf-8"))
                if r.status_code != 200:
                    print(f"  ⚠️ 批量 {i}: {r.status_code} {r.text[:200]}")
                else:
                    print(f"  ✅ 批量 {i}: {len(batch)} rows")
        except Exception as e:
            print(f"  ⚠️ 异常: {e}")

    print(f"\n🎉 APM 数据注入完成！共 {len(all_spans)} 条 spans")

    # 统计
    with httpx.Client(timeout=10) as client:
        r = client.post(CLICKHOUSE_URL, data="""
            SELECT service_name, count() as spans,
                   round(avg(duration_ms), 1) as avg_ms,
                   round(quantile(0.99)(duration_ms), 1) as p99_ms,
                   round(countIf(status_code = 'error') * 100.0 / count(), 2) as err_rate
            FROM traces.spans
            WHERE start_time > now() - INTERVAL 3 HOUR
            GROUP BY service_name
            ORDER BY spans DESC
            FORMAT JSON
        """)
        if r.status_code == 200:
            print("\n📈 最近 3 小时 APM 统计:")
            for row in r.json().get("data", []):
                print(f"  {row['service_name']:20s} spans={row['spans']:>6}  avg={row['avg_ms']:>8}ms  p99={row['p99_ms']:>8}ms  err={row['err_rate']}%")


if __name__ == "__main__":
    main()
