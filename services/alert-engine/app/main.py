"""
统一告警引擎 — 主循环 + Webhook 接收服务。

功能:
1. 定时评估 alert_rule，触发/恢复告警
2. 接收外部告警（Prometheus/Grafana webhook）
3. 写入 ClickHouse records + PostgreSQL alert_instance
4. 级联影响分析

用法:
  python -m app.main              # 持续运行（默认 60s 间隔）
  python -m app.main --once       # 单次评估后退出
"""

import os
import sys
import uuid
import json
import time
import logging
import argparse
import threading
from datetime import datetime, timezone

import httpx
import psycopg2
import uvicorn
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("alert-engine")

# ---- 配置 ----
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cmdb",
)
CLICKHOUSE_URL = os.getenv(
    "CLICKHOUSE_URL",
    "http://localhost:8123",
)
INTERVAL = int(os.getenv("ALERT_ENGINE_INTERVAL", "60"))
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8003"))


def get_pg_conn():
    return psycopg2.connect(DATABASE_URL)


# ============================================================
# Webhook 接收服务
# ============================================================

webhook_app = FastAPI(title="Alert Webhook Receiver")


@webhook_app.get("/health")
async def webhook_health():
    return {"status": "ok", "service": "alert-engine-webhook"}


@webhook_app.post("/webhook/prometheus")
async def receive_prometheus(request: Request):
    """接收 Prometheus AlertManager webhook。"""
    from app.ingest import parse_prometheus_alerts
    from app.matcher import match_entity

    body = await request.json()
    alerts = parse_prometheus_alerts(body)
    logger.info(f"📥 收到 {len(alerts)} 条 Prometheus 告警")

    pg = get_pg_conn()
    try:
        entities = load_entities(pg)
        processed = 0
        for alert in alerts:
            # 匹配实体
            entity = match_entity(alert["labels"], entities)
            entity_guid = str(entity["guid"]) if entity else None
            entity_name = entity["name"] if entity else alert["labels"].get("instance", "unknown")
            entity_type = entity["type_name"] if entity else "unknown"

            # 写入 records (ClickHouse)
            record_id = str(uuid.uuid4())
            write_record_to_ch(record_id, alert, entity_guid, entity_name, entity_type)

            # 写入/更新 alert_instance (PostgreSQL)
            upsert_alert_instance(pg, alert, entity_guid, entity_name, entity_type, record_id)
            processed += 1

        pg.commit()
        logger.info(f"  ✅ 处理 {processed} 条告警")
        return {"status": "ok", "processed": processed}
    except Exception as e:
        logger.error(f"  ❌ 处理失败: {e}")
        pg.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        pg.close()


@webhook_app.post("/webhook/grafana")
async def receive_grafana(request: Request):
    """接收 Grafana webhook（格式与 Prometheus 类似）。"""
    from app.ingest import parse_grafana_alerts
    body = await request.json()
    alerts = parse_grafana_alerts(body)
    # 复用 Prometheus 处理逻辑
    return await receive_prometheus.__wrapped__(alerts)


# ============================================================
# 数据访问辅助
# ============================================================

def load_entities(pg):
    """加载所有 active 实体。"""
    with pg.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT guid, type_name, name, attributes, labels, health_level, health_score FROM entity WHERE status = 'active'")
        return [dict(row) for row in cur.fetchall()]


def load_alert_rules(pg):
    """加载所有启用的告警规则。"""
    with pg.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM alert_rule WHERE is_enabled = true ORDER BY created_at")
        return [dict(row) for row in cur.fetchall()]


def load_firing_alerts(pg):
    """加载所有 firing 状态的告警实例。"""
    with pg.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM alert_instance WHERE status = 'firing'")
        return [dict(row) for row in cur.fetchall()]


def load_relationships(pg):
    """加载所有关系。"""
    with pg.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT guid, type_name,
                   COALESCE(from_guid::text, end1_guid::text) as from_guid,
                   COALESCE(to_guid::text, end2_guid::text) as to_guid
            FROM relationship WHERE is_active = true
        """)
        return [dict(row) for row in cur.fetchall()]


def write_record_to_ch(record_id: str, alert: dict, entity_guid: str, entity_name: str, entity_type: str):
    """写入 ClickHouse records 表。"""
    try:
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        entity_guid_sql = f"'{entity_guid}'" if entity_guid and entity_guid != "None" else "toUUID('00000000-0000-0000-0000-000000000000')"
        gid = alert.get("group_id")
        group_id_sql = f"'{gid}'" if gid and gid != "None" else "toUUID('00000000-0000-0000-0000-000000000000')"

        # 用参数化方式避免转义问题：直接 JSON 写入
        values = {
            "record_id": record_id,
            "record_type": "alert",
            "source": alert.get("source", "alert-engine"),
            "timestamp": now_str,
            "entity_guid": entity_guid if entity_guid and entity_guid != "None" else "00000000-0000-0000-0000-000000000000",
            "entity_name": entity_name or "",
            "entity_type": entity_type or "",
            "severity": alert.get("severity", "warning"),
            "title": alert.get("title", ""),
            "content": json.dumps(alert, ensure_ascii=False),
            "fingerprint": alert.get("fingerprint", ""),
            "group_id": gid if gid and gid != "None" else "00000000-0000-0000-0000-000000000000",
            "alert_status": alert.get("status", "firing"),
            "alert_rule_id": "00000000-0000-0000-0000-000000000000",
            "alert_starts_at": now_str,
            "alert_ends_at": now_str,
        }

        sql = "INSERT INTO records (record_id, record_type, source, timestamp, entity_guid, entity_name, entity_type, severity, title, content, fingerprint, group_id, alert_status, alert_rule_id, alert_starts_at, alert_ends_at) FORMAT JSONEachRow"
        with httpx.Client(timeout=10) as client:
            client.post(
                f"{CLICKHOUSE_URL}?query={httpx.QueryParams({'query': sql}).get('query')}",
                content=json.dumps(values).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
    except Exception as e:
        logger.warning(f"写入 ClickHouse 失败: {e}")


def upsert_alert_instance(pg, alert: dict, entity_guid: str, entity_name: str, entity_type: str, record_id: str):
    """创建或更新 PostgreSQL alert_instance。"""
    fingerprint = alert.get("fingerprint", "")

    with pg.cursor(cursor_factory=RealDictCursor) as cur:
        # 查重
        cur.execute("SELECT alert_id, status FROM alert_instance WHERE fingerprint = %s", (fingerprint,))
        existing = cur.fetchone()

        if existing:
            if alert["status"] == "resolved" and existing["status"] == "firing":
                cur.execute("""
                    UPDATE alert_instance SET status = 'resolved', ends_at = now(), updated_at = now()
                    WHERE alert_id = %s
                """, (str(existing["alert_id"]),))
                logger.info(f"  🟢 告警恢复: {entity_name}")
            elif alert["status"] == "firing" and existing["status"] == "firing":
                cur.execute("""
                    UPDATE alert_instance SET updated_at = now() WHERE alert_id = %s
                """, (str(existing["alert_id"]),))
        else:
            if alert["status"] == "firing":
                # 级联归并
                from app.impact import find_group_id
                relationships = load_relationships(pg)
                firing_map = {}
                for fa in load_firing_alerts(pg):
                    if fa.get("entity_guid"):
                        firing_map[str(fa["entity_guid"])] = str(fa.get("group_id", fa["alert_id"]))
                group_id = find_group_id(entity_guid, firing_map, relationships) if entity_guid else None

                cur.execute("""
                    INSERT INTO alert_instance
                    (rule_id, entity_guid, entity_name, entity_type, status, severity, title, summary, fingerprint, record_id, group_id, starts_at)
                    VALUES (%s, %s, %s, %s, 'firing', %s, %s, %s, %s, %s, %s, now())
                """, (
                    "00000000-0000-0000-0000-000000000000",  # 外部告警无规则ID
                    entity_guid or None,
                    entity_name,
                    entity_type,
                    alert.get("severity", "warning"),
                    alert.get("title", ""),
                    alert.get("summary", ""),
                    fingerprint,
                    record_id,
                    group_id,
                ))
                logger.info(f"  🔴 新告警: {entity_name} — {alert.get('title', '')}")


def _escape(s: str) -> str:
    """简单 SQL 转义（ClickHouse INSERT 用）。"""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


# ============================================================
# 规则评估主循环
# ============================================================

def run_evaluation():
    """单次规则评估。"""
    from app.evaluator import (
        evaluate_threshold_rule,
        evaluate_health_change_rule,
        evaluate_absence_rule,
        make_fingerprint,
    )

    logger.info("⚡ 告警评估开始...")

    pg = get_pg_conn()
    try:
        rules = load_alert_rules(pg)
        entities = load_entities(pg)
        relationships = load_relationships(pg)

        if not rules:
            logger.info("  无启用规则，跳过")
            return

        # 加载上次健康度状态（用于 health_change 检测）
        # 简化：用 entity 当前 health_level 作为"上次"（完整方案需持久化）
        previous_states = {str(e["guid"]): e.get("health_level") for e in entities}

        total_fired = 0
        total_resolved = 0

        for rule in rules:
            condition_type = rule["condition_type"]
            target_type = rule.get("target_type")

            # 过滤目标实体
            if target_type:
                target_entities = [e for e in entities if e["type_name"] == target_type]
            else:
                target_entities = entities

            # 评估
            triggered = []
            if condition_type == "threshold":
                triggered = evaluate_threshold_rule(rule, target_entities, CLICKHOUSE_URL)
            elif condition_type == "health_change":
                triggered = evaluate_health_change_rule(rule, target_entities, previous_states)
            elif condition_type == "absence":
                triggered = evaluate_absence_rule(rule, target_entities, CLICKHOUSE_URL)
            # composite 和 external 类型暂由 ingest 模块处理

            for t in triggered:
                entity = t["entity"]
                fingerprint = make_fingerprint(
                    str(rule["rule_id"]),
                    str(entity["guid"]),
                    rule["severity"],
                )

                # 检查是否已存在
                with pg.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT alert_id, status FROM alert_instance WHERE fingerprint = %s", (fingerprint,))
                    existing = cur.fetchone()

                    if existing and existing["status"] == "firing":
                        # 已存在 firing，更新时间
                        cur.execute("UPDATE alert_instance SET updated_at = now() WHERE alert_id = %s",
                                    (str(existing["alert_id"]),))
                    elif not existing:
                        # 新告警
                        record_id = str(uuid.uuid4())
                        value_str = ""
                        if "value" in t:
                            value_str = f" (当前值: {t['value']}{t.get('operator', '')}{t.get('threshold', '')})"

                        # 级联归并
                        from app.impact import find_group_id
                        firing_map = {}
                        for fa in load_firing_alerts(pg):
                            if fa.get("entity_guid"):
                                firing_map[str(fa["entity_guid"])] = str(fa.get("group_id", fa["alert_id"]))
                        group_id = find_group_id(str(entity["guid"]), firing_map, relationships)

                        cur.execute("""
                            INSERT INTO alert_instance
                            (rule_id, entity_guid, entity_name, entity_type, status, severity, title, summary, fingerprint, record_id, group_id, starts_at)
                            VALUES (%s, %s, %s, %s, 'firing', %s, %s, %s, %s, %s, %s, now())
                        """, (
                            str(rule["rule_id"]),
                            str(entity["guid"]),
                            entity["name"],
                            entity["type_name"],
                            rule["severity"],
                            f"{rule['rule_name']}: {entity['name']}",
                            f"{rule.get('description', '')}{value_str}",
                            fingerprint,
                            record_id,
                            str(group_id) if group_id else None,
                        ))

                        # 写 ClickHouse record
                        alert_record = {
                            "source": "alert-engine",
                            "severity": rule["severity"],
                            "title": f"{rule['rule_name']}: {entity['name']}",
                            "status": "firing",
                            "fingerprint": fingerprint,
                            "group_id": str(group_id) if group_id else str(uuid.uuid4()),
                        }
                        write_record_to_ch(record_id, alert_record, str(entity["guid"]), entity["name"], entity["type_name"])

                        total_fired += 1
                        logger.info(f"  🔴 触发: {rule['rule_name']} → {entity['name']}")

                    else:
                        # 已 resolved，重新触发
                        cur.execute("""
                            UPDATE alert_instance SET status = 'firing', starts_at = now(), ends_at = NULL, updated_at = now()
                            WHERE alert_id = %s
                        """, (str(existing["alert_id"]),))
                        total_fired += 1

        # 恢复检测：之前 firing 但现在不再触发的
        firing_alerts = load_firing_alerts(pg)
        active_fingerprints = set()
        for rule in rules:
            target_type = rule.get("target_type")
            if target_type:
                target_entities = [e for e in entities if e["type_name"] == target_type]
            else:
                target_entities = entities

            condition_type = rule["condition_type"]
            if condition_type == "threshold":
                triggered = evaluate_threshold_rule(rule, target_entities, CLICKHOUSE_URL)
            elif condition_type == "absence":
                triggered = evaluate_absence_rule(rule, target_entities, CLICKHOUSE_URL)
            else:
                continue

            for t in triggered:
                fp = make_fingerprint(str(rule["rule_id"]), str(t["entity"]["guid"]), rule["severity"])
                active_fingerprints.add(fp)

        for fa in firing_alerts:
            if fa["fingerprint"] and fa["fingerprint"] not in active_fingerprints:
                # 仅恢复规则触发的告警（非外部推送的）
                rule_id_str = str(fa.get("rule_id", ""))
                if rule_id_str != "00000000-0000-0000-0000-000000000000":
                    with pg.cursor() as cur:
                        cur.execute("""
                            UPDATE alert_instance SET status = 'resolved', ends_at = now(), updated_at = now()
                            WHERE alert_id = %s
                        """, (str(fa["alert_id"]),))
                    total_resolved += 1
                    logger.info(f"  🟢 恢复: {fa.get('entity_name', '?')}")

        pg.commit()
        logger.info(f"  ✅ 评估完成: +{total_fired} firing, +{total_resolved} resolved")

    except Exception as e:
        logger.error(f"  ❌ 评估失败: {e}")
        pg.rollback()
    finally:
        pg.close()


def main():
    parser = argparse.ArgumentParser(description="统一告警引擎")
    parser.add_argument("--once", action="store_true", help="单次评估后退出")
    parser.add_argument("--interval", type=int, default=INTERVAL, help="评估间隔（秒）")
    args = parser.parse_args()

    if args.once:
        run_evaluation()
        return

    # 启动 webhook 服务（后台线程）
    logger.info(f"🌐 Webhook 服务启动，端口 {WEBHOOK_PORT}")
    wh_thread = threading.Thread(
        target=uvicorn.run,
        args=(webhook_app,),
        kwargs={"host": "0.0.0.0", "port": WEBHOOK_PORT, "log_level": "warning"},
        daemon=True,
    )
    wh_thread.start()

    # 主循环
    logger.info(f"⚡ 告警引擎启动，间隔 {args.interval}s")
    while True:
        try:
            run_evaluation()
        except Exception as e:
            logger.error(f"评估异常: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
