"""
CMDB 自动发现：从 ClickHouse 扫描已存在的服务和主机，同步到 CMDB。

用法:
  直接调用 API: POST /api/v1/cmdb/discover
  或定时任务: python -m app.routers.discover
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import Entity, EntityTypeDef
from datetime import datetime
import httpx
import os

router = APIRouter()

CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123")


@router.post("/discover")
async def discover_entities(
    session: AsyncSession = Depends(get_session),
):
    """
    从 ClickHouse 扫描日志中的 service_name / host_name，
    同步到 CMDB（有则更新，无则创建）。
    """
    results = {"services": [], "hosts": [], "created": 0, "updated": 0, "skipped": 0}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 查询 distinct service_name
            r = await client.post(
                f"{CLICKHOUSE_URL}",
                params={"query": "SELECT DISTINCT service_name FROM logs.log_entries WHERE service_name != '' LIMIT 500"}
            )
            if r.status_code == 200:
                service_names = [line.strip() for line in r.text.strip().split("\n") if line.strip()]
            else:
                service_names = []

            # 查询 distinct host_name
            r = await client.post(
                f"{CLICKHOUSE_URL}",
                params={"query": "SELECT DISTINCT host_name FROM logs.log_entries WHERE host_name != '' LIMIT 500"}
            )
            if r.status_code == 200:
                host_names = [line.strip() for line in r.text.strip().split("\n") if line.strip()]
            else:
                host_names = []

    except Exception as e:
        return {"error": f"ClickHouse query failed: {e}", **results}

    # 同步 services
    for name in service_names:
        qname = f"Service:{name}"
        entity = await session.scalar(select(Entity).where(Entity.qualified_name == qname))
        if entity:
            entity.last_observed = datetime.utcnow()
            results["updated"] += 1
        else:
            type_def = await session.get(EntityTypeDef, "Service")
            metrics = type_def.definition.get("metrics", []) if type_def and type_def.definition else []
            entity = Entity(
                type_name="Service", name=name, qualified_name=qname,
                source="auto_discovered", expected_metrics=metrics,
                health_score=100, health_level="healthy",
            )
            session.add(entity)
            results["created"] += 1
        results["services"].append(name)

    # 同步 hosts
    for name in host_names:
        qname = f"Host:{name}"
        existing = await session.scalar(select(Entity).where(Entity.qualified_name == qname))
        if existing:
            existing.last_observed = datetime.utcnow()
            results["updated"] += 1
        else:
            type_def = await session.get(EntityTypeDef, "Host")
            metrics = type_def.definition.get("metrics", []) if type_def and type_def.definition else []
            entity = Entity(
                type_name="Host", name=name, qualified_name=qname,
                source="auto_discovered", expected_metrics=metrics,
                health_score=100, health_level="healthy",
            )
            session.add(entity)
            results["created"] += 1
        results["hosts"].append(name)

    await session.commit()

    results["summary"] = f"发现 {len(results['services'])} 服务 + {len(results['hosts'])} 主机, 创建 {results['created']}, 更新 {results['updated']}"
    return results
