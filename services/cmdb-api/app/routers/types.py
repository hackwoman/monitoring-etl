"""CMDB Type management routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import EntityTypeDef, RelationshipTypeDef

router = APIRouter()


@router.get("/types")
async def list_entity_types(session: AsyncSession = Depends(get_session)):
    """List all entity type definitions."""
    result = await session.execute(select(EntityTypeDef))
    types = result.scalars().all()
    return {
        "total": len(types),
        "items": [
            {
                "type_name": t.type_name,
                "description": t.description,
                "super_types": t.super_types or [],
                "attribute_defs": t.attribute_defs or {},
            }
            for t in types
        ],
    }


@router.post("/types", status_code=201)
async def create_entity_type(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Register a new entity type."""
    etype = EntityTypeDef(
        type_name=body["type_name"],
        description=body.get("description", ""),
        super_types=body.get("super_types", []),
        attribute_defs=body.get("attribute_defs", {}),
    )
    session.add(etype)
    await session.commit()
    return {"type_name": etype.type_name, "status": "created"}


@router.get("/relation-types")
async def list_relationship_types(session: AsyncSession = Depends(get_session)):
    """List all relationship type definitions."""
    result = await session.execute(select(RelationshipTypeDef))
    types = result.scalars().all()
    return {
        "total": len(types),
        "items": [
            {
                "type_name": t.type_name,
                "end1_type": t.end1_type,
                "end1_name": t.end1_name,
                "end2_type": t.end2_type,
                "end2_name": t.end2_name,
                "description": t.description,
            }
            for t in types
        ],
    }
