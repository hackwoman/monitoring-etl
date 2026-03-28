"""CMDB Entity API routes."""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import Entity, Relationship, RelationshipTypeDef

router = APIRouter()


# ---- Pydantic Schemas ----

class EntityCreate(BaseModel):
    type_name: str
    name: str
    qualified_name: Optional[str] = None
    attributes: dict = Field(default_factory=dict)
    labels: dict = Field(default_factory=dict)
    source: str = "manual"


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    attributes: Optional[dict] = None
    labels: Optional[dict] = None
    status: Optional[str] = None


class EntityResponse(BaseModel):
    guid: str
    type_name: str
    name: str
    qualified_name: str
    attributes: dict
    labels: dict
    status: str
    source: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class RelationshipCreate(BaseModel):
    type_name: str
    end2_guid: str
    attributes: dict = Field(default_factory=dict)
    source: str = "manual"
    confidence: float = 1.0


class RelationshipResponse(BaseModel):
    guid: str
    type_name: str
    end1_guid: str
    end2_guid: str
    attributes: dict
    source: str
    confidence: float
    is_active: bool

    class Config:
        from_attributes = True


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
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


# ---- Routes ----

@router.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(
    body: EntityCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new entity."""
    qname = body.qualified_name or f"{body.type_name}:{body.name}"
    entity = Entity(
        type_name=body.type_name,
        name=body.name,
        qualified_name=qname,
        attributes=body.attributes,
        labels=body.labels,
        source=body.source,
    )
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return _entity_to_dict(entity)


@router.get("/entities")
async def list_entities(
    type_name: Optional[str] = Query(None),
    label_key: Optional[str] = Query(None),
    label_value: Optional[str] = Query(None),
    status: Optional[str] = Query("active"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List entities with filters."""
    query = select(Entity)
    count_query = select(func.count(Entity.guid))

    conditions = []
    if type_name:
        conditions.append(Entity.type_name == type_name)
    if status:
        conditions.append(Entity.status == status)
    if label_key and label_value:
        conditions.append(Entity.labels[label_key].astext == label_value)
    if search:
        conditions.append(Entity.name.ilike(f"%{search}%"))

    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total = await session.scalar(count_query)
    query = query.order_by(Entity.updated_at.desc()).limit(limit).offset(offset)
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
        "end1_guid": str(rel.end1_guid),
        "end2_guid": str(rel.end2_guid),
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
            (Relationship.end1_guid == eid) | (Relationship.end2_guid == eid)
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
                "end1_guid": str(r.end1_guid),
                "end2_guid": str(r.end2_guid),
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
    """
    Called by Vector ETL to enrich log data with CMDB info.
    Returns entity attributes and labels if found.
    """
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


# ---- Heartbeat (for Agent) ----

@router.post("/heartbeat")
async def entity_heartbeat(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """
    Called by OTel Agent to report entity liveness.
    Creates entity if not exists.
    """
    name = body.get("name")
    type_name = body.get("type_name", "Host")
    labels = body.get("labels", {})

    if not name:
        raise HTTPException(400, "name is required")

    qname = f"{type_name}:{name}"
    q = select(Entity).where(Entity.qualified_name == qname)
    entity = await session.scalar(q)

    if not entity:
        entity = Entity(
            type_name=type_name,
            name=name,
            qualified_name=qname,
            labels=labels,
            source="heartbeat",
        )
        session.add(entity)

    entity.updated_at = __import__("datetime").datetime.utcnow()
    await session.commit()

    return {"status": "ok", "entity_guid": str(entity.guid)}
