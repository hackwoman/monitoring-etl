#!/usr/bin/env python3
"""
Demo 告警数据制造脚本。

模拟 2 小时级联故障场景，使用 Prometheus AlertManager webhook 标准格式。

用法:
  python scripts/demo_alert_factory.py              # 注入全部数据
  python scripts/demo_alert_factory.py --metrics     # 仅注入指标
  python scripts/demo_alert_factory.py --alerts      # 仅注入告警
  python scripts/demo_alert_factory.py --clean       # 清除 demo 数据
"""

import os
import sys
import json
import time
import uuid
import argparse
from datetime import datetime, timedelta, timezone

import httpx

# ---- 配置 ----
CMDB_API = os.getenv("CMDB_API_URL", "http://8.146.232.9:8000")
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://47.93.61.196:8123")
ALERT_INGEST_URL = f"{CMDB_API}/api/v1/alerts/ingest"

# Demo 实体
DB_MASTER = "db-master"
ORDER_DB = "order-db"
ORDER_SVC = "order-service"
GATEWAY = "gateway"
ONLINE_PAY = "在线支付"


def inject_metrics():
    """注入 ClickHouse 指标数据，模拟 db-master CPU 异常曲线。"""
    print("📊 注入指标数据（模拟日志量曲线）...")

    now = datetime.now()
    rows = []

    for t in range(120):  # 2 小时，每分钟一个点
        ts = now - timedelta(minutes=120 - t)

        # CPU 曲线: 正常(45-55) → 爬升 → 92% → 恢复
        if t < 15:
            cpu = 45 + (t % 10)
        elif t < 45:
            cpu = 45 + (t - 15) * 1.5 + (t % 5)
        elif t < 60:
            cpu = 92 - (t - 45) * 2 + (t % 5)
        else:
            cpu = 50 + (t % 10)
        cpu = min(99, max(30, cpu))

        # P99 延迟 (DB 异常时飙升)
        if 25 < t < 50:
            p99 = 800 + (t - 25) * 80
        else:
            p99 = 100 + (t % 30)
        p99 = min(3000, max(50, p99))

        # 错误率
        if 30 < t < 48:
            err_rate = 2 + (t - 30) * 0.5
        else:
            err_rate = 0.1 + (t % 3) * 0.1
        err_rate = min(15, max(0, err_rate))

        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

        # 模拟 db-master 的日志（host_name）
        level = "error" if err_rate > 3 else "info"
        rows.append(
            f"('{ts_str}', '{DB_MASTER}', '{DB_MASTER}', 'system', '{level}', "
            f"'CPU usage: {cpu:.1f}%', '')"
        )

        # 模拟 order-service 的日志
        svc_level = "error" if err_rate > 2 else "info"
        rows.append(
            f"('{ts_str}', '{ORDER_SVC}', 'app-01', 'order-service', '{svc_level}', "
            f"'request processed p99={p99:.0f}ms', '')"
        )

        # 模拟 gateway 的日志
        rows.append(
            f"('{ts_str}', '{GATEWAY}', 'web-01', 'gateway', '{svc_level}', "
            f"'proxy request p99={p99 * 0.8:.0f}ms', '')"
        )

    # 批量写入 logs.log_entries (每 300 行一批)
    for i in range(0, len(rows), 300):
        batch = rows[i:i + 300]
        sql = f"""
        INSERT INTO logs.log_entries (timestamp, host_name, service_name, source, level, message, body)
        VALUES {','.join(batch)}
        """
        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(CLICKHOUSE_URL, data=sql.encode("utf-8"))
                if r.status_code != 200:
                    print(f"  ⚠️ 批量写入失败: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"  ⚠️ 写入异常: {e}")

    print(f"  ✅ 注入 {len(rows)} 条日志数据")


def inject_alerts():
    """通过 /alerts/ingest 推送 Prometheus 格式告警。"""
    print("🚨 注入告警数据...")

    now = datetime.utcnow()

    # 时间线 (相对于 demo 开始的分钟数)
    events = [
        # T+20: db-master CPU 过高
        (20, "firing", {
            "alertname": "HighCPU",
            "instance": "10.0.1.30:9100",
            "job": "node-exporter",
            "severity": "critical",
            "host": DB_MASTER,
        }, "CPU usage > 90% on db-master", "CPU usage is 92.3% (threshold 90%)"),

        # T+25: order-db 连接数高
        (25, "firing", {
            "alertname": "MySQLConnectionsHigh",
            "instance": "10.0.1.30:9104",
            "job": "mysqld-exporter",
            "severity": "error",
            "service": ORDER_DB,
        }, "MySQL active connections > 90%", "order-db connections usage rate: 88.2%"),

        # T+32: order-service P99 延迟高
        (32, "firing", {
            "alertname": "ServiceHighLatency",
            "instance": "10.0.1.20:9090",
            "service": ORDER_SVC,
            "severity": "error",
        }, "Service P99 latency > 2000ms", "order-service P99: 2560ms (threshold 2000ms)"),

        # T+38: gateway 错误率高
        (38, "firing", {
            "alertname": "ServiceHighErrorRate",
            "instance": "10.0.1.10:9090",
            "service": GATEWAY,
            "severity": "critical",
        }, "Service error rate > 5%", "gateway error rate: 8.2% (threshold 5%)"),

        # T+45: db-master CPU 恢复
        (45, "resolved", {
            "alertname": "HighCPU",
            "instance": "10.0.1.30:9100",
            "job": "node-exporter",
            "severity": "critical",
            "host": DB_MASTER,
        }, "CPU usage recovered", "CPU usage is now 65%"),

        # T+50: order-service 恢复
        (50, "resolved", {
            "alertname": "ServiceHighLatency",
            "instance": "10.0.1.20:9090",
            "service": ORDER_SVC,
            "severity": "error",
        }, "Service latency recovered", "order-service P99: 120ms"),

        # T+55: gateway 恢复
        (55, "resolved", {
            "alertname": "ServiceHighErrorRate",
            "instance": "10.0.1.10:9090",
            "service": GATEWAY,
            "severity": "critical",
        }, "Service error rate recovered", "gateway error rate: 0.3%"),

        # T+55: order-db 恢复
        (55, "resolved", {
            "alertname": "MySQLConnectionsHigh",
            "instance": "10.0.1.30:9104",
            "job": "mysqld-exporter",
            "severity": "error",
            "service": ORDER_DB,
        }, "MySQL connections recovered", "order-db connections: 52%"),
    ]

    with httpx.Client(timeout=15) as client:
        for offset_min, status, labels, summary, description in events:
            starts_at = (now - timedelta(minutes=120 - offset_min)).isoformat() + "Z"
            ends_at = (now - timedelta(minutes=120 - offset_min)).isoformat() + "Z" if status == "resolved" else "0001-01-01T00:00:00Z"

            payload = {
                "source": "prometheus",
                "alerts": [{
                    "status": status,
                    "labels": labels,
                    "annotations": {
                        "summary": summary,
                        "description": description,
                    },
                    "startsAt": starts_at,
                    "endsAt": ends_at,
                    "generatorURL": f"http://prometheus:9090/graph?g0.expr={labels['alertname']}",
                }]
            }

            try:
                r = client.post(ALERT_INGEST_URL, json=payload)
                emoji = "🔴" if status == "firing" else "🟢"
                print(f"  {emoji} T+{offset_min}m {status}: {labels['alertname']} → {labels.get('service', labels.get('host', '?'))}")
            except Exception as e:
                print(f"  ⚠️ 推送失败: {e}")

            time.sleep(0.1)  # 避免太快

    print(f"  ✅ 注入 {len(events)} 条告警事件")


def clean_demo_data():
    """清除 demo 数据。"""
    print("🧹 清除 demo 数据...")

    # 清除 ClickHouse 指标
    try:
        with httpx.Client(timeout=15) as client:
            client.post(CLICKHOUSE_URL, data="TRUNCATE TABLE metrics.points")
            print("  ✅ 指标数据已清除")
    except Exception as e:
        print(f"  ⚠️ 清除指标失败: {e}")

    # 清除 PostgreSQL 告警实例
    print("  ℹ️ 告警实例需手动清除: DELETE FROM alert_instance;")


def main():
    parser = argparse.ArgumentParser(description="Demo 告警数据制造")
    parser.add_argument("--metrics", action="store_true", help="仅注入指标")
    parser.add_argument("--alerts", action="store_true", help="仅注入告警")
    parser.add_argument("--clean", action="store_true", help="清除 demo 数据")
    args = parser.parse_args()

    if args.clean:
        clean_demo_data()
        return

    do_all = not (args.metrics or args.alerts)

    if do_all or args.metrics:
        inject_metrics()

    if do_all or args.alerts:
        inject_alerts()

    print("\n🎉 Demo 数据注入完成！")
    print(f"   查看告警: {CMDB_API}/api/v1/alerts")
    print(f"   查看统计: {CMDB_API}/api/v1/alerts/stats")
    print(f"   前端页面: {CMDB_API.replace(':8000', ':3000')}/alerts")


if __name__ == "__main__":
    main()
