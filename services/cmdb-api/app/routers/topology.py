"""CMDB 拓扑 API — 横向调用链 + 纵向承载链下钻。

Phase 3: 2026-04-23
- GET /topology/logical    → 横向业务应用调用链（过滤基础设施层）
- GET /topology/drilldown/{entity_id} → 纵向承载关系（容器→进程→服务器）
"""
import uuid, json
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from app.database import get_session
from app.models import Entity, Relationship, EntityTypeDef

router = APIRouter()

CLICKHOUSE_URL = "http://47.93.61.196:8123"

# ============================================================
# Schema
# ============================================================

class LogicalNode(BaseModel):
    guid: str
    name: str
    type_name: str
    display_name: str
    category: str
    health_score: int | None
    health_level: str | None
    biz_service: str | None
    attributes: dict = Field(default_factory=dict)
    alert_count: int = 0
    # 核心性能指标（从 ClickHouse 实时查询）
    key_metrics: dict = Field(default_factory=dict)


class LogicalEdge(BaseModel):
    from_guid: str
    to_guid: str
    relation_type: str
    call_type: str = "sync"
    confidence: float = 1.0
    # 调用统计（从 ClickHouse 查询）
    call_count: int | None = None
    avg_latency_ms: float | None = None
    error_rate: float | None = None


class LogicalTopologyResponse(BaseModel):
    nodes: list[LogicalNode]
    edges: list[LogicalEdge]
    total_nodes: int
    total_edges: int
    layers: list[str]


class DrilldownNode(BaseModel):
    guid: str
    name: str
    type_name: str
    display_name: str
    category: str
    health_score: int | None
    health_level: str | None
    risk_score: int | None
    attributes: dict = Field(default_factory=dict)
    key_metrics: dict = Field(default_factory=dict)
    alert_count: int = 0
    relation_type: str | None = None
    children: list["DrilldownNode"] = []


DrilldownNode.model_rebuild()


class DrilldownResponse(BaseModel):
    root: DrilldownNode
    max_depth: int
    visited_count: int


# ============================================================
# Constants
# ============================================================

INFRA_LAYER_TYPES = {"Host", "NetworkDevice", "IP"}
VERTICAL_REL_TYPES = {
    "runs_on", "hosts", "contains", "scheduled_on",
    "allocated_to", "includes", "depends_on",
}
HORIZONTAL_REL_TYPES = {"calls", "async_calls", "depends_on", "forwards_to"}

# ClickHouse 指标名称映射（metric_name → key_metrics key）
METRIC_MAPPING = {
    "http.server.request.qps": "qps",
    "http.server.request.error_rate": "error_rate",
    "http.server.request.duration.p50": "latency",
    "http.server.request.duration.p99": "latency_p99",
    "xhr.request.count": "qps",
    "xhr.request.error_rate": "error_rate",
    "xhr.timing.total": "latency",
}


# ============================================================
# ClickHouse 查询
# ============================================================

async def query_clickhouse(sql: str) -> list[dict]:
    """对 ClickHouse 执行 SQL，返回 JSON 解析后的 rows。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                CLICKHOUSE_URL,
                params={"database": "default", "query": sql, "default_format": "JSON"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
    except Exception as e:
        print(f"[CH query error] {e}")
        return []


async def get_node_metrics_from_ch(entity_names: list[str]) -> dict[str, dict]:
    """从 ClickHouse 查询节点最近 5 分钟的指标聚合。

    Returns:
        { entity_name: { "qps": float, "error_rate": float, "latency": float, ... } }
    """
    if not entity_names:
        return {}

    names_csv = "', '".join(entity_names)
    sql = f"""
    SELECT
        entity_name,
        metric_name,
        avg(value) as avg_val,
        max(value) as max_val
    FROM metrics_timeseries
    WHERE timestamp >= now() - INTERVAL 5 MINUTE
      AND entity_name IN ('{names_csv}')
      AND metric_name IN (
          'http.server.request.qps',
          'http.server.request.error_rate',
          'http.server.request.duration.p50',
          'http.server.request.duration.p99',
          'xhr.request.count',
          'xhr.request.error_rate',
          'xhr.timing.total'
      )
    GROUP BY entity_name, metric_name
    FORMAT JSON
    """
    rows = await query_clickhouse(sql)

    result: dict[str, dict] = {name: {} for name in entity_names}
    for row in rows:
        name = row.get("entity_name", "")
        metric = row.get("metric_name", "")
        avg_val = row.get("avg_val")
        if name not in result:
            result[name] = {}
        key = METRIC_MAPPING.get(metric, metric)
        result[name][key] = round(avg_val, 3) if avg_val is not None else None

    return result


async def get_edge_metrics_from_ch(
    edge_entity_names: list[tuple[str, str]],
    entity_name_map: dict[str, Entity],
) -> dict[tuple[str, str], dict]:
    """从 ClickHouse 查询边的聚合指标。

    通过 caller=from_entity, callee=to_entity 匹配 traces/apm 调用链表。
    这里用 entity_name 做模糊匹配，实际应该走 records 表的调用链。
    """
    if not edge_entity_names:
        return {}

    # 尝试从 metrics_timeseries 找关联指标（通过 entity_name 匹配）
    # 策略：对每个 (caller, callee) 找 caller 的 qps/error_rate/latency
    result: dict[tuple[str, str], dict] = {}

    # 收集所有涉及的 entity_name
    all_names = list(set([n for pair in edge_entity_names for n in pair]))
    names_csv = "', '".join(all_names)

    sql = f"""
    SELECT
        entity_name,
        metric_name,
        avg(value) as avg_val
    FROM metrics_timeseries
    WHERE timestamp >= now() - INTERVAL 5 MINUTE
      AND entity_name IN ('{names_csv}')
      AND metric_name IN ('http.server.request.qps', 'http.server.request.error_rate',
                          'http.server.request.duration.p50')
    GROUP BY entity_name, metric_name
    FORMAT JSON
    """
    rows = await query_clickhouse(sql)

    # 转换为 entity_name → metrics
    name_metrics: dict[str, dict] = {}
    for row in rows:
        name = row.get("entity_name", "")
        metric = row.get("metric_name", "")
        avg_val = row.get("avg_val")
        name_metrics.setdefault(name, {})[METRIC_MAPPING.get(metric, metric)] = (
            round(avg_val, 3) if avg_val is not None else None
        )

    # 为每条边填充 caller 的指标（作为边的指标代理）
    for from_name, to_name in edge_entity_names:
        caller_metrics = name_metrics.get(from_name, {})
        if caller_metrics:
            result[(from_name, to_name)] = caller_metrics

    return result


# ============================================================
# Helpers
# ============================================================

async def _get_type_def(session: AsyncSession, type_name: str) -> Optional[EntityTypeDef]:
    return await session.get(EntityTypeDef, type_name)


async def _entity_to_logical_node(
    e: Entity,
    type_def: Optional[EntityTypeDef],
    ch_metrics: dict,
    alert_count: int = 0,
) -> LogicalNode:
    display_name = type_def.display_name if type_def else e.type_name
    category = type_def.category if type_def else "custom"
    # 优先用 ClickHouse 指标，fallback 到 health_detail
    key_metrics = ch_metrics.get(e.name, {}) if ch_metrics else {}
    if e.health_detail and isinstance(e.health_detail, dict) and not key_metrics:
        for dim, info in e.health_detail.items():
            if isinstance(info, dict) and "value" in info:
                key_metrics[dim] = info["value"]

    return LogicalNode(
        guid=str(e.guid),
        name=e.name,
        type_name=e.type_name,
        display_name=display_name,
        category=category,
        health_score=e.health_score,
        health_level=e.health_level,
        biz_service=e.biz_service,
        attributes=e.attributes or {},
        alert_count=alert_count,
        key_metrics=key_metrics,
    )


async def _build_drill_node(
    session: AsyncSession,
    e: Entity,
    rel_type_from_parent: Optional[str],
    depth: int,
    max_depth: int,
    visited: set,
) -> Optional[DrilldownNode]:
    if e.guid in visited or depth > max_depth:
        return None
    visited.add(e.guid)

    type_def = await _get_type_def(session, e.type_name)
    key_metrics = {}
    if e.health_detail and isinstance(e.health_detail, dict):
        for dim, info in e.health_detail.items():
            if isinstance(info, dict) and "value" in info:
                key_metrics[dim] = info["value"]

    node = DrilldownNode(
        guid=str(e.guid),
        name=e.name,
        type_name=e.type_name,
        display_name=type_def.display_name if type_def else e.type_name,
        category=type_def.category if type_def else "custom",
        health_score=e.health_score,
        health_level=e.health_level,
        risk_score=e.risk_score,
        attributes=e.attributes or {},
        key_metrics=key_metrics,
        alert_count=0,
        relation_type=rel_type_from_parent,
        children=[],
    )

    vertical_rels = await session.execute(
        select(Relationship).where(
            and_(
                Relationship.is_active == True,
                Relationship.end1_guid == e.guid,
                Relationship.dimension == "vertical",
                Relationship.type_name.in_(VERTICAL_REL_TYPES),
            )
        )
    )
    for rel in vertical_rels.scalars().all():
        child_entity = await session.get(Entity, rel.end2_guid)
        if child_entity:
            child_node = await _build_drill_node(
                session, child_entity, rel.type_name, depth + 1, max_depth, visited
            )
            if child_node:
                node.children.append(child_node)

    return node


# ============================================================
# Routes
# ============================================================

@router.get("/topology/logical", response_model=LogicalTopologyResponse)
async def get_logical_topology(
    biz_service: Optional[str] = Query(None, description="业务服务名称过滤"),
    include_types: Optional[str] = Query(None, description="逗号分隔的类型列表"),
    session: AsyncSession = Depends(get_session),
):
    """获取横向业务应用调用链拓扑（默认视图）。

    过滤掉 Host/NetworkDevice/IP 等基础设施节点。
    展示 Business -> Application -> Service -> Middleware -> Data 的完整调用链。
    关系线区分 sync（实线）和 async（虚线）。
    节点和边的性能指标从 ClickHouse 实时查询（最近5分钟）。
    """
    exclude_types = set(INFRA_LAYER_TYPES)

    query = select(Entity).where(Entity.status == "active")
    if include_types:
        explicit = set(t.strip() for t in include_types.split(","))
        query = query.where(Entity.type_name.in_(explicit))
    else:
        query = query.where(~Entity.type_name.in_(exclude_types))

    result = await session.execute(query)
    entities = result.scalars().all()

    nodes = []
    entity_map: dict[uuid.UUID, Entity] = {}
    for e in entities:
        if biz_service and e.biz_service != biz_service:
            continue
        entity_map[e.guid] = e

    # ── 从 ClickHouse 批量查询节点指标 ──
    entity_names = [e.name for e in entity_map.values()]
    ch_node_metrics = await get_node_metrics_from_ch(entity_names)

    for e in entity_map.values():
        type_def = await _get_type_def(session, e.type_name)
        nodes.append(await _entity_to_logical_node(e, type_def, ch_node_metrics))

    # ── 横向关系 ──
    horiz_result = await session.execute(
        select(Relationship).where(
            and_(
                Relationship.is_active == True,
                Relationship.dimension == "horizontal",
                Relationship.type_name.in_(HORIZONTAL_REL_TYPES),
            )
        )
    )
    rels = horiz_result.scalars().all()

    node_guids = {uuid.UUID(n.guid) for n in nodes}
    entity_name_by_guid: dict[uuid.UUID, str] = {e.guid: e.name for e in entity_map.values()}

    # ── 从 ClickHouse 查边指标 ──
    edge_name_pairs = [
        (entity_name_by_guid.get(rel.end1_guid, ""), entity_name_by_guid.get(rel.end2_guid, ""))
        for rel in rels
        if rel.end1_guid in node_guids and rel.end2_guid in node_guids
    ]
    ch_edge_metrics = await get_edge_metrics_from_ch(edge_name_pairs, entity_map)

    edges = []
    for rel in rels:
        if rel.end1_guid not in node_guids or rel.end2_guid not in node_guids:
            continue
        from_name = entity_name_by_guid.get(rel.end1_guid, "")
        to_name = entity_name_by_guid.get(rel.end2_guid, "")
        edge_key = (from_name, to_name)
        edge_ch = ch_edge_metrics.get(edge_key, {})

        edges.append(LogicalEdge(
            from_guid=str(rel.end1_guid),
            to_guid=str(rel.end2_guid),
            relation_type=rel.type_name,
            call_type=rel.call_type or "sync",
            confidence=rel.confidence or 1.0,
            call_count=int(edge_ch.get("qps")) if edge_ch.get("qps") else None,
            avg_latency_ms=edge_ch.get("latency"),
            error_rate=edge_ch.get("error_rate"),
        ))

    layers = sorted(set(n.category for n in nodes))

    return LogicalTopologyResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=len(nodes),
        total_edges=len(edges),
        layers=layers,
    )


@router.get("/topology/drilldown/{entity_id}", response_model=DrilldownResponse)
async def get_topology_drilldown(
    entity_id: str,
    max_depth: int = Query(4, ge=1, le=6),
    session: AsyncSession = Depends(get_session),
):
    """获取实体的纵向承载链下钻视图。"""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")

    visited = set()
    root = await _build_drill_node(session, entity, None, 0, max_depth, visited)
    if not root:
        raise HTTPException(404, "Unable to build drilldown tree")

    return DrilldownResponse(root=root, max_depth=max_depth, visited_count=len(visited))


@router.get("/topology/logical/summary")
async def get_logical_topology_summary(
    session: AsyncSession = Depends(get_session),
):
    """获取横向拓扑的统计摘要。"""
    from sqlalchemy import func
    exclude_types = set(INFRA_LAYER_TYPES)

    total_result = await session.execute(
        select(func.count(Entity.guid)).where(
            and_(Entity.status == "active", ~Entity.type_name.in_(exclude_types))
        )
    )
    total = total_result.scalar() or 0

    type_result = await session.execute(
        select(Entity.type_name, func.count(Entity.guid))
        .where(and_(Entity.status == "active", ~Entity.type_name.in_(exclude_types)))
        .group_by(Entity.type_name)
    )
    type_counts = dict(type_result.all())

    edge_result = await session.execute(
        select(func.count(Relationship.guid)).where(
            and_(
                Relationship.is_active == True,
                Relationship.dimension == "horizontal",
                Relationship.type_name.in_(HORIZONTAL_REL_TYPES),
            )
        )
    )
    call_edge_count = edge_result.scalar() or 0

    return {
        "total_logical_entities": total,
        "type_distribution": type_counts,
        "total_call_edges": call_edge_count,
    }
