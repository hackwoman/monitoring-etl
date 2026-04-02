"""统一告警中心 API — 告警规则、告警实例、外部接入。"""

import uuid
import json
import hashlib
import logging
from typing import Optional, List
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_session
from app.models import AlertRule, AlertInstance, Entity

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alerts"])

CLICKHOUSE_URL = "http://47.93.61.196:8123"  # 生产环境从环境变量读


# ============================================================
# Pydantic Schemas
# ============================================================

class AlertRuleCreate(BaseModel):
    rule_name: str
    description: Optional[str] = None
    target_type: Optional[str] = None
    condition_type: str
    condition_expr: dict
    severity: str = "warning"
    eval_interval: int = 60
    eval_window: int = 300
    for_duration: int = 0
    notify_channels: list = Field(default_factory=list)


class AlertRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    condition_expr: Optional[dict] = None
    severity: Optional[str] = None


class SilenceRequest(BaseModel):
    duration_minutes: int = 60
    reason: Optional[str] = None


class AckRequest(BaseModel):
    ack_by: Optional[str] = None


class IngestPayload(BaseModel):
    """兼容 Prometheus AlertManager webhook 格式。"""
    source: Optional[str] = "prometheus"
    alerts: Optional[list] = None
    # 单条兼容
    labels: Optional[dict] = None
    annotations: Optional[dict] = None
    status: Optional[str] = None


# ============================================================
# Helper
# ============================================================

def _alert_to_dict(a: AlertInstance) -> dict:
    return {
        "alert_id": str(a.alert_id),
        "rule_id": str(a.rule_id),
        "entity_guid": str(a.entity_guid) if a.entity_guid else None,
        "entity_name": a.entity_name,
        "entity_type": a.entity_type,
        "status": a.status,
        "severity": a.severity,
        "title": a.title,
        "summary": a.summary,
        "fingerprint": a.fingerprint,
        "blast_radius": a.blast_radius,
        "affected_biz": a.affected_biz or [],
        "group_id": str(a.group_id) if a.group_id else None,
        "starts_at": a.starts_at.isoformat() if a.starts_at else None,
        "ends_at": a.ends_at.isoformat() if a.ends_at else None,
        "ack_at": a.ack_at.isoformat() if a.ack_at else None,
        "ack_by": a.ack_by,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _rule_to_dict(r: AlertRule) -> dict:
    return {
        "rule_id": str(r.rule_id),
        "rule_name": r.rule_name,
        "description": r.description,
        "rule_source": r.rule_source,
        "target_type": r.target_type,
        "condition_type": r.condition_type,
        "condition_expr": r.condition_expr,
        "severity": r.severity,
        "eval_interval": r.eval_interval,
        "eval_window": r.eval_window,
        "for_duration": r.for_duration,
        "is_enabled": r.is_enabled,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _make_fingerprint(labels: dict) -> str:
    raw = json.dumps(labels, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


# ============================================================
# 告警规则 CRUD
# ============================================================

@router.get("/alerts/rules")
async def list_alert_rules(
    is_enabled: Optional[bool] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """列出告警规则。"""
    query = select(AlertRule)
    if is_enabled is not None:
        query = query.where(AlertRule.is_enabled == is_enabled)
    query = query.order_by(AlertRule.created_at)
    result = await session.execute(query)
    rules = result.scalars().all()
    return {"total": len(rules), "items": [_rule_to_dict(r) for r in rules]}


@router.post("/alerts/rules", status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    session: AsyncSession = Depends(get_session),
):
    """创建告警规则。"""
    rule = AlertRule(
        rule_name=body.rule_name,
        description=body.description,
        rule_source="custom",
        target_type=body.target_type,
        condition_type=body.condition_type,
        condition_expr=body.condition_expr,
        severity=body.severity,
        eval_interval=body.eval_interval,
        eval_window=body.eval_window,
        for_duration=body.for_duration,
        notify_channels=body.notify_channels,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return _rule_to_dict(rule)


@router.get("/alerts/rules/{rule_id}")
async def get_alert_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取规则详情。"""
    rule = await session.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    return _rule_to_dict(rule)


@router.put("/alerts/rules/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    body: AlertRuleUpdate,
    session: AsyncSession = Depends(get_session),
):
    """更新规则。"""
    rule = await session.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    for key, val in body.model_dump(exclude_unset=True).items():
        setattr(rule, key, val)
    await session.commit()
    await session.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/alerts/rules/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
):
    """删除规则。"""
    rule = await session.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    await session.delete(rule)
    await session.commit()


# ============================================================
# 告警实例
# ============================================================

@router.get("/alerts")
async def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    entity_guid: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """列出告警实例。"""
    query = select(AlertInstance)
    count_query = select(func.count(AlertInstance.alert_id))
    conditions = []

    if status:
        conditions.append(AlertInstance.status == status)
    if severity:
        conditions.append(AlertInstance.severity == severity)
    if entity_guid:
        conditions.append(AlertInstance.entity_guid == entity_guid)

    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total = await session.scalar(count_query)
    query = query.order_by(AlertInstance.starts_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    alerts = result.scalars().all()

    return {
        "total": total or 0,
        "items": [_alert_to_dict(a) for a in alerts],
        "limit": limit,
        "offset": offset,
    }


@router.get("/alerts/stats")
async def alert_stats(
    session: AsyncSession = Depends(get_session),
):
    """告警统计。"""
    # 按状态统计
    status_query = select(
        AlertInstance.status,
        func.count(AlertInstance.alert_id)
    ).group_by(AlertInstance.status)
    result = await session.execute(status_query)
    by_status = {row[0]: row[1] for row in result.fetchall()}

    # 按严重度统计 firing 告警
    sev_query = select(
        AlertInstance.severity,
        func.count(AlertInstance.alert_id)
    ).where(AlertInstance.status == "firing").group_by(AlertInstance.severity)
    result = await session.execute(sev_query)
    by_severity = {row[0]: row[1] for row in result.fetchall()}

    return {
        "by_status": by_status,
        "by_severity": by_severity,
        "total_firing": by_status.get("firing", 0),
        "total_resolved": by_status.get("resolved", 0),
    }


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: str,
    session: AsyncSession = Depends(get_session),
):
    """告警详情。"""
    alert = await session.get(AlertInstance, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return _alert_to_dict(alert)


@router.post("/alerts/{alert_id}/ack")
async def ack_alert(
    alert_id: str,
    body: AckRequest = None,
    session: AsyncSession = Depends(get_session),
):
    """确认告警。"""
    alert = await session.get(AlertInstance, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = "acknowledged"
    alert.ack_at = datetime.utcnow()
    alert.ack_by = body.ack_by if body else None
    await session.commit()
    return _alert_to_dict(alert)


@router.post("/alerts/{alert_id}/silence")
async def silence_alert(
    alert_id: str,
    body: SilenceRequest,
    session: AsyncSession = Depends(get_session),
):
    """静默告警。"""
    from datetime import timedelta
    alert = await session.get(AlertInstance, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = "silenced"
    alert.silence_at = datetime.utcnow()
    alert.silence_until = datetime.utcnow() + timedelta(minutes=body.duration_minutes)
    await session.commit()
    return _alert_to_dict(alert)


# ============================================================
# 外部告警接入
# ============================================================

@router.post("/alerts/ingest")
async def ingest_alerts(
    payload: IngestPayload,
    session: AsyncSession = Depends(get_session),
):
    """
    接收外部告警（兼容 Prometheus AlertManager webhook 格式）。

    支持批量（alerts 数组）和单条格式。
    """
    from app.models import AlertInstance

    alerts_raw = payload.alerts or []
    # 兼容单条
    if not alerts_raw and payload.labels:
        alerts_raw = [{
            "status": payload.status or "firing",
            "labels": payload.labels,
            "annotations": payload.annotations or {},
            "startsAt": datetime.utcnow().isoformat() + "Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }]

    # 加载实体用于匹配
    entities_result = await session.execute(
        select(Entity).where(Entity.status == "active")
    )
    entities = [_entity_to_dict_simple(e) for e in entities_result.scalars().all()]
    entity_by_name = {e["name"].lower(): e for e in entities}
    entity_by_ip = {}
    for e in entities:
        ip = (e.get("attributes") or {}).get("ip")
        if ip:
            entity_by_ip[ip] = e

    processed = 0
    for alert_data in alerts_raw:
        labels = alert_data.get("labels", {})
        annotations = alert_data.get("annotations", {})

        # 实体匹配
        entity = _match_entity(labels, entity_by_name, entity_by_ip, entities)
        entity_guid = entity["guid"] if entity else None
        entity_name = entity["name"] if entity else labels.get("instance", "unknown")
        entity_type = entity["type_name"] if entity else "unknown"

        # fingerprint
        fingerprint = _make_fingerprint(labels)
        severity = labels.get("severity", "warning")
        status = "resolved" if alert_data.get("status") == "resolved" else "firing"
        title = annotations.get("summary", labels.get("alertname", "Unknown Alert"))

        # 查重
        existing_q = await session.execute(
            select(AlertInstance).where(AlertInstance.fingerprint == fingerprint)
        )
        existing = existing_q.scalar_one_or_none()

        if existing:
            if status == "resolved" and existing.status == "firing":
                existing.status = "resolved"
                existing.ends_at = datetime.utcnow()
        elif status == "firing":
            alert = AlertInstance(
                entity_guid=entity_guid,
                entity_name=entity_name,
                entity_type=entity_type,
                status="firing",
                severity=severity,
                title=title,
                summary=annotations.get("description", ""),
                fingerprint=fingerprint,
            )
            session.add(alert)

        processed += 1

    await session.commit()
    return {"status": "ok", "processed": processed}


def _entity_to_dict_simple(e: Entity) -> dict:
    return {
        "guid": str(e.guid),
        "type_name": e.type_name,
        "name": e.name,
        "attributes": e.attributes or {},
    }


def _match_entity(labels: dict, entity_by_name: dict, entity_by_ip: dict, entities: list) -> Optional[dict]:
    """匹配 Prometheus labels 到 CMDB entity。"""
    # 1. instance
    instance = labels.get("instance", "")
    if instance:
        host_part = instance.split(":")[0]
        if host_part in entity_by_ip:
            return entity_by_ip[host_part]
        if host_part.lower() in entity_by_name:
            return entity_by_name[host_part.lower()]

    # 2. service / host / hostname
    for key in ("service", "host", "hostname"):
        val = labels.get(key, "")
        if val and val.lower() in entity_by_name:
            return entity_by_name[val.lower()]

    # 3. job 映射
    job = labels.get("job", "")
    job_type_map = {
        "node-exporter": "Host",
        "mysqld-exporter": "MySQL",
        "redis-exporter": "Redis",
    }
    mapped_type = job_type_map.get(job)
    if mapped_type:
        instance_host = instance.split(":")[0] if instance else ""
        for e in entities:
            if e["type_name"] == mapped_type:
                if instance_host and (instance_host == e["name"] or instance_host == (e.get("attributes") or {}).get("ip")):
                    return e
                elif not instance_host:
                    return e

    return None


# ============================================================
# 实体关联告警
# ============================================================

@router.get("/cmdb/entities/{entity_guid}/alerts")
async def entity_alerts(
    entity_guid: str,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """查询实体关联的告警。"""
    conditions = [AlertInstance.entity_guid == entity_guid]
    if status:
        conditions.append(AlertInstance.status == status)

    query = select(AlertInstance).where(and_(*conditions)).order_by(
        AlertInstance.starts_at.desc()
    ).limit(limit)
    result = await session.execute(query)
    alerts = result.scalars().all()

    return {"total": len(alerts), "items": [_alert_to_dict(a) for a in alerts]}
