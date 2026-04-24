"""业务自动发现 API — L2 方案：从 Trace 拓扑自动识别业务模式。

整合功能：
- L2 自动发现：从 ClickHouse traces.spans 分析调用链
- L1 手动编辑：URL 模式配置
- 业务映射：前端页面 URL → 业务 的映射
"""

import logging
import hashlib
import json
from typing import Optional, List
from datetime import datetime

import httpx
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_session
from app.models import Entity, EntityTypeDef, Relationship

logger = logging.getLogger(__name__)

router = APIRouter(tags=["business-discovery"])

CLICKHOUSE_URL = "http://47.93.61.196:8123"


# ============================================================
# 数据模型
# ============================================================

class DiscoveredPattern(BaseModel):
    """发现的业务模式"""
    fingerprint: str
    root_service: str
    root_url: str
    root_method: str
    trace_count: int
    avg_duration_ms: float
    error_rate: float
    services: List[str]
    endpoints: List[str]
    db_systems: List[str]
    suggested_name: str
    pattern_type: str = "api"  # api 或 page


class BusinessFromPattern(BaseModel):
    """从模式创建 Business 的请求"""
    fingerprint: str
    name: str
    display_name: Optional[str] = None
    attributes: Optional[dict] = None
    # 统一的 URL 模式
    frontend_urls: Optional[List[str]] = None  # L1: 前端页面 URL
    api_urls: Optional[List[str]] = None  # L1: API URL
    url_patterns: Optional[List[str]] = None  # 兼容旧接口
    include_services: Optional[List[str]] = None
    exclude_services: Optional[List[str]] = None


class BusinessEdit(BaseModel):
    """手动编辑 Business"""
    name: Optional[str] = None
    display_name: Optional[str] = None
    # 统一的 URL 模式
    frontend_urls: Optional[List[str]] = None  # 前端页面 URL 模式
    api_urls: Optional[List[str]] = None  # API URL 模式
    url_patterns: Optional[List[str]] = None  # 兼容旧接口
    include_services: Optional[List[str]] = None
    exclude_services: Optional[List[str]] = None
    attributes: Optional[dict] = None


class UrlMappingRule(BaseModel):
    """URL 映射规则"""
    url_pattern: str
    mapping_type: str  # "frontend" 或 "api"
    business_name: Optional[str] = None


# ============================================================
# L2: 自动发现
# ============================================================

def _infer_business_name(root_url: str, services: List[str]) -> str:
    """从 URL 和服务名推断业务名称。"""
    url_patterns = {
        '/order': '订单业务',
        '/pay': '支付业务',
        '/payment': '支付业务',
        '/user': '用户业务',
        '/login': '登录业务',
        '/register': '注册业务',
        '/product': '商品业务',
        '/inventory': '库存业务',
        '/search': '搜索业务',
        '/cart': '购物车业务',
        '/checkout': '结算业务',
        '/notify': '通知业务',
        '/shipping': '物流业务',
    }
    
    # 从 URL 推断
    for pattern, name in url_patterns.items():
        if pattern in root_url.lower():
            return name
    
    # 从服务名推断
    service_patterns = {
        'order': '订单业务',
        'payment': '支付业务',
        'user': '用户业务',
        'product': '商品业务',
        'inventory': '库存业务',
        'search': '搜索业务',
        'cart': '购物车业务',
    }
    
    for svc in services:
        for pattern, name in service_patterns.items():
            if pattern in svc.lower():
                return name
    
    # 默认使用 URL 路径
    path = root_url.split('?')[0].split('/')[-1] or 'unknown'
    return f"业务-{path}"


@router.get("/business-discovery/patterns")
async def discover_business_patterns(
    hours: int = Query(24, description="分析时间范围(小时)"),
    min_traces: int = Query(10, description="最小调用次数阈值"),
    pattern_type: Optional[str] = Query(None, description="模式类型: api/page/all"),
):
    """从 ClickHouse 自动发现业务模式 (L2 方案)。
    
    分析两种数据源：
    1. traces.spans - 后端 API 调用链
    2. traces.spans (前端页面) - 前端页面请求
    
    识别：
    1. API 入口模式（后端）
    2. 页面入口模式（前端）
    3. 调用链结构
    4. 模式聚类
    """
    patterns = []
    
    # 如果不是只查 page，查询 API 模式
    if pattern_type != "page":
        # 查询后端 API 入口
        api_sql = f"""
        WITH root_spans AS (
            SELECT 
                trace_id,
                span_id as root_span_id,
                service_name as root_service,
                http_url as root_url,
                http_method as root_method,
                duration_ms as total_duration,
                status_code
            FROM traces.spans
            WHERE parent_span_id = ''
              AND start_time > now() - INTERVAL {hours} HOUR
              AND service_name != ''  -- 排除前端页面
        ),
        chain_components AS (
            SELECT
                r.trace_id,
                r.root_span_id,
                r.root_service,
                r.root_url,
                r.root_method,
                r.total_duration,
                r.status_code,
                s.service_name,
                s.endpoint,
                s.db_system
            FROM root_spans r
            JOIN traces.spans s ON r.trace_id = s.trace_id
        ),
        patterns AS (
            SELECT
                root_service,
                root_url,
                root_method,
                cityHash64(arrayStringConcat(
                    groupArray(DISTINCT service_name || ':' || coalesce(endpoint, db_system, 'service')),
                    '|'
                )) as fingerprint,
                count(DISTINCT trace_id) as trace_count,
                avg(total_duration) as avg_duration_ms,
                countIf(status_code = 'error') * 100.0 / count(DISTINCT trace_id) as error_rate,
                groupArray(DISTINCT service_name) as services,
                groupArray(DISTINCT endpoint) as endpoints,
                groupArray(DISTINCT db_system) as db_systems
            FROM chain_components
            GROUP BY root_service, root_url, root_method
            HAVING trace_count >= {min_traces}
        )
        SELECT *, 'api' as pattern_type
        FROM patterns
        ORDER BY trace_count DESC
        LIMIT 30
        FORMAT JSON
        """
        
        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(CLICKHOUSE_URL, data=api_sql)
                if r.status_code == 200:
                    for row in r.json().get("data", []):
                        db_systems = [d for d in row.get('db_systems', []) if d]
                        services = [s for s in row.get('services', []) if s]
                        endpoints = [e for e in row.get('endpoints', []) if e]
                        
                        suggested_name = _infer_business_name(row.get('root_url', ''), services)
                        
                        patterns.append(DiscoveredPattern(
                            fingerprint=str(row.get('fingerprint', '')),
                            root_service=row.get('root_service', ''),
                            root_url=row.get('root_url', ''),
                            root_method=row.get('root_method', ''),
                            trace_count=row.get('trace_count', 0),
                            avg_duration_ms=round(row.get('avg_duration_ms', 0), 2),
                            error_rate=round(row.get('error_rate', 0), 2),
                            services=services[:10],
                            endpoints=endpoints[:15],
                            db_systems=db_systems,
                            suggested_name=suggested_name,
                            pattern_type="api",
                        ))
        except Exception as e:
            logger.error(f"API pattern discovery failed: {e}")
    
    # 如果不是只查 api，查询页面模式
    if pattern_type != "api":
        # 从 spans 中提取前端页面请求（通常 http_url 是页面路径）
        page_sql = f"""
        SELECT 
            http_url as page_url,
            count() as visit_count,
            avg(duration_ms) as avg_duration_ms,
            countIf(status_code = 'error') * 100.0 / count() as error_rate,
            groupArray(DISTINCT service_name) as services
        FROM traces.spans
        WHERE start_time > now() - INTERVAL {hours} HOUR
          AND http_url LIKE '/%'  -- 页面路径
          AND http_url NOT LIKE '/api/%'  -- 排除 API
          AND (service_name = '' OR service_name LIKE '%frontend%' OR service_name LIKE '%page%')
        GROUP BY page_url
        HAVING visit_count >= {min_traces}
        ORDER BY visit_count DESC
        LIMIT 20
        FORMAT JSON
        """
        
        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(CLICKHOUSE_URL, data=page_sql)
                if r.status_code == 200:
                    for row in r.json().get("data", []):
                        page_url = row.get('page_url', '')
                        services = [s for s in row.get('services', []) if s]
                        
                        # 生成指纹
                        fingerprint = hashlib.md5(f"page:{page_url}".encode()).hexdigest()[:16]
                        
                        # 推断业务名称
                        suggested_name = _infer_business_name(page_url, [])
                        
                        patterns.append(DiscoveredPattern(
                            fingerprint=fingerprint,
                            root_service="frontend",
                            root_url=page_url,
                            root_method="GET",
                            trace_count=row.get('visit_count', 0),
                            avg_duration_ms=round(row.get('avg_duration_ms', 0), 2),
                            error_rate=round(row.get('error_rate', 0), 2),
                            services=services,
                            endpoints=[],
                            db_systems=[],
                            suggested_name=suggested_name,
                            pattern_type="page",
                        ))
        except Exception as e:
            logger.error(f"Page pattern discovery failed: {e}")
    
    # 按调用次数排序
    patterns.sort(key=lambda x: x.trace_count, reverse=True)
    
    return {
        "total": len(patterns),
        "patterns": patterns,
        "analysis_range": f"{hours} hours",
        "pattern_types": {
            "api": len([p for p in patterns if p.pattern_type == "api"]),
            "page": len([p for p in patterns if p.pattern_type == "page"]),
        },
    }


@router.get("/business-discovery/preview/{fingerprint}")
async def preview_business_pattern(
    fingerprint: str,
    hours: int = Query(24),
    session: AsyncSession = Depends(get_session),
):
    """预览业务模式的详细信息。
    
    返回该模式下的调用链示例、关联的实体等。
    """
    # 查询该模式下的 trace 示例
    sql = f"""
    WITH root_traces AS (
        SELECT DISTINCT trace_id
        FROM traces.spans
        WHERE parent_span_id = ''
          AND start_time > now() - INTERVAL {hours} HOUR
        LIMIT 1000
    )
    SELECT 
        trace_id,
        service_name,
        endpoint,
        http_url,
        duration_ms,
        status_code,
        parent_span_id
    FROM traces.spans
    WHERE trace_id IN (SELECT trace_id FROM root_traces)
    ORDER BY trace_id, start_time_us
    LIMIT 500
    FORMAT JSON
    """
    
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(CLICKHOUSE_URL, data=sql)
            spans = r.json().get("data", []) if r.status_code == 200 else []
        
        # 按 trace_id 分组
        traces = {}
        for span in spans:
            tid = span.get('trace_id', '')
            if tid not in traces:
                traces[tid] = []
            traces[tid].append(span)
        
        # 查找关联的 CMDB 实体
        related_entities = []
        services_set = set()
        for span in spans[:50]:
            svc = span.get('service_name', '')
            if svc and svc not in services_set:
                services_set.add(svc)
                # 查询 CMDB 中的实体
                result = await session.execute(
                    select(Entity).where(Entity.name == svc).limit(1)
                )
                entity = result.scalar_one_or_none()
                if entity:
                    related_entities.append({
                        "guid": str(entity.guid),
                        "name": entity.name,
                        "type_name": entity.type_name,
                        "health_score": entity.health_score,
                    })
        
        return {
            "fingerprint": fingerprint,
            "sample_traces": list(traces.values())[:5],
            "related_entities": related_entities,
            "total_spans": len(spans),
        }
        
    except Exception as e:
        logger.error(f"Preview failed: {e}")
        raise HTTPException(500, str(e))


# ============================================================
# 从模式创建 Business (L2 + L1)
# ============================================================

@router.post("/business-discovery/create")
async def create_business_from_pattern(
    body: BusinessFromPattern,
    session: AsyncSession = Depends(get_session),
):
    """从业务模式创建 Business 实体。
    
    支持 L2 自动发现 + L1 手动编辑：
    - 自动关联 services
    - 手动定义 frontend_urls (前端页面)
    - 手动定义 api_urls (API 入口)
    - 手动选择/排除 services
    """
    # 检查是否已存在
    existing = await session.execute(
        select(Entity).where(
            Entity.type_name == "Business",
            Entity.name == body.name
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Business '{body.name}' already exists")
    
    # 获取类型定义
    type_def = await session.get(EntityTypeDef, "Business")
    if not type_def:
        raise HTTPException(404, "Business type not found")
    
    # 构建统一的 URL 模式
    url_patterns = {
        "frontend": body.frontend_urls or [],
        "api": body.api_urls or [],
        "auto_discovered": body.url_patterns or [],  # 兼容旧接口
    }
    
    # 构建 attributes
    attributes = body.attributes or {}
    attributes.update({
        "auto_discovered": True,
        "fingerprint": body.fingerprint,
        "source": "trace_topology",
        "url_patterns": url_patterns,
    })
    
    # 创建 Business 实体
    entity = Entity(
        type_name="Business",
        name=body.name,
        qualified_name=f"Business:{body.name}",
        attributes=attributes,
        labels={"source": "auto_discovery"},
    )
    session.add(entity)
    await session.flush()
    
    # 关联 services
    services_to_include = body.include_services or []
    if not services_to_include:
        # 如果没有手动选择，从模式中获取
        sql = f"""
        SELECT DISTINCT service_name
        FROM traces.spans
        WHERE trace_id IN (
            SELECT trace_id FROM traces.spans
            WHERE parent_span_id = ''
            LIMIT 100
        )
        AND service_name != ''
        FORMAT JSON
        """
        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(CLICKHOUSE_URL, data=sql)
                if r.status_code == 200:
                    services_to_include = [
                        row['service_name'] 
                        for row in r.json().get('data', [])
                        if row.get('service_name')
                    ]
        except:
            pass
    
    # 排除指定的 services
    if body.exclude_services:
        services_to_include = [
            s for s in services_to_include 
            if s not in body.exclude_services
        ]
    
    # 创建关系
    rel_count = 0
    for svc_name in services_to_include:
        result = await session.execute(
            select(Entity).where(Entity.name == svc_name).limit(1)
        )
        svc_entity = result.scalar_one_or_none()
        if svc_entity:
            rel = Relationship(
                type_name="includes",
                dimension="vertical",
                end1_guid=entity.guid,
                end2_guid=svc_entity.guid,
                source="auto_discovery",
                confidence=0.9,
            )
            session.add(rel)
            rel_count += 1
    
    await session.commit()
    await session.refresh(entity)
    
    return {
        "guid": str(entity.guid),
        "name": entity.name,
        "created": True,
        "relations_created": rel_count,
        "url_patterns": url_patterns,
        "message": f"Business '{body.name}' created with {rel_count} service relations",
    }


# ============================================================
# L1: 手动编辑
# ============================================================

@router.put("/business-discovery/{entity_id}")
async def edit_business(
    entity_id: str,
    body: BusinessEdit,
    session: AsyncSession = Depends(get_session),
):
    """手动编辑 Business 配置 (L1 方案)。
    
    支持：
    - 修改前端页面 URL 模式 (frontend_urls)
    - 修改 API URL 模式 (api_urls)
    - 添加/移除关联的 services
    - 更新属性
    """
    import uuid
    try:
        eid = uuid.UUID(entity_id)
    except ValueError:
        raise HTTPException(400, "Invalid UUID")
    
    entity = await session.get(Entity, eid)
    if not entity:
        raise HTTPException(404, "Business not found")
    
    # 更新基本信息
    if body.name:
        entity.name = body.name
        entity.qualified_name = f"Business:{body.name}"
    if body.display_name:
        entity.attributes = entity.attributes or {}
        entity.attributes['display_name'] = body.display_name
    
    # 更新统一的 URL 模式 (L1)
    entity.attributes = entity.attributes or {}
    current_url_patterns = entity.attributes.get('url_patterns', {})
    
    # 兼容旧格式（如果 url_patterns 是列表）
    if isinstance(current_url_patterns, list):
        current_url_patterns = {"api": current_url_patterns, "frontend": [], "auto_discovered": []}
    
    # 更新各类型的 URL
    if body.frontend_urls is not None:
        current_url_patterns['frontend'] = body.frontend_urls
    if body.api_urls is not None:
        current_url_patterns['api'] = body.api_urls
    if body.url_patterns is not None:
        current_url_patterns['auto_discovered'] = body.url_patterns
    
    entity.attributes['url_patterns'] = current_url_patterns
    
    # 更新其他属性
    if body.attributes:
        entity.attributes.update(body.attributes)
    
    # 处理 services 关联
    if body.include_services:
        for svc_name in body.include_services:
            result = await session.execute(
                select(Entity).where(Entity.name == svc_name).limit(1)
            )
            svc_entity = result.scalar_one_or_none()
            if svc_entity:
                # 检查关系是否已存在
                existing_rel = await session.execute(
                    select(Relationship).where(
                        Relationship.end1_guid == entity.guid,
                        Relationship.end2_guid == svc_entity.guid,
                        Relationship.type_name == "includes",
                    ).limit(1)
                )
                if not existing_rel.scalar_one_or_none():
                    rel = Relationship(
                        type_name="includes",
                        dimension="vertical",
                        end1_guid=entity.guid,
                        end2_guid=svc_entity.guid,
                        source="manual",
                        confidence=1.0,
                    )
                    session.add(rel)
    
    if body.exclude_services:
        for svc_name in body.exclude_services:
            result = await session.execute(
                select(Entity).where(Entity.name == svc_name).limit(1)
            )
            svc_entity = result.scalar_one_or_none()
            if svc_entity:
                # 删除关系
                await session.execute(
                    Relationship.__table__.delete().where(
                        Relationship.end1_guid == entity.guid,
                        Relationship.end2_guid == svc_entity.guid,
                        Relationship.type_name == "includes",
                    )
                )
    
    await session.commit()
    await session.refresh(entity)
    
    return {
        "guid": str(entity.guid),
        "name": entity.name,
        "updated": True,
        "url_patterns": entity.attributes.get('url_patterns', {}),
    }


@router.get("/business-discovery/list")
async def list_businesses(
    source: Optional[str] = Query(None, description="过滤来源: auto_discovery/manual"),
    session: AsyncSession = Depends(get_session),
):
    """列出所有 Business 实体，标注来源（自动发现/手动创建）。
    
    返回统一的 URL 模式：
    - frontend: 前端页面 URL
    - api: API URL
    - auto_discovered: L2 自动发现的 URL
    """
    result = await session.execute(
        select(Entity).where(Entity.type_name == "Business")
    )
    entities = result.scalars().all()
    
    items = []
    for e in entities:
        attrs = e.attributes or {}
        is_auto = attrs.get('auto_discovered', False)
        
        if source == 'auto_discovery' and not is_auto:
            continue
        if source == 'manual' and is_auto:
            continue
        
        # 获取统一的 URL 模式
        url_patterns = attrs.get('url_patterns', {})
        if isinstance(url_patterns, list):
            # 兼容旧格式
            url_patterns = {"api": url_patterns, "frontend": [], "auto_discovered": []}
        
        items.append({
            "guid": str(e.guid),
            "name": e.name,
            "health_score": e.health_score,
            "health_level": e.health_level,
            "auto_discovered": is_auto,
            "fingerprint": attrs.get('fingerprint', ''),
            "url_patterns": url_patterns,
            "frontend_urls": url_patterns.get('frontend', []),
            "api_urls": url_patterns.get('api', []),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })
    
    return {
        "total": len(items),
        "items": items,
    }
