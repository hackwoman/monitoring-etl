"""CMDB Heartbeat 接口 — 支持 NDJSON 批量处理。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import Entity, EntityTypeDef
from datetime import datetime
import json

router = APIRouter()


@router.post("/heartbeat")
async def entity_heartbeat(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    自动发现实体 — 支持单个 JSON 和 NDJSON（Vector 多条 event 合并发送）。
    兼容格式：
    - Agent: {"name": "x", "type_name": "Service"}
    - Vector: {"cmdb_name": "x", "cmdb_type": "Service"}
    - Vector NDJSON: {"cmdb_name":"a",...}\n{"cmdb_name":"b",...}
    """
    raw = await request.body()
    raw_text = raw.decode("utf-8", errors="replace").strip()

    # 解析请求体：单个 JSON 或 NDJSON
    payloads = []
    if raw_text.startswith("{"):
        # 单个 JSON
        try:
            payloads.append(json.loads(raw_text))
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON")
    else:
        # NDJSON：逐行解析
        for line in raw_text.split("\n"):
            line = line.strip()
            if line and line.startswith("{"):
                try:
                    payloads.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not payloads:
        raise HTTPException(400, "No valid JSON payloads found")

    results = []
    for body in payloads:
        result = await _process_heartbeat(body, session)
        results.append(result)

    await session.commit()

    # 如果只有一个 payload，返回单个结果（兼容旧格式）
    if len(results) == 1:
        return results[0]
    return {"status": "ok", "processed": len(results), "results": results}


async def _process_heartbeat(body: dict, session: AsyncSession) -> dict:
    """处理单个 heartbeat 请求。"""
    # 解析实体名和类型
    name = body.get("name") or body.get("cmdb_name") or body.get("service_name") or body.get("host_name")

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
        entity.last_observed = datetime.utcnow()
        if labels:
            existing_labels = entity.labels or {}
            existing_labels.update(labels)
            entity.labels = existing_labels
        return {"status": "ok", "action": "updated", "entity_guid": str(entity.guid)}
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
        # flush 以获取 GUID（commit 在外层统一做）
        await session.flush()
        return {"status": "ok", "action": "created", "entity_guid": str(entity.guid)}
