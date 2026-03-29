"""Overview API — 全局概览：健康度分布 + 告警统计 + 资源规模。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import Entity, EntityTypeDef

router = APIRouter()


@router.get("/overview")
async def get_overview(
    session: AsyncSession = Depends(get_session),
):
    """全局概览 — 一句话：全局健不健康？"""
    # 资源规模
    size_q = select(
        Entity.type_name,
        func.count(Entity.guid).label("count"),
    ).where(Entity.status == "active").group_by(Entity.type_name)
    size_result = await session.execute(size_q)
    resource_size = {row.type_name: row.count for row in size_result}
    total_entities = sum(resource_size.values())

    # 健康度分布
    health_q = select(
        func.coalesce(Entity.health_level, "unknown"),
        func.count(Entity.guid),
    ).where(Entity.status == "active").group_by(Entity.health_level)
    health_result = await session.execute(health_q)
    health_dist = {row[0]: row[1] for row in health_result}

    # 异常实体 (health_level not healthy)
    anomaly_q = select(Entity).where(
        and_(
            Entity.status == "active",
            Entity.health_level.in_(["warning", "critical", "down"]),
        )
    ).order_by(
        func.coalesce(Entity.risk_score, 0).desc()
    ).limit(10)
    anomaly_result = await session.execute(anomaly_q)
    anomalies = []
    for e in anomaly_result.scalars().all():
        anomalies.append({
            "guid": str(e.guid),
            "name": e.name,
            "type_name": e.type_name,
            "health_score": e.health_score,
            "health_level": e.health_level,
            "risk_score": e.risk_score,
            "biz_service": e.biz_service,
        })

    # 业务健康度
    biz_q = select(
        Entity.biz_service,
        func.avg(Entity.health_score).label("avg_health"),
        func.count(Entity.guid).label("resource_count"),
    ).where(
        and_(
            Entity.status == "active",
            Entity.biz_service.isnot(None),
        )
    ).group_by(Entity.biz_service)
    biz_result = await session.execute(biz_q)
    biz_health = []
    for row in biz_result:
        biz_health.append({
            "name": row.biz_service,
            "health_score": round(row.avg_health) if row.avg_health else None,
            "resource_count": row.resource_count,
        })

    return {
        "total_entities": total_entities,
        "resource_size": resource_size,
        "health_distribution": health_dist,
        "anomaly_entities": anomalies,
        "business_health": biz_health,
    }


@router.get("/data-quality")
async def get_data_quality(
    session: AsyncSession = Depends(get_session),
):
    """数据质量概览 — 借鉴蓝鲸 PDCA。"""
    from app.models import DataCheckRule, DataQualitySnapshot

    # Get latest snapshot
    snapshot_q = select(DataQualitySnapshot).order_by(
        DataQualitySnapshot.snapshot_time.desc()
    ).limit(1)
    snapshot = await session.scalar(snapshot_q)

    # Get rule count
    rule_count = await session.scalar(select(func.count(DataCheckRule.rule_id)))

    # Entity stats
    total = await session.scalar(
        select(func.count(Entity.guid)).where(Entity.status == "active")
    )
    with_biz = await session.scalar(
        select(func.count(Entity.guid)).where(
            and_(Entity.status == "active", Entity.biz_service.isnot(None))
        )
    )
    with_health = await session.scalar(
        select(func.count(Entity.guid)).where(
            and_(Entity.status == "active", Entity.health_score.isnot(None))
        )
    )

    return {
        "latest_snapshot": {
            "snapshot_time": snapshot.snapshot_time.isoformat() if snapshot else None,
            "overall_score": snapshot.overall_score if snapshot else None,
            "total_rules": snapshot.total_rules if snapshot else rule_count,
            "passed_rules": snapshot.passed_rules if snapshot else None,
            "failed_rules": snapshot.failed_rules if snapshot else None,
            "issues": snapshot.issues if snapshot else [],
        } if snapshot else None,
        "entity_stats": {
            "total": total or 0,
            "with_biz_service": with_biz or 0,
            "with_health_score": with_health or 0,
            "biz_coverage": round((with_biz or 0) / max(total or 1, 1) * 100, 1),
            "health_coverage": round((with_health or 0) / max(total or 1, 1) * 100, 1),
        },
        "rule_count": rule_count or 0,
    }
