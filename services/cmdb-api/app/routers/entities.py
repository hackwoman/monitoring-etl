"""CMDB Entity API routes - Phase 2 认知层增强版。"""
import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import Entity, Relationship, EntityTypeDef

router = APIRouter()


# ---- Pydantic Schemas ----

class EntityCreate(BaseModel):
    type_name: str
    name: str
    qualified_name: Optional[str] = None
    attributes: dict = Field(default_factory=dict)
    labels: dict = Field(default_factory=dict)
    source: str = "manual"
    biz_service: Optional[str] = None


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    attributes: Optional[dict] = None
    labels: Optional[dict] = None
    status: Optional[str] = None
    biz_service: Optional[str] = None
    health_score: Optional[int] = None
    health_level: Optional[str] = None
    health_detail: Optional[dict] = None
    risk_score: Optional[int] = None


class RelationshipCreate(BaseModel):
    type_name: str
    end2_guid: str
    attributes: dict = Field(default_factory=dict)
    source: str = "manual"
    confidence: float = 1.0
    dimension: str = "vertical"


# ---- Helper ----

def _entity_to_dict(e: Entity) -> dict:
    return {
        "guid": str(e.guid),
        "type_name": e.type_name,
        "name": e.name,
        "qualified_name": e.qualified_name,
        "attributes": e.attributes or {},
        "labels": e.labels or {},
        "status": e.status,
        "source": e.source,
        "biz_service": e.biz_service,
        "health_score": e.health_score,
        "health_level": e.health_level,
        "health_detail": e.health_detail,
        "risk_score": e.risk_score,
        "propagation_hops": e.propagation_hops,
        "blast_radius": e.blast_radius,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _validate_attributes(attributes: dict, attr_defs: list) -> list[str]:
    """
    校验属性是否符合 type_def.definition.attributes 的元数据定义。

    返回错误列表，空列表表示通过。
    """
    errors = []
    if not attr_defs:
        return errors

    # 建立 key → 定义 的映射
    def_map = {d["key"]: d for d in attr_defs if isinstance(d, dict) and "key" in d}

    # 检查必填字段
    for key, defn in def_map.items():
        if defn.get("required", False):
            val = attributes.get(key)
            if val is None or val == "":
                errors.append(f"属性 '{defn.get('name', key)}' ({key}) 为必填项")

    # 检查类型和约束
    for key, val in attributes.items():
        if val is None:
            continue
        defn = def_map.get(key)
        if not defn:
            continue  # 未定义的属性，允许（自由扩展）

        expected_type = defn.get("type", "string")
        if expected_type == "int":
            try:
                int_val = int(val)
                if "min" in defn and int_val < defn["min"]:
                    errors.append(f"属性 '{key}' 值 {int_val} 小于最小值 {defn['min']}")
                if "max" in defn and int_val > defn["max"]:
                    errors.append(f"属性 '{key}' 值 {int_val} 大于最大值 {defn['max']}")
            except (ValueError, TypeError):
                errors.append(f"属性 '{key}' 应为整数类型，收到 {type(val).__name__}")
        elif expected_type == "float":
            try:
                float(val)
            except (ValueError, TypeError):
                errors.append(f"属性 '{key}' 应为浮点数类型，收到 {type(val).__name__}")
        elif expected_type == "bool":
            if not isinstance(val, bool):
                errors.append(f"属性 '{key}' 应为布尔类型，收到 {type(val).__name__}")

    return errors


def _entity_cognition(e: Entity, type_def: EntityTypeDef, relations: list) -> dict:
    """构建实体完整认知（四个维度）。"""
    definition = type_def.definition or {}
    return {
        # ① 身份
        "identity": {
            "guid": str(e.guid),
            "type_name": e.type_name,
            "display_name": type_def.display_name or e.type_name,
            "category": type_def.category,
            "name": e.name,
            "qualified_name": e.qualified_name,
            "attributes": e.attributes or {},
            "labels": e.labels or {},
            "source": e.source,
        },
        # ② 期望
        "expectation": {
            "metrics": definition.get("metrics", []),
            "relations": definition.get("relations", []),
            "health_model": definition.get("health"),
        },
        # ③ 观测
        "observation": {
            "health_score": e.health_score,
            "health_level": e.health_level,
            "health_detail": e.health_detail,
            "last_observed": e.last_observed.isoformat() if e.last_observed else None,
            "expected_metrics": e.expected_metrics or [],
        },
        # ④ 影响
        "impact": {
            "biz_service": e.biz_service,
            "risk_score": e.risk_score,
            "propagation_hops": e.propagation_hops,
            "blast_radius": e.blast_radius,
            "relations": relations,
        },
    }


# ---- Routes ----

@router.post("/entities", status_code=201)
async def create_entity(
    body: EntityCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new entity."""
    qname = body.qualified_name or f"{body.type_name}:{body.name}"

    # Check duplicate
    existing = await session.scalar(
        select(Entity).where(Entity.qualified_name == qname)
    )
    if existing:
        raise HTTPException(409, f"Entity with qualified_name '{qname}' already exists")

    # Get type definition for expected metrics/relations
    type_def = await session.get(EntityTypeDef, body.type_name)
    expected_metrics = []
    expected_relations = []
    if type_def and type_def.definition:
        expected_metrics = type_def.definition.get("metrics", [])
        expected_relations = type_def.definition.get("relations", [])

        # 属性校验
        attr_defs = type_def.definition.get("attributes", [])
        if attr_defs:
            errors = _validate_attributes(body.attributes, attr_defs)
            if errors:
                raise HTTPException(422, detail={"message": "属性校验失败", "errors": errors})

    entity = Entity(
        type_name=body.type_name,
        name=body.name,
        qualified_name=qname,
        attributes=body.attributes,
        labels=body.labels,
        source=body.source,
        biz_service=body.biz_service,
        expected_metrics=expected_metrics,
        expected_relations=expected_relations,
        health_score=100,
        health_level="healthy",
    )
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return _entity_to_dict(entity)


@router.get("/entities")
async def list_entities(
    type_name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    label_key: Optional[str] = Query(None),
    label_value: Optional[str] = Query(None),
    biz_service: Optional[str] = Query(None),
    health_level: Optional[str] = Query(None),
    status: Optional[str] = Query("active"),
    search: Optional[str] = Query(None),
    sort: str = Query("updated_at", regex="^(updated_at|name|health_score|risk_score)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List entities with filters — 支持健康度/风险度/业务/标签筛选和排序。"""
    query = select(Entity)
    count_query = select(func.count(Entity.guid))

    conditions = []
    if type_name:
        conditions.append(Entity.type_name == type_name)
    if category:
        # Join with type_def for category filter
        query = query.join(EntityTypeDef, Entity.type_name == EntityTypeDef.type_name)
        count_query = count_query.join(EntityTypeDef, Entity.type_name == EntityTypeDef.type_name)
        conditions.append(EntityTypeDef.category == category)
    if status:
        conditions.append(Entity.status == status)
    if label_key and label_value:
        conditions.append(Entity.labels[label_key].astext == label_value)
    if biz_service:
        conditions.append(Entity.biz_service == biz_service)
    if health_level:
        conditions.append(Entity.health_level == health_level)
    if search:
        conditions.append(Entity.name.ilike(f"%{search}%"))

    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total = await session.scalar(count_query)

    # Sorting
    sort_col = {
        "updated_at": Entity.updated_at,
        "name": Entity.name,
        "health_score": Entity.health_score,
        "risk_score": Entity.risk_score,
    }[sort]
    if order == "desc":
        query = query.order_by(sort_col.desc().nullslast())
    else:
        query = query.order_by(sort_col.asc().nullsfirst())

    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    entities = result.scalars().all()

    return {
        "total": total,
        "items": [_entity_to_dict(e) for e in entities],
        "limit": limit,
        "offset": offset,
    }


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get entity by GUID."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")
    return _entity_to_dict(entity)


@router.get("/entities/{entity_id}/cognition")
async def get_entity_cognition(
    entity_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取实体完整认知 — 四个维度：身份/期望/观测/影响。"""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")

    # Get type definition
    type_def = await session.get(EntityTypeDef, entity.type_name)
    if not type_def:
        type_def = EntityTypeDef(type_name=entity.type_name, definition={})

    # Get relationships
    rel_query = select(Relationship).where(
        and_(
            Relationship.is_active == True,
            or_(Relationship.end1_guid == eid, Relationship.end2_guid == eid),
        )
    )
    rel_result = await session.execute(rel_query)
    rels = rel_result.scalars().all()

    relations = []
    for r in rels:
        is_outgoing = r.end1_guid == eid
        relations.append({
            "guid": str(r.guid),
            "type": r.type_name,
            "direction": "outgoing" if is_outgoing else "incoming",
            "peer_guid": str(r.end2_guid if is_outgoing else r.end1_guid),
            "attributes": r.attributes or {},
            "confidence": r.confidence,
            "source": r.source,
        })

    return _entity_cognition(entity, type_def, relations)


@router.get("/entities/{entity_id}/attribute-schema")
async def get_entity_attribute_schema(
    entity_id: str,
    session: AsyncSession = Depends(get_session),
):
    """获取实体的属性元数据 schema（用于前端表单生成）。"""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")

    type_def = await session.get(EntityTypeDef, entity.type_name)
    if not type_def:
        return {"type_name": entity.type_name, "attributes": [], "metrics": [], "relations": []}

    definition = type_def.definition or {}
    return {
        "type_name": entity.type_name,
        "display_name": type_def.display_name or entity.type_name,
        "category": type_def.category,
        "attributes": definition.get("attributes", []),
        "metrics": definition.get("metrics", []),
        "metrics_by_category": _group_metrics_by_category(definition.get("metrics", [])),
        "health_model": definition.get("health"),
        "current_values": entity.attributes or {},
    }


@router.get("/type-schema/{type_name}")
async def get_type_schema(
    type_name: str,
    session: AsyncSession = Depends(get_session),
):
    """获取类型的完整 schema（属性/指标/关系/健康模型），不需实体ID。"""
    type_def = await session.get(EntityTypeDef, type_name)
    if not type_def:
        raise HTTPException(404, f"Type '{type_name}' not found")

    definition = type_def.definition or {}
    return {
        "type_name": type_name,
        "display_name": type_def.display_name or type_name,
        "category": type_def.category,
        "super_type": type_def.super_type,
        "attributes": definition.get("attributes", []),
        "metrics": definition.get("metrics", []),
        "metrics_by_category": _group_metrics_by_category(definition.get("metrics", [])),
        "relations": definition.get("relations", []),
        "health_model": definition.get("health"),
    }


def _group_metrics_by_category(metrics: list) -> dict:
    """按 category 分组指标。"""
    groups = {}
    for m in metrics:
        cat = m.get("category", "other")
        (groups[cat] if cat in groups else groups.setdefault(cat, [])).append(m)
    return groups


@router.get("/entities/{entity_id}/health")
async def get_entity_health(
    entity_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get entity health status."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")

    return {
        "guid": str(entity.guid),
        "name": entity.name,
        "type_name": entity.type_name,
        "health_score": entity.health_score,
        "health_level": entity.health_level,
        "health_detail": entity.health_detail,
        "last_observed": entity.last_observed.isoformat() if entity.last_observed else None,
    }


@router.put("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    body: EntityUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an entity."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")

    # 属性校验（如果更新了 attributes）
    update_data = body.model_dump(exclude_unset=True)
    if "attributes" in update_data:
        type_def = await session.get(EntityTypeDef, entity.type_name)
        if type_def and type_def.definition:
            attr_defs = type_def.definition.get("attributes", [])
            if attr_defs:
                # 合并现有属性和更新属性进行校验
                merged_attrs = {**(entity.attributes or {}), **update_data["attributes"]}
                errors = _validate_attributes(merged_attrs, attr_defs)
                if errors:
                    raise HTTPException(422, detail={"message": "属性校验失败", "errors": errors})

    for key, value in update_data.items():
        setattr(entity, key, value)

    await session.commit()
    await session.refresh(entity)
    return _entity_to_dict(entity)


@router.delete("/entities/{entity_id}", status_code=204)
async def delete_entity(
    entity_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete an entity."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")

    await session.delete(entity)
    await session.commit()


# ---- Relationships ----

@router.post("/entities/{entity_id}/relations", status_code=201)
async def create_relationship(
    entity_id: str,
    body: RelationshipCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a relationship from entity to another entity."""
    try:
        e1 = uuid.UUID(entity_id)
        e2 = uuid.UUID(body.end2_guid)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    # 校验关系约束：from_entity.type 必须匹配关系定义的 end1_type
    entity1 = await session.get(Entity, e1)
    entity2 = await session.get(Entity, e2)
    if not entity1 or not entity2:
        raise HTTPException(404, "Source or target entity not found")

    rel_type_def = await session.get(RelationshipTypeDef, body.type_name)
    if rel_type_def:
        if rel_type_def.end1_type and entity1.type_name != rel_type_def.end1_type:
            raise HTTPException(422,
                f"关系类型 '{body.type_name}' 要求源实体类型为 '{rel_type_def.end1_type}'，"
                f"但 '{entity1.name}' 的类型为 '{entity1.type_name}'")
        if rel_type_def.end2_type and entity2.type_name != rel_type_def.end2_type:
            raise HTTPException(422,
                f"关系类型 '{body.type_name}' 要求目标实体类型为 '{rel_type_def.end2_type}'，"
                f"但 '{entity2.name}' 的类型为 '{entity2.type_name}'")

    rel = Relationship(
        type_name=body.type_name,
        end1_guid=e1,
        end2_guid=e2,
        from_guid=e1,
        to_guid=e2,
        attributes=body.attributes,
        source=body.source,
        confidence=body.confidence,
        dimension=body.dimension,
    )
    session.add(rel)
    await session.commit()
    await session.refresh(rel)

    return {
        "guid": str(rel.guid),
        "type_name": rel.type_name,
        "from_guid": str(rel.from_guid or rel.end1_guid),
        "to_guid": str(rel.to_guid or rel.end2_guid),
        "attributes": rel.attributes,
        "source": rel.source,
        "confidence": rel.confidence,
        "dimension": rel.dimension or "vertical",
        "is_active": rel.is_active,
    }


@router.get("/entities/{entity_id}/relations")
async def list_relationships(
    entity_id: str,
    direction: str = Query("both", regex="^(outgoing|incoming|both)$"),
    relation_type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List relationships for an entity."""
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    conditions = [Relationship.is_active == True]

    if direction == "outgoing":
        conditions.append(Relationship.end1_guid == eid)
    elif direction == "incoming":
        conditions.append(Relationship.end2_guid == eid)
    else:
        conditions.append(
            or_(Relationship.end1_guid == eid, Relationship.end2_guid == eid)
        )

    if relation_type:
        conditions.append(Relationship.type_name == relation_type)

    query = select(Relationship).where(and_(*conditions))
    result = await session.execute(query)
    rels = result.scalars().all()

    return {
        "total": len(rels),
        "items": [
            {
                "guid": str(r.guid),
                "type_name": r.type_name,
                "from_guid": str(r.from_guid or r.end1_guid),
                "to_guid": str(r.to_guid or r.end2_guid),
                "attributes": r.attributes or {},
                "source": r.source,
                "confidence": r.confidence,
                "dimension": r.dimension or "vertical",
                "is_active": r.is_active,
            }
            for r in rels
        ],
    }


# ---- Enrich (for Vector ETL) ----

class EnrichRequest(BaseModel):
    service_name: Optional[str] = None
    host_name: Optional[str] = None
    labels: dict = Field(default_factory=dict)


@router.post("/enrich")
async def enrich_entity(
    body: EnrichRequest,
    session: AsyncSession = Depends(get_session),
):
    """Called by Vector ETL to enrich log data with CMDB info."""
    result = {}

    if body.service_name:
        q = select(Entity).where(
            and_(
                Entity.type_name == "Service",
                Entity.name == body.service_name,
            )
        )
        entity = await session.scalar(q)
        if entity:
            result["cmdb"] = _entity_to_dict(entity)

    return result

# ---- 拓扑下钻 ----

@router.get("/entities/{entity_id}/drill-down")
async def get_entity_drill_down(
    entity_id: str,
    max_depth: int = Query(3, ge=1, le=5, description="最大展开深度"),
    session: AsyncSession = Depends(get_session),
):
    """获取实体的纵向下钻拓扑 — 沿 runs_on / depends_on / includes 向下展开。

    返回该实体的完整归属树，包含每个节点的健康度和关键指标。
    """
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")

    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Entity not found")

    visited = set()

    async def _expand(guid: uuid.UUID, depth: int):
        if depth > max_depth or guid in visited:
            return None
        visited.add(guid)

        e = await session.get(Entity, guid)
        if not e:
            return None

        # 获取类型定义
        type_def = await session.get(EntityTypeDef, e.type_name)
        definition = type_def.definition if type_def else {}

        node = {
            "guid": str(e.guid),
            "name": e.name,
            "type_name": e.type_name,
            "display_name": type_def.display_name if type_def else e.type_name,
            "category": type_def.category if type_def else "custom",
            "health_score": e.health_score,
            "health_level": e.health_level,
            "risk_score": e.risk_score,
            "attributes": e.attributes or {},
            "metrics": definition.get("metrics", []),
            "children": [],
            "calls_to": [],  # 横向调用关系（只展示，不展开）
        }

        # 查询纵向关系（runs_on, depends_on, includes）
        vertical_rels = await session.execute(
            select(Relationship).where(
                and_(
                    Relationship.is_active == True,
                    Relationship.end1_guid == guid,
                    Relationship.dimension == "vertical",
                    Relationship.type_name.in_(["runs_on", "depends_on", "includes", "hosts"]),
                )
            )
        )
        for rel in vertical_rels.scalars().all():
            child = await _expand(rel.end2_guid, depth + 1)
            if child:
                node["children"].append({
                    "relation_type": rel.type_name,
                    "relation_guid": str(rel.guid),
                    "confidence": rel.confidence,
                    "node": child,
                })

        # 查询横向关系（calls）— 只展示，不展开
        horizontal_rels = await session.execute(
            select(Relationship, Entity).join(
                Entity, Relationship.end2_guid == Entity.guid
            ).where(
                and_(
                    Relationship.is_active == True,
                    Relationship.end1_guid == guid,
                    Relationship.dimension == "horizontal",
                    Relationship.type_name.in_(["calls", "depends_on"]),
                )
            )
        )
        for rel, target_entity in horizontal_rels.all():
            node["calls_to"].append({
                "guid": str(target_entity.guid),
                "name": target_entity.name,
                "type_name": target_entity.type_name,
                "relation_type": rel.type_name,
            })

        return node

    drill_tree = await _expand(eid, 0)

    # 获取类型定义中的 health 模型
    type_def = await session.get(EntityTypeDef, entity.type_name)
    health_model = (type_def.definition or {}).get("health") if type_def else None

    return {
        "entity": {
            "guid": str(entity.guid),
            "name": entity.name,
            "type_name": entity.type_name,
            "health_score": entity.health_score,
            "health_level": entity.health_level,
            "risk_score": entity.risk_score,
        },
        "health_model": health_model,
        "drill_tree": drill_tree,
        "max_depth": max_depth,
        "visited_count": len(visited),
    }


@router.get("/topology/call")
async def get_call_topology(
    window_minutes: int = Query(15, ge=1, le=60, description="时间窗口(分钟)"),
    session: AsyncSession = Depends(get_session),
):
    """获取调用拓扑 — 从 CMDB relationship 表查询横向调用关系。"""
    # 查询所有横向调用关系
    query = select(
        Relationship,
        Entity.name.label("from_name"),
        Entity.type_name.label("from_type"),
    ).join(
        Entity, Relationship.end1_guid == Entity.guid
    ).where(
        and_(
            Relationship.is_active == True,
            Relationship.dimension == "horizontal",
            Relationship.type_name.in_(["calls", "depends_on"]),
        )
    )
    result = await session.execute(query)

    edges = []
    nodes = {}

    for rel, from_name, from_type in result.all():
        # 获取目标实体
        target = await session.get(Entity, rel.end2_guid)
        if not target:
            continue

        edges.append({
            "from_guid": str(rel.end1_guid),
            "from_name": from_name,
            "from_type": from_type,
            "to_guid": str(rel.end2_guid),
            "to_name": target.name,
            "to_type": target.type_name,
            "relation_type": rel.type_name,
            "confidence": rel.confidence,
            "source": rel.source,
        })

        # 收集节点
        nodes[str(rel.end1_guid)] = {"name": from_name, "type": from_type}
        nodes[str(rel.end2_guid)] = {"name": target.name, "type": target.type_name}

    return {
        "nodes": [
            {"guid": guid, **info}
            for guid, info in nodes.items()
        ],
        "edges": edges,
        "window_minutes": window_minutes,
    }


@router.get("/topology/infra")
async def get_infra_topology(
    session: AsyncSession = Depends(get_session),
):
    """获取基础设施拓扑 — 查询 runs_on / hosts / connected_to 关系。"""
    query = select(
        Relationship,
        Entity.name.label("from_name"),
        Entity.type_name.label("from_type"),
    ).join(
        Entity, Relationship.end1_guid == Entity.guid
    ).where(
        and_(
            Relationship.is_active == True,
            Relationship.type_name.in_(["runs_on", "hosts", "connected_to"]),
        )
    )
    result = await session.execute(query)

    edges = []
    nodes = {}

    for rel, from_name, from_type in result.all():
        target = await session.get(Entity, rel.end2_guid)
        if not target:
            continue

        edges.append({
            "from_guid": str(rel.end1_guid),
            "from_name": from_name,
            "from_type": from_type,
            "to_guid": str(rel.end2_guid),
            "to_name": target.name,
            "to_type": target.type_name,
            "relation_type": rel.type_name,
        })

        nodes[str(rel.end1_guid)] = {
            "name": from_name,
            "type": from_type,
            "health_score": None,
        }
        nodes[str(rel.end2_guid)] = {
            "name": target.name,
            "type": target.type_name,
            "health_score": target.health_score,
        }

    # 补充节点的健康度信息
    for guid in nodes:
        e = await session.get(Entity, uuid.UUID(guid))
        if e:
            nodes[guid]["health_score"] = e.health_score
            nodes[guid]["health_level"] = e.health_level

    return {
        "nodes": [
            {"guid": guid, **info}
            for guid, info in nodes.items()
        ],
        "edges": edges,
    }


# heartbeat 路由已迁移到 heartbeat.py
