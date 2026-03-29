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

    update_data = body.model_dump(exclude_unset=True)
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

    rel = Relationship(
        type_name=body.type_name,
        end1_guid=e1,
        end2_guid=e2,
        from_guid=e1,
        to_guid=e2,
        attributes=body.attributes,
        source=body.source,
        confidence=body.confidence,
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


# ---- Heartbeat (Agent + Vector ETL 自动发现) ----

@router.post("/heartbeat")
async def entity_heartbeat(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """
    自动发现实体：有则更新 last_observed，无则创建。
    兼容两种格式：
    - Agent 格式: {"name": "x", "type_name": "Service", "labels": {}}
    - Vector 格式: {"cmdb_name": "x", "cmdb_type": "Service", "cmdb_labels": {}}
    - 也兼容: {"service_name": "x"} → type=Service, {"host_name": "x"} → type=Host
    """
    # 解析实体名和类型（兼容多种格式）
    name = body.get("name") or body.get("cmdb_name") or body.get("service_name") or body.get("host_name")
    if not name:
        raise HTTPException(400, "name/cmdb_name/service_name/host_name is required")

    if body.get("cmdb_type"):
        type_name = body["cmdb_type"]
    elif body.get("type_name"):
        type_name = body["type_name"]
    elif body.get("service_name"):
        type_name = "Service"
    elif body.get("host_name"):
        type_name = "Host"
    else:
        type_name = "Host"

    labels = body.get("labels") or body.get("cmdb_labels") or {}

    # 查找已有实体
    qname = f"{type_name}:{name}"
    q = select(Entity).where(Entity.qualified_name == qname)
    entity = await session.scalar(q)

    if entity:
        # 已存在：只更新 last_observed 和 labels
        entity.last_observed = datetime.utcnow()
        if labels:
            existing_labels = entity.labels or {}
            existing_labels.update(labels)
            entity.labels = existing_labels
    else:
        # 新实体：自动创建
        type_def = await session.get(EntityTypeDef, type_name)
        expected_metrics = []
        expected_relations = []
        if type_def and type_def.definition:
            expected_metrics = type_def.definition.get("metrics", [])
            expected_relations = type_def.definition.get("relations", [])

        entity = Entity(
            type_name=type_name,
            name=name,
            qualified_name=qname,
            labels=labels,
            source="auto_discovered",
            expected_metrics=expected_metrics,
            expected_relations=expected_relations,
            health_score=100,
            health_level="healthy",
        )
        session.add(entity)

    await session.commit()

    return {"status": "ok", "action": "created" if entity.source == "auto_discovered" else "updated", "entity_guid": str(entity.guid)}
