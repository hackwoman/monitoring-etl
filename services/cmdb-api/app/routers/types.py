"""CMDB Type management routes - Phase 2 增强版。"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import EntityTypeDef, RelationshipTypeDef, AttributeTemplate
from app.metric_definitions import (
    ENTITY_METRIC_DEFINITIONS,
    METRIC_DIMENSIONS,
    get_metrics_for_type,
    get_all_metrics_flat,
    validate_metric_value,
)
from app.attribute_definitions import (
    ATTRIBUTE_TYPES,
    ATTRIBUTE_TEMPLATES,
    AttributeMetadata,
    get_attribute_template,
    get_attribute_schema,
    validate_entity_attributes,
)

router = APIRouter()


# ---- Pydantic Schemas ----

class TypeCreate(BaseModel):
    type_name: str
    display_name: Optional[str] = None
    category: str = "custom"
    icon: Optional[str] = None
    super_type: Optional[str] = None
    definition: dict = Field(default_factory=dict)
    description: Optional[str] = None


class TypeResponse(BaseModel):
    type_name: str
    display_name: Optional[str]
    category: str
    icon: Optional[str]
    super_type: Optional[str]
    definition: dict
    description: Optional[str]
    is_custom: bool
    version: int

    class Config:
        from_attributes = True


def _type_to_dict(t: EntityTypeDef) -> dict:
    return {
        "type_name": t.type_name,
        "display_name": t.display_name,
        "category": t.category,
        "icon": t.icon,
        "super_type": t.super_type,
        "definition": t.definition or {},
        "description": t.description,
        "is_custom": t.is_custom,
        "version": t.version,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# ---- Routes ----

@router.get("/types")
async def list_entity_types(
    category: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List all entity type definitions, optionally filtered by category."""
    query = select(EntityTypeDef)
    if category:
        query = query.where(EntityTypeDef.category == category)
    query = query.order_by(EntityTypeDef.category, EntityTypeDef.type_name)
    result = await session.execute(query)
    types = result.scalars().all()
    return {
        "total": len(types),
        "items": [_type_to_dict(t) for t in types],
    }


@router.get("/types/{type_name}")
async def get_entity_type(
    type_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single entity type with its full definition."""
    entity_type = await session.get(EntityTypeDef, type_name)
    if not entity_type:
        raise HTTPException(404, f"Type '{type_name}' not found")
    return _type_to_dict(entity_type)


@router.post("/types", status_code=201)
async def create_entity_type(
    body: TypeCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new entity type (supports custom types with full definition)."""
    etype = EntityTypeDef(
        type_name=body.type_name,
        display_name=body.display_name,
        category=body.category,
        icon=body.icon,
        super_type=body.super_type,
        definition=body.definition,
        description=body.description,
        is_custom=True,
    )
    session.add(etype)
    await session.commit()
    await session.refresh(etype)
    return _type_to_dict(etype)


@router.put("/types/{type_name}")
async def update_entity_type(
    type_name: str,
    body: TypeCreate,
    session: AsyncSession = Depends(get_session),
):
    """Update an entity type definition."""
    etype = await session.get(EntityTypeDef, type_name)
    if not etype:
        raise HTTPException(404, f"Type '{type_name}' not found")

    etype.display_name = body.display_name or etype.display_name
    etype.category = body.category or etype.category
    etype.icon = body.icon or etype.icon
    etype.super_type = body.super_type
    etype.definition = body.definition or etype.definition
    etype.description = body.description or etype.description
    etype.version = (etype.version or 1) + 1

    await session.commit()
    await session.refresh(etype)
    return _type_to_dict(etype)


@router.delete("/types/{type_name}", status_code=204)
async def delete_entity_type(
    type_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a custom entity type (builtin types cannot be deleted)."""
    etype = await session.get(EntityTypeDef, type_name)
    if not etype:
        raise HTTPException(404, f"Type '{type_name}' not found")
    if not etype.is_custom:
        raise HTTPException(400, "Cannot delete builtin type")
    await session.delete(etype)
    await session.commit()


@router.get("/types/{type_name}/metrics")
async def get_type_metrics(
    type_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get metric templates for a type (from its definition)."""
    etype = await session.get(EntityTypeDef, type_name)
    if not etype:
        raise HTTPException(404, f"Type '{type_name}' not found")

    definition = etype.definition or {}
    metrics = definition.get("metrics", [])

    # If has super_type, merge parent metrics
    if etype.super_type:
        parent = await session.get(EntityTypeDef, etype.super_type)
        if parent:
            parent_metrics = (parent.definition or {}).get("metrics", [])
            # Child metrics override parent by name
            metric_names = {m["name"] for m in metrics}
            for pm in parent_metrics:
                if pm["name"] not in metric_names:
                    metrics.append(pm)

    return {
        "type_name": type_name,
        "total": len(metrics),
        "metrics": metrics,
    }


@router.get("/types/{type_name}/health-model")
async def get_type_health_model(
    type_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get health model for a type."""
    etype = await session.get(EntityTypeDef, type_name)
    if not etype:
        raise HTTPException(404, f"Type '{type_name}' not found")

    definition = etype.definition or {}
    return {
        "type_name": type_name,
        "health": definition.get("health"),
        "method": definition.get("health", {}).get("method") if definition.get("health") else None,
    }


@router.get("/types/{type_name}/relations")
async def get_type_relations(
    type_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get expected relation templates for a type."""
    etype = await session.get(EntityTypeDef, type_name)
    if not etype:
        raise HTTPException(404, f"Type '{type_name}' not found")

    definition = etype.definition or {}
    relations = definition.get("relations", [])

    # Merge parent relations
    if etype.super_type:
        parent = await session.get(EntityTypeDef, etype.super_type)
        if parent:
            parent_relations = (parent.definition or {}).get("relations", [])
            rel_keys = {(r["type"], r.get("target")) for r in relations}
            for pr in parent_relations:
                if (pr["type"], pr.get("target")) not in rel_keys:
                    relations.append(pr)

    return {
        "type_name": type_name,
        "total": len(relations),
        "relations": relations,
    }


# ---- Relationship Types (保留兼容) ----

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


# ---- Attribute Templates ----

@router.get("/attribute-templates")
async def list_attribute_templates(
    category: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List attribute templates."""
    query = select(AttributeTemplate)
    if category:
        query = query.where(AttributeTemplate.category == category)
    result = await session.execute(query)
    templates = result.scalars().all()
    return {
        "total": len(templates),
        "items": [
            {
                "template_name": t.template_name,
                "category": t.category,
                "attributes": t.attributes or [],
                "description": t.description,
                "is_builtin": t.is_builtin,
            }
            for t in templates
        ],
    }


@router.get("/attribute-templates/{template_name}")
async def get_attribute_template(
    template_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single attribute template."""
    tmpl = await session.get(AttributeTemplate, template_name)
    if not tmpl:
        raise HTTPException(404, f"Template '{template_name}' not found")
    return {
        "template_name": tmpl.template_name,
        "category": tmpl.category,
        "attributes": tmpl.attributes or [],
        "description": tmpl.description,
        "is_builtin": tmpl.is_builtin,
    }


# ---- Phase 4.1: 指标体系 API ----

@router.get("/metric-dimensions")
async def list_metric_dimensions():
    """列出所有指标维度分类。"""
    return {
        "total": len(METRIC_DIMENSIONS),
        "dimensions": [
            {"key": key, "label": label}
            for key, label in METRIC_DIMENSIONS.items()
        ],
    }


@router.get("/metric-definitions")
async def list_metric_definitions(
    type_name: Optional[str] = Query(None, description="按实体类型过滤"),
):
    """列出所有实体类型的指标定义。"""
    if type_name:
        metrics = get_metrics_for_type(type_name)
        if not metrics:
            raise HTTPException(404, f"No metric definitions for type '{type_name}'")
        return {
            "type_name": type_name,
            "dimensions": metrics,
            "total": sum(len(m) for m in metrics.values()),
        }
    
    # 返回所有类型的指标概览
    result = {}
    for tname, dims in ENTITY_METRIC_DEFINITIONS.items():
        result[tname] = {
            "dimensions": list(dims.keys()),
            "total_metrics": sum(len(m) for m in dims.values()),
        }
    return {
        "types": result,
        "total_types": len(result),
    }


@router.get("/metric-definitions/{type_name}")
async def get_type_metric_definitions(
    type_name: str,
    flat: bool = Query(False, description="是否返回扁平化列表"),
):
    """获取指定实体类型的完整指标定义（带维度和阈值）。"""
    if flat:
        metrics = get_all_metrics_flat(type_name)
        if not metrics:
            raise HTTPException(404, f"No metric definitions for type '{type_name}'")
        return {
            "type_name": type_name,
            "total": len(metrics),
            "metrics": metrics,
        }
    
    metrics = get_metrics_for_type(type_name)
    if not metrics:
        raise HTTPException(404, f"No metric definitions for type '{type_name}'")
    
    return {
        "type_name": type_name,
        "dimensions": {
            dim: {
                "label": METRIC_DIMENSIONS.get(dim, dim),
                "metrics": mets,
            }
            for dim, mets in metrics.items()
        },
        "total": sum(len(m) for m in metrics.values()),
    }


@router.post("/metric-definitions/validate")
async def validate_metric(
    metric_name: str = Query(..., description="指标名称"),
    type_name: str = Query(..., description="实体类型"),
    value: float = Query(..., description="指标值"),
):
    """验证指标值是否超阈值。"""
    status = validate_metric_value(metric_name, type_name, value)
    return {
        "metric_name": metric_name,
        "type_name": type_name,
        "value": value,
        "status": status,
    }


# ---- Phase 4.2: 属性元数据 API ----

@router.get("/attribute-schemas/{type_name}")
async def get_attribute_schema_api(
    type_name: str,
    session: AsyncSession = Depends(get_session),
):
    """获取实体类型的属性 Schema（从数据库 definition.attributes 读取）。

    返回格式化的 Schema，供前端表单生成使用。
    """
    etype = await session.get(EntityTypeDef, type_name)
    if not etype:
        raise HTTPException(404, f"Type '{type_name}' not found")

    definition = etype.definition or {}
    attributes = definition.get("attributes", [])

    # 按分组组织
    groups = {}
    for attr in attributes:
        group = attr.get("group") or "其他"
        if group not in groups:
            groups[group] = []
        groups[group].append(attr)

    # 统计 health_factor 属性
    health_factors = [a for a in attributes if a.get("health_factor")]
    scale_keys = [a for a in attributes if a.get("threshold_scale_key")]

    return {
        "type_name": type_name,
        "attributes": attributes,
        "groups": [
            {"name": name, "attributes": attrs}
            for name, attrs in groups.items()
        ],
        "total": len(attributes),
        "health_factors": [a["key"] for a in health_factors],
        "threshold_scale_keys": [a["key"] for a in scale_keys],
    }


class AttributeValidateRequest(BaseModel):
    type_name: str
    attributes: dict


@router.post("/attribute-schemas/validate")
async def validate_attributes_api(
    body: AttributeValidateRequest,
    session: AsyncSession = Depends(get_session),
):
    """校验属性值是否符合元数据定义。"""
    etype = await session.get(EntityTypeDef, body.type_name)
    if not etype:
        raise HTTPException(404, f"Type '{body.type_name}' not found")

    definition = etype.definition or {}
    attr_defs = definition.get("attributes", [])

    errors = []
    for attr_def in attr_defs:
        attr_meta = AttributeMetadata(**attr_def)
        value = body.attributes.get(attr_meta.key)
        valid, error = validate_attribute_value(attr_meta, value)
        if not valid:
            errors.append({"key": attr_meta.key, "error": error})

    return {
        "type_name": body.type_name,
        "valid": len(errors) == 0,
        "errors": errors,
    }
