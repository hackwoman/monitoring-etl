"""实体聚合统计 API — 按类型汇总健康分布、告警数等。"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_session
from app.models import Entity, AlertInstance, Relationship

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])


@router.get("/cmdb/stats")
async def entity_stats(
    type_name: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """
    实体聚合统计。

    返回：总数、健康分布、关联告警数。
    """
    conditions = [Entity.status == "active"]
    if type_name:
        conditions.append(Entity.type_name == type_name)

    # 总数 + 健康分布
    query = select(
        Entity.health_level,
        func.count(Entity.guid),
        func.avg(Entity.health_score),
    ).where(and_(*conditions)).group_by(Entity.health_level)
    result = await session.execute(query)
    rows = result.fetchall()

    total = 0
    health_dist = {}
    score_sum = 0
    score_count = 0
    for level, count, avg_score in rows:
        level_key = level or "unknown"
        health_dist[level_key] = count
        total += count
        if avg_score is not None:
            score_sum += avg_score * count
            score_count += count

    avg_score = round(score_sum / score_count, 1) if score_count > 0 else None

    # 活跃告警数
    alert_conditions = [AlertInstance.status == "firing"]
    if type_name:
        alert_conditions.append(AlertInstance.entity_type == type_name)
    alert_query = select(func.count(AlertInstance.alert_id)).where(and_(*alert_conditions))
    firing_alerts = await session.scalar(alert_query) or 0

    # 按严重度的告警分布
    sev_query = select(
        AlertInstance.severity,
        func.count(AlertInstance.alert_id),
    ).where(and_(*alert_conditions)).group_by(AlertInstance.severity)
    sev_result = await session.execute(sev_query)
    alerts_by_severity = {row[0]: row[1] for row in sev_result.fetchall()}

    return {
        "type_name": type_name,
        "total": total,
        "avg_health_score": avg_score,
        "health_distribution": health_dist,
        "firing_alerts": firing_alerts,
        "alerts_by_severity": alerts_by_severity,
    }
