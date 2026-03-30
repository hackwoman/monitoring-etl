"""
健康度计算引擎 — 核心计算逻辑。

支持两种健康度聚合方法：
1. weighted_avg: 按维度权重加权平均（主力）
2. children_avg: 取下游子实体健康评分平均值（业务层）
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def metric_value_to_score(value: float, thresholds: dict) -> int:
    """
    将指标值映射到 0-100 分。
    
    阈值定义示例：
    - {"warn": 70, "crit": 90}  → 值越大越差（CPU、内存等）
    - {"warn": 99, "crit": 95}  → 值越小越差（成功率等）
    
    规则：
    - warn < crit → 值越大越差，warn 以下=100分，crit 以上=0分
    - warn > crit → 值越小越差，warn 以上=100分，crit 以下=0分
    
    线性插值：warn 到 crit 之间 = 100 → 0 分
    """
    if value is None:
        return 50  # 无数据给中等分

    warn = thresholds.get("warn")
    crit = thresholds.get("crit")

    if warn is None and crit is None:
        # 无阈值，返回默认
        return 80

    if warn is not None and crit is not None:
        if warn < crit:
            # 值越大越差
            if value <= warn:
                return 100
            elif value >= crit:
                return 0
            else:
                return int(100 * (crit - value) / (crit - warn))
        else:
            # 值越小越差
            if value >= warn:
                return 100
            elif value <= crit:
                return 0
            else:
                return int(100 * (value - crit) / (warn - crit))

    # 只有 warn 或只有 crit
    threshold = warn if warn is not None else crit
    if warn is None:
        # 只有 crit，crit 是好/坏的边界
        if value >= crit:
            return 0
        return min(100, int(100 - value / crit * 50))
    else:
        # 只有 warn
        if value <= warn:
            return 100
        return max(0, int(100 - (value - warn) / warn * 50))


def calculate_weighted_avg(
    dimensions: list,
    metrics_data: dict,
    type_def_definition: dict,
) -> tuple:
    """
    weighted_avg 方法：按维度权重加权平均。
    
    Args:
        dimensions: [{"name": "latency", "metric": "http.server.request.duration.p99", "weight": 0.4}, ...]
        metrics_data: {"http.server.request.duration.p99": 150.5, "http.server.request.error_rate": 0.5, ...}
        type_def_definition: 完整的 type_def.definition（用于查找指标阈值）
    
    Returns:
        (health_score: int, health_detail: dict)
    """
    # 建立指标名 → 阈值的映射
    metric_thresholds = {}
    for m in type_def_definition.get("metrics", []):
        metric_thresholds[m["name"]] = m.get("thresholds", {})

    detail = {}
    total_weight = 0
    weighted_sum = 0

    for dim in dimensions:
        metric_name = dim.get("metric", "")
        weight = dim.get("weight", 0)
        dim_name = dim.get("name", metric_name)

        value = metrics_data.get(metric_name)
        thresholds = metric_thresholds.get(metric_name, {})

        score = metric_value_to_score(value, thresholds)

        detail[dim_name] = {
            "metric": metric_name,
            "value": value,
            "score": score,
            "weight": weight,
            "thresholds": thresholds,
        }

        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 80, detail

    health_score = int(weighted_sum / total_weight)
    return health_score, detail


def calculate_children_avg(
    entity_guid: str,
    child_health_scores: list,
) -> tuple:
    """
    children_avg 方法：取下游子实体健康评分平均值。
    
    Args:
        entity_guid: 当前实体 GUID
        child_health_scores: [85, 92, 55, ...] 子实体的 health_score 列表
    
    Returns:
        (health_score: int, health_detail: dict)
    """
    if not child_health_scores:
        return 80, {"method": "children_avg", "children": [], "reason": "no_children"}

    avg = sum(child_health_scores) / len(child_health_scores)
    return int(avg), {
        "method": "children_avg",
        "children_count": len(child_health_scores),
        "children_avg": round(avg, 1),
        "min_score": min(child_health_scores),
        "max_score": max(child_health_scores),
    }


def score_to_level(score: int) -> str:
    """健康评分 → 健康等级。"""
    if score >= 80:
        return "healthy"
    elif score >= 60:
        return "warning"
    elif score >= 30:
        return "critical"
    else:
        return "down"


def calculate_risk_score(
    health_score: int,
    biz_weight: float = 1.0,
    blast_radius: int = 0,
    propagation_hops: int = 0,
) -> int:
    """
    计算风险评分。
    
    风险 = 健康度差 × 业务权重 × 影响范围
    
    公式：
    risk = (100 - health_score) × biz_weight × (1 + blast_radius/5) × (1 + propagation_hops/3)
    
    最终归一化到 0-100。
    """
    health_penalty = 100 - health_score
    impact_factor = (1 + blast_radius / 5) * (1 + propagation_hops / 3)
    raw_risk = health_penalty * biz_weight * impact_factor

    # 归一化到 0-100（除以 2.5，更敏感）
    risk = min(100, int(raw_risk / 2.5))
    return risk


def calculate_entity_health(
    entity: dict,
    type_def: dict,
    metrics_data: dict,
    child_health_scores: Optional[list] = None,
) -> dict:
    """
    计算单个实体的健康度。
    
    Args:
        entity: {"guid": "...", "name": "...", "type_name": "...", ...}
        type_def: {"type_name": "...", "definition": {"health": {...}, "metrics": [...], ...}}
        metrics_data: {"metric.name": value, ...} 从 ClickHouse 查到的最新指标值
        child_health_scores: 子实体的 health_score 列表（用于 children_avg）
    
    Returns:
        {
            "health_score": 85,
            "health_level": "healthy",
            "health_detail": {...},
            "risk_score": 15,
        }
    """
    definition = type_def.get("definition", {})
    health_model = definition.get("health", {})

    if not health_model:
        # 无健康模型，给默认值
        return {
            "health_score": 80,
            "health_level": "healthy",
            "health_detail": {"method": "none", "reason": "no_health_model"},
            "risk_score": 20,
        }

    method = health_model.get("method", "weighted_avg")

    if method == "weighted_avg":
        dimensions = health_model.get("dimensions", [])
        if not dimensions:
            return {
                "health_score": 80,
                "health_level": "healthy",
                "health_detail": {"method": "weighted_avg", "reason": "no_dimensions"},
                "risk_score": 20,
            }
        score, detail = calculate_weighted_avg(dimensions, metrics_data, definition)

    elif method == "children_avg":
        score, detail = calculate_children_avg(
            entity.get("guid", ""),
            child_health_scores or [],
        )

    else:
        logger.warning(f"Unknown health method: {method}")
        score, detail = 80, {"method": method, "reason": "unknown_method"}

    level = score_to_level(score)
    risk = calculate_risk_score(score)

    return {
        "health_score": score,
        "health_level": level,
        "health_detail": detail,
        "risk_score": risk,
    }
