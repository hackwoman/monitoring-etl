"""
Phase 4: 补偿机制 API 端点
提供冲突检测、映射管理、动态扩展确认的 REST API
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import asyncpg
import json

router = APIRouter()

DATABASE_URL = "postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb"


async def get_conn():
    return await asyncpg.connect(DATABASE_URL)


# ---- 请求/响应模型 ----

class MetricResolveRequest(BaseModel):
    source_system: str
    source_metric: str
    dimensions: dict = {}

class DimensionResolveRequest(BaseModel):
    source_system: str
    source_dimension: str

class MetricConfirmRequest(BaseModel):
    metric_id: int
    target_metric_id: str
    confirmed_by: str = "admin"

class MappingCreateRequest(BaseModel):
    source_system: str
    source_metric: str
    target_metric_id: str
    confidence: float = 1.0


# ---- 冲突检测 API ----

@router.post("/resolve/metric")
async def resolve_metric(body: MetricResolveRequest):
    """解析第三方指标，尝试映射到标准模型"""
    conn = await get_conn()
    try:
        # 查询映射表
        row = await conn.fetchrow(
            """SELECT target_metric_id, confidence, status 
               FROM metric_mapping 
               WHERE source_system = $1 AND source_metric = $2""",
            body.source_system, body.source_metric
        )
        
        if row and row['status'] == 'confirmed':
            return {
                "status": "mapped",
                "target_metric_id": row['target_metric_id'],
                "confidence": row['confidence'],
                "message": f"已映射到标准指标: {row['target_metric_id']}"
            }
        
        # 模糊匹配
        fuzzy = await _fuzzy_match(conn, body.source_metric)
        if fuzzy:
            return {
                "status": "mapped",
                "target_metric_id": fuzzy['metric_id'],
                "confidence": fuzzy['confidence'],
                "message": f"模糊匹配: {fuzzy['metric_id']}"
            }
        
        # 推断实体类型
        inferred_type = _infer_entity_type(body.source_metric)
        
        # 创建动态记录
        row = await conn.fetchrow(
            """INSERT INTO dynamic_metric (source_system, source_metric, inferred_entity_type, sample_dimensions, status)
               VALUES ($1, $2, $3, $4, 'pending')
               RETURNING id""",
            body.source_system, body.source_metric, inferred_type,
            json.dumps(body.dimensions)
        )
        
        return {
            "status": "dynamic",
            "dynamic_id": row['id'],
            "inferred_entity_type": inferred_type,
            "message": f"未知指标，已创建待确认记录 (ID: {row['id']})"
        }
    finally:
        await conn.close()


@router.post("/resolve/dimension")
async def resolve_dimension(body: DimensionResolveRequest):
    """解析第三方维度，尝试映射到标准标签"""
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """SELECT target_label_key, transform_rule, status
               FROM dimension_mapping 
               WHERE source_system = $1 AND source_dimension = $2""",
            body.source_system, body.source_dimension
        )
        
        if row and row['status'] == 'confirmed':
            return {
                "status": "mapped",
                "target_key": row['target_label_key'],
                "message": f"已映射到标签: {row['target_label_key']}"
            }
        
        return {
            "status": "unknown",
            "message": f"未知维度: {body.source_dimension}"
        }
    finally:
        await conn.close()


# ---- 映射管理 API ----

@router.get("/mappings/metrics")
async def list_metric_mappings(
    source_system: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """列出指标映射"""
    conn = await get_conn()
    try:
        query = "SELECT * FROM metric_mapping WHERE 1=1"
        params = []
        idx = 1
        
        if source_system:
            query += f" AND source_system = ${idx}"
            params.append(source_system)
            idx += 1
        if status:
            query += f" AND status = ${idx}"
            params.append(status)
            idx += 1
        
        count = await conn.fetchval(query.replace("SELECT *", "SELECT COUNT(*)"), *params)
        query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}"
        params.extend([limit, offset])
        
        rows = await conn.fetch(query, *params)
        return {
            "total": count,
            "items": [dict(r) for r in rows]
        }
    finally:
        await conn.close()


@router.post("/mappings/metrics")
async def create_metric_mapping(body: MappingCreateRequest):
    """创建指标映射"""
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO metric_mapping (source_system, source_metric, target_metric_id, confidence, status, created_by)
               VALUES ($1, $2, $3, $4, 'confirmed', 'admin')
               ON CONFLICT (source_system, source_metric) 
               DO UPDATE SET target_metric_id=$3, confidence=$4, status='confirmed'""",
            body.source_system, body.source_metric, body.target_metric_id, body.confidence
        )
        return {"status": "ok", "message": "映射创建成功"}
    finally:
        await conn.close()


@router.get("/mappings/dimensions")
async def list_dimension_mappings(
    source_system: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """列出维度映射"""
    conn = await get_conn()
    try:
        query = "SELECT * FROM dimension_mapping WHERE 1=1"
        params = []
        idx = 1
        
        if source_system:
            query += f" AND source_system = ${idx}"
            params.append(source_system)
            idx += 1
        
        count = await conn.fetchval(query.replace("SELECT *", "SELECT COUNT(*)"), *params)
        query += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}"
        params.extend([limit, offset])
        
        rows = await conn.fetch(query, *params)
        return {
            "total": count,
            "items": [dict(r) for r in rows]
        }
    finally:
        await conn.close()


# ---- 动态扩展管理 API ----

@router.get("/dynamic/metrics")
async def list_dynamic_metrics(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """列出动态扩展指标"""
    conn = await get_conn()
    try:
        query = "SELECT * FROM dynamic_metric WHERE 1=1"
        params = []
        idx = 1
        
        if status:
            query += f" AND status = ${idx}"
            params.append(status)
            idx += 1
        
        count = await conn.fetchval(query.replace("SELECT *", "SELECT COUNT(*)"), *params)
        query += f" ORDER BY created_at DESC LIMIT ${idx}"
        params.append(limit)
        
        rows = await conn.fetch(query, *params)
        return {
            "total": count,
            "items": [dict(r) for r in rows]
        }
    finally:
        await conn.close()


@router.post("/dynamic/metrics/{metric_id}/confirm")
async def confirm_dynamic_metric(metric_id: int, body: MetricConfirmRequest):
    """确认动态指标"""
    conn = await get_conn()
    try:
        # 更新动态记录状态
        await conn.execute(
            """UPDATE dynamic_metric 
               SET status = 'confirmed', confirmed_by = $1, confirmed_at = NOW()
               WHERE id = $2""",
            body.confirmed_by, metric_id
        )
        
        # 创建映射记录
        row = await conn.fetchrow(
            "SELECT source_system, source_metric FROM dynamic_metric WHERE id = $1",
            metric_id
        )
        if row:
            await conn.execute(
                """INSERT INTO metric_mapping (source_system, source_metric, target_metric_id, confidence, status, created_by)
                   VALUES ($1, $2, $3, 1.0, 'confirmed', $4)
                   ON CONFLICT (source_system, source_metric) DO UPDATE SET target_metric_id=$3, status='confirmed'""",
                row['source_system'], row['source_metric'], body.target_metric_id, body.confirmed_by
            )
        
        return {"status": "ok", "message": "指标确认成功"}
    finally:
        await conn.close()


@router.post("/dynamic/metrics/{metric_id}/reject")
async def reject_dynamic_metric(metric_id: int):
    """拒绝动态指标"""
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE dynamic_metric SET status = 'rejected' WHERE id = $1",
            metric_id
        )
        return {"status": "ok", "message": "指标已拒绝"}
    finally:
        await conn.close()


# ---- 统计 API ----

@router.get("/stats")
async def get_compensation_stats():
    """获取补偿机制统计"""
    conn = await get_conn()
    try:
        metrics_total = await conn.fetchval("SELECT COUNT(*) FROM metric_def")
        mappings_total = await conn.fetchval("SELECT COUNT(*) FROM metric_mapping")
        mappings_confirmed = await conn.fetchval("SELECT COUNT(*) FROM metric_mapping WHERE status = 'confirmed'")
        mappings_pending = await conn.fetchval("SELECT COUNT(*) FROM metric_mapping WHERE status = 'pending'")
        dynamic_total = await conn.fetchval("SELECT COUNT(*) FROM dynamic_metric")
        dynamic_pending = await conn.fetchval("SELECT COUNT(*) FROM dynamic_metric WHERE status = 'pending'")
        dynamic_confirmed = await conn.fetchval("SELECT COUNT(*) FROM dynamic_metric WHERE status = 'confirmed'")
        dimensions_total = await conn.fetchval("SELECT COUNT(*) FROM dimension_mapping")
        
        return {
            "metrics": {"total": metrics_total},
            "mappings": {"total": mappings_total, "confirmed": mappings_confirmed, "pending": mappings_pending},
            "dynamic": {"total": dynamic_total, "pending": dynamic_pending, "confirmed": dynamic_confirmed},
            "dimensions": {"total": dimensions_total},
        }
    finally:
        await conn.close()


# ---- 辅助函数 ----

async def _fuzzy_match(conn, source_metric: str):
    """模糊匹配"""
    keywords = {
        "cpu": "host.cpu.usage",
        "memory": "host.memory.usage",
        "disk": "host.disk.usage",
        "network": "host.network.bandwidth.in",
        "load": "host.cpu.load.1m",
        "qps": "service.http.request.qps",
        "latency": "service.http.request.duration.p99",
        "error": "service.http.request.error_rate",
    }
    
    source_lower = source_metric.lower()
    for keyword, metric_id in keywords.items():
        if keyword in source_lower:
            exists = await conn.fetchval(
                "SELECT COUNT(*) FROM metric_def WHERE metric_id = $1", metric_id
            )
            if exists:
                return {"metric_id": metric_id, "confidence": 0.7}
    return None


def _infer_entity_type(source_metric: str) -> str:
    """推断实体类型"""
    prefix_map = {
        "node_": "Host", "host_": "Host", "container_": "Container",
        "kube_pod_": "K8sPod", "kube_node_": "K8sNode",
        "http_": "Service", "grpc_": "Service",
        "redis_": "Redis", "mysql_": "Database", "postgres_": "Database",
        "kafka_": "MessageQueue", "process_": "Process",
    }
    source_lower = source_metric.lower()
    for prefix, entity_type in prefix_map.items():
        if source_lower.startswith(prefix):
            return entity_type
    return None
