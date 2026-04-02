"""
统一告警引擎 — 规则评估器。

加载 alert_rule，逐条评估，触发/恢复告警实例。
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("alert-engine.evaluator")

CLICKHOUSE_URL = "http://localhost:8123"  # 容器内访问，会被环境变量覆盖


def make_fingerprint(rule_id: str, entity_guid: str, severity: str) -> str:
    """生成告警去重指纹。"""
    raw = f"{rule_id}:{entity_guid}:{severity}"
    return hashlib.md5(raw.encode()).hexdigest()


def query_clickhouse_metric(
    metric_name: str,
    entity_name: str,
    entity_type: str,
    window_seconds: int = 300,
    ch_url: str = CLICKHOUSE_URL,
) -> Optional[float]:
    """从 ClickHouse 查询指定实体的指标最新值。"""
    try:
        with httpx.Client(timeout=10) as client:
            # 根据实体类型构建查询
            if entity_type == "Service":
                sql = f"""
                SELECT round(avg(
                    CASE '{metric_name}'
                        WHEN 'http.server.request.error_rate' THEN
                            countIf(level = 'error') * 100.0 / greatest(count(), 1)
                        WHEN 'http.server.request.duration.p99' THEN
                            quantile(0.99)(duration_ms)
                        ELSE 0
                    END
                ), 2) as value
                FROM logs.log_entries
                WHERE service_name = '{entity_name}'
                  AND timestamp > now() - INTERVAL {window_seconds} SECOND
                FORMAT JSON
                """
            elif entity_type == "Host":
                # 主机指标从日志量间接推算
                sql = f"""
                SELECT round(count() * 100.0 / greatest({window_seconds}, 1), 2) as value
                FROM logs.log_entries
                WHERE host_name = '{entity_name}'
                  AND timestamp > now() - INTERVAL {window_seconds} SECOND
                FORMAT JSON
                """
            else:
                return None

            r = client.post(ch_url, data=sql)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data and data[0].get("value") is not None:
                    return float(data[0]["value"])
    except Exception as e:
        logger.warning(f"ClickHouse query failed for {entity_name}.{metric_name}: {e}")
    return None


def evaluate_threshold_rule(
    rule: dict,
    entities: list,
    ch_url: str = CLICKHOUSE_URL,
) -> list:
    """评估阈值类规则，返回触发的 (entity, condition_result) 列表。"""
    triggered = []
    condition = rule["condition_expr"]
    metric = condition.get("metric")
    operator = condition.get("operator", ">")
    threshold = condition.get("value", 0)
    window = rule.get("eval_window", 300)
    target_type = rule.get("target_type")

    for entity in entities:
        if target_type and entity["type_name"] != target_type:
            continue

        value = query_clickhouse_metric(
            metric_name=metric,
            entity_name=entity["name"],
            entity_type=entity["type_name"],
            window_seconds=window,
            ch_url=ch_url,
        )

        if value is None:
            continue

        fired = False
        if operator == ">" and value > threshold:
            fired = True
        elif operator == ">=" and value >= threshold:
            fired = True
        elif operator == "<" and value < threshold:
            fired = True
        elif operator == "<=" and value <= threshold:
            fired = True

        if fired:
            triggered.append({
                "entity": entity,
                "metric": metric,
                "value": value,
                "threshold": threshold,
                "operator": operator,
            })

    return triggered


def evaluate_health_change_rule(
    rule: dict,
    entities: list,
    previous_states: dict,
) -> list:
    """评估健康度变更规则。"""
    triggered = []
    condition = rule["condition_expr"]
    from_level = condition.get("from_level")
    to_level = condition.get("to_level")

    for entity in entities:
        prev_level = previous_states.get(str(entity["guid"]))
        curr_level = entity.get("health_level")

        if prev_level == from_level and curr_level == to_level:
            triggered.append({
                "entity": entity,
                "from_level": from_level,
                "to_level": to_level,
                "health_score": entity.get("health_score"),
            })

    return triggered


def evaluate_absence_rule(
    rule: dict,
    entities: list,
    ch_url: str = CLICKHOUSE_URL,
) -> list:
    """评估缺失类规则（指标不存在/为零持续 N 秒）。"""
    triggered = []
    condition = rule["condition_expr"]
    metric = condition.get("metric")
    absent_for = condition.get("absent_for", 300)
    threshold = condition.get("threshold", 0)
    target_type = rule.get("target_type")

    for entity in entities:
        if target_type and entity["type_name"] != target_type:
            continue

        value = query_clickhouse_metric(
            metric_name=metric,
            entity_name=entity["name"],
            entity_type=entity["type_name"],
            window_seconds=absent_for,
            ch_url=ch_url,
        )

        if value is None or value <= threshold:
            triggered.append({
                "entity": entity,
                "metric": metric,
                "value": value or 0,
                "absent_for": absent_for,
            })

    return triggered
