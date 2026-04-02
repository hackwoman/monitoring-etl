"""
外部告警接收器。

兼容 Prometheus AlertManager webhook 格式。
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("alert-engine.ingest")

# Prometheus severity → 我们的 severity 映射
SEVERITY_MAP = {
    "critical": "critical",
    "error": "error",
    "warning": "warning",
    "info": "info",
    "none": "info",
}


def parse_prometheus_alerts(payload: dict) -> list:
    """
    解析 Prometheus AlertManager webhook 格式。

    支持单条和批量（alerts 数组）。
    """
    alerts = payload.get("alerts", [])

    # 兼容单条格式（没有 alerts 数组）
    if not alerts and "labels" in payload:
        alerts = [payload]

    parsed = []
    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        # 提取 severity（Prometheus 用 labels.severity）
        severity = SEVERITY_MAP.get(
            labels.get("severity", "warning"),
            "warning"
        )

        # 状态映射
        prom_status = alert.get("status", "firing")
        if prom_status == "resolved":
            status = "resolved"
        else:
            status = "firing"

        # 生成 fingerprint
        fp_raw = json.dumps({"labels": labels}, sort_keys=True)
        fingerprint = hashlib.md5(fp_raw.encode()).hexdigest()

        parsed.append({
            "source": payload.get("source", "prometheus"),
            "external_id": alert.get("fingerprint", fingerprint),
            "status": status,
            "severity": severity,
            "labels": labels,
            "title": annotations.get("summary", labels.get("alertname", "Unknown Alert")),
            "summary": annotations.get("description", ""),
            "starts_at": alert.get("startsAt"),
            "ends_at": alert.get("endsAt"),
            "generator_url": alert.get("generatorURL", ""),
            "fingerprint": fingerprint,
        })

    return parsed


def parse_grafana_alerts(payload: dict) -> list:
    """兼容 Grafana webhook 格式。"""
    # Grafana 格式与 Prometheus 类似但字段略有不同
    alerts = payload.get("alerts", [])
    if not alerts and "title" in payload:
        # Grafana 单条告警
        return [{
            "source": "grafana",
            "status": "firing" if payload.get("state") == "alerting" else "resolved",
            "severity": payload.get("tags", {}).get("severity", "warning"),
            "labels": payload.get("tags", {}),
            "title": payload.get("title", "Grafana Alert"),
            "summary": payload.get("message", ""),
            "starts_at": payload.get("startedAt"),
            "ends_at": payload.get("endedAt"),
            "fingerprint": hashlib.md5(payload.get("title", "").encode()).hexdigest(),
        }]
    return parse_prometheus_alerts({"alerts": alerts, "source": "grafana"})
