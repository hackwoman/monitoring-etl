"""Trace 关系发现 API 路由。"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discover", tags=["discover"])


class DiscoveryRequest(BaseModel):
    window_minutes: int = 60


class DiscoveryResponse(BaseModel):
    discovered: int
    created: int
    updated: int
    skipped: int
    timestamp: str


@router.post("/trace", response_model=DiscoveryResponse)
async def discover_trace_relations(request: DiscoveryRequest = DiscoveryRequest()):
    """
    手动触发 Trace 关系发现。

    从 ClickHouse traces.spans 表提取服务调用拓扑，
    与 CMDB 现有关系融合。
    """
    try:
        from app.services.trace_discovery import run_discovery_once
        result = run_discovery_once(request.window_minutes)
        return DiscoveryResponse(**result)
    except Exception as e:
        logger.error(f"Trace discovery failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/topology")
async def get_trace_topology(
    window_minutes: int = Query(60, description="分析窗口（分钟）"),
):
    """获取从 Trace 数据发现的调用拓扑（不写入 CMDB）。"""
    try:
        from app.services.trace_discovery import query_service_topology_from_trace
        relations = query_service_topology_from_trace(window_minutes)
        return {
            "window_minutes": window_minutes,
            "relations": [
                {
                    "caller": r.caller,
                    "callee": r.callee,
                    "call_count": r.call_count,
                    "avg_latency_ms": r.avg_latency_ms,
                    "p99_latency_ms": r.p99_latency_ms,
                    "error_rate": r.error_rate,
                }
                for r in relations
            ],
        }
    except Exception as e:
        logger.error(f"Trace topology query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/endpoints")
async def get_endpoint_topology(
    window_minutes: int = Query(60, description="分析窗口（分钟）"),
):
    """获取接口级调用拓扑。"""
    try:
        from app.services.trace_discovery import query_endpoint_topology
        data = query_endpoint_topology(window_minutes)
        return {
            "window_minutes": window_minutes,
            "endpoints": data,
        }
    except Exception as e:
        logger.error(f"Endpoint topology query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
