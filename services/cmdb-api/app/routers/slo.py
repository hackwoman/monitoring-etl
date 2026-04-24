"""SLO API — 服务水平目标和错误预算管理。

功能：
1. SLO 达成率计算
2. 错误预算计算和消耗追踪
3. SLO 告警（预算消耗过快）
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_session
from app.models import Entity, EntityTypeDef

logger = logging.getLogger(__name__)

router = APIRouter(tags=["slo"])

CLICKHOUSE_URL = "http://47.93.61.196:8123"


# ============================================================
# 数据模型
# ============================================================

class SLOStatus(BaseModel):
    """SLO 状态"""
    name: str
    display: str
    sli: str
    target: float
    current: float
    unit: str
    comparison: str
    status: str  # ok, warning, critical
    achievement_rate: float  # 达成率 0-100%
    weight: float = 1.0  # 权重


class ErrorBudget(BaseModel):
    """错误预算"""
    total: float  # 总预算（百分比）
    consumed: float  # 已消耗
    remaining: float  # 剩余
    burn_rate: float  # 消耗速度（倍数）
    status: str  # ok, warning, frozen
    days_remaining: Optional[float] = None  # 预计剩余天数


class SLOReport(BaseModel):
    """SLO 报告"""
    entity_guid: str
    entity_name: str
    entity_type: str
    window_days: int
    objectives: List[SLOStatus]
    error_budget: ErrorBudget
    overall_status: str
    updated_at: str


# ============================================================
# SLO 计算逻辑
# ============================================================

def _calculate_achievement_rate(current: float, target: float, comparison: str) -> float:
    """计算 SLO 达成率。"""
    if comparison == "gte":  # 大于等于（如可用性）
        if current >= target:
            return 100.0
        return (current / target) * 100
    elif comparison == "lte":  # 小于等于（如延迟、错误率）
        if current <= target:
            return 100.0
        if target == 0:
            return 0.0
        return (target / current) * 100
    return 0.0


def _calculate_error_budget(slo_objectives: List[SLOStatus], window_days: int) -> ErrorBudget:
    """计算错误预算。
    
    错误预算 = 1 - SLO 目标值
    例: SLO = 99.9% → 错误预算 = 0.1%
    """
    # 计算综合 SLO 目标（加权平均）
    total_weight = sum(obj.target for obj in slo_objectives if obj.comparison == "gte")
    weighted_slo = 99.9  # 默认值
    
    # 找到可用性 SLO
    availability_obj = next((obj for obj in slo_objectives if obj.name == "availability"), None)
    if availability_obj:
        weighted_slo = availability_obj.target
    
    # 错误预算 = 100% - SLO
    total_budget = 100 - weighted_slo  # 如 SLO=99.9% → 预算=0.1%
    
    # 计算已消耗（基于当前 SLI 值）
    consumed = 0.0
    for obj in slo_objectives:
        if obj.current > obj.target and obj.comparison == "gte":
            # 可用性低于目标
            consumed += (obj.target - obj.current) * obj.weight
        elif obj.current > obj.target and obj.comparison == "lte":
            # 延迟/错误率高于目标
            consumed += ((obj.current - obj.target) / obj.target * 100) * obj.weight
    
    consumed = max(0, min(consumed, total_budget))
    remaining = max(0, total_budget - consumed)
    
    # 计算消耗速度（相对于正常速度）
    # 正常速度 = total_budget / window_days
    daily_budget = total_budget / window_days if window_days > 0 else total_budget
    burn_rate = consumed / daily_budget if daily_budget > 0 else 0
    
    # 状态判断
    if remaining <= 0:
        status = "frozen"
    elif burn_rate > 3:  # 消耗速度超过3倍
        status = "warning"
    else:
        status = "ok"
    
    # 预计剩余天数
    days_remaining = None
    if burn_rate > 0 and remaining > 0:
        days_remaining = remaining / (consumed / window_days if window_days > 0 else consumed)
    
    return ErrorBudget(
        total=round(total_budget, 4),
        consumed=round(consumed, 4),
        remaining=round(remaining, 4),
        burn_rate=round(burn_rate, 2),
        status=status,
        days_remaining=round(days_remaining, 1) if days_remaining else None,
    )


def _get_status_from_achievement(achievement_rate: float) -> str:
    """根据达成率判断状态。"""
    if achievement_rate >= 100:
        return "ok"
    elif achievement_rate >= 95:
        return "warning"
    else:
        return "critical"


# ============================================================
# API 端点
# ============================================================

@router.get("/slo/{entity_guid}")
async def get_entity_slo(
    entity_guid: str,
    window_days: int = Query(30, description="计算窗口（天）"),
    session: AsyncSession = Depends(get_session),
):
    """获取实体的 SLO 报告。"""
    import uuid
    try:
        eid = uuid.UUID(entity_guid)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")
    
    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")
    
    # 获取类型定义中的 SLO 配置
    type_def = await session.get(EntityTypeDef, entity.type_name)
    if not type_def:
        raise HTTPException(404, "Type definition not found")
    
    slo_config = (type_def.definition or {}).get("slo", {})
    objectives_config = slo_config.get("objectives", [])
    
    if not objectives_config:
        return {
            "entity_guid": str(entity.guid),
            "entity_name": entity.name,
            "entity_type": entity.type_name,
            "message": "SLO not configured for this entity type",
            "objectives": [],
        }
    
    # 获取实体当前的指标值
    attributes = entity.attributes or {}
    health_detail = entity.health_detail or {}
    
    # 计算每个 SLO 目标的达成情况
    objectives = []
    for obj_config in objectives_config:
        sli_name = obj_config.get("sli", "")
        target = obj_config.get("target", 0)
        comparison = obj_config.get("comparison", "gte")
        
        # 从 health_detail 或 attributes 获取当前值
        current = None
        if isinstance(health_detail, dict):
            for key, value in health_detail.items():
                if sli_name in key or obj_config.get("name") in key:
                    if isinstance(value, dict):
                        current = value.get("value") or value.get("score")
                    else:
                        current = value
                    break
        
        # 如果没有找到，使用模拟值
        if current is None:
            # 从健康度推算
            health_score = entity.health_score or 80
            if comparison == "gte":
                current = target * (health_score / 100)
            else:
                current = target * (1 + (100 - health_score) / 100)
        
        # 计算达成率
        achievement_rate = _calculate_achievement_rate(current, target, comparison)
        status = _get_status_from_achievement(achievement_rate)
        
        objectives.append(SLOStatus(
            name=obj_config.get("name", ""),
            display=obj_config.get("display", ""),
            sli=sli_name,
            target=target,
            current=round(current, 2),
            unit=obj_config.get("unit", ""),
            comparison=comparison,
            status=status,
            achievement_rate=round(achievement_rate, 2),
            weight=obj_config.get("weight", 1.0),
        ))
    
    # 计算错误预算
    error_budget = _calculate_error_budget(objectives, window_days)
    
    # 整体状态
    if error_budget.status == "frozen":
        overall_status = "critical"
    elif any(obj.status == "critical" for obj in objectives):
        overall_status = "critical"
    elif any(obj.status == "warning" for obj in objectives):
        overall_status = "warning"
    else:
        overall_status = "healthy"
    
    return SLOReport(
        entity_guid=str(entity.guid),
        entity_name=entity.name,
        entity_type=entity.type_name,
        window_days=window_days,
        objectives=objectives,
        error_budget=error_budget,
        overall_status=overall_status,
        updated_at=datetime.utcnow().isoformat(),
    )


@router.get("/slo")
async def list_slo_overview(
    entity_type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """获取所有实体的 SLO 概览。"""
    query = select(Entity)
    if entity_type:
        query = query.where(Entity.type_name == entity_type)
    
    result = await session.execute(query.limit(50))
    entities = result.scalars().all()
    
    reports = []
    for entity in entities:
        try:
            report = await get_entity_slo(str(entity.guid), 30, session)
            if isinstance(report, SLOReport):
                reports.append(report)
        except:
            continue
    
    # 统计
    total = len(reports)
    healthy = len([r for r in reports if r.overall_status == "healthy"])
    warning = len([r for r in reports if r.overall_status == "warning"])
    critical = len([r for r in reports if r.overall_status == "critical"])
    
    return {
        "total": total,
        "healthy": healthy,
        "warning": warning,
        "critical": critical,
        "reports": [r.dict() for r in reports],
    }


@router.get("/error-budget/{entity_guid}")
async def get_error_budget(
    entity_guid: str,
    window_days: int = Query(30),
    session: AsyncSession = Depends(get_session),
):
    """获取实体的错误预算详情。"""
    report = await get_entity_slo(entity_guid, window_days, session)
    if isinstance(report, SLOReport):
        return report.error_budget
    return report
