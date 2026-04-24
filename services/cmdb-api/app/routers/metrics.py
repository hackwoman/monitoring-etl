"""指标时间序列查询 API — 分位数/降采样/维度分组。"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])

CLICKHOUSE_URL = "http://47.93.61.196:8123"


class MetricsQueryParams(BaseModel):
    """指标查询参数"""
    entity_guid: Optional[str] = None
    entity_type: Optional[str] = None
    metric_name: Optional[str] = None
    start_time: str
    end_time: str
    granularity: str = Field("5m", description="降采样粒度: 1m/5m/1h/1d")
    quantiles: List[float] = Field(
        default=[0.5, 0.75, 0.9, 0.99],
        description="分位数列表"
    )
    group_by: Optional[str] = Field(
        None,
        description="分组维度: entity_guid/entity_type/metric_name"
    )


class TimeSeriesPoint(BaseModel):
    """时序数据点"""
    time: str
    entity_guid: Optional[str] = None
    entity_type: Optional[str] = None
    metric_name: Optional[str] = None
    min: float
    max: float
    avg: float
    count: int
    p50: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    p99: Optional[float] = None


class MetricsQueryResponse(BaseModel):
    """查询响应"""
    total_points: int
    series: List[TimeSeriesPoint]
    query_time_ms: float
    granularity: str
    time_range: dict


def get_granularity_func(granularity: str) -> str:
    """获取 ClickHouse 时间桶函数"""
    funcs = {
        "1m": "toStartOfMinute",
        "5m": "toStartOfFiveMinute",
        "1h": "toStartOfHour",
        "1d": "toStartOfDay",
    }
    return funcs.get(granularity, "toStartOfFiveMinute")


@router.get("/metrics/query")
async def query_metrics(
    entity_guid: Optional[str] = Query(None, description="实体 GUID"),
    entity_type: Optional[str] = Query(None, description="实体类型"),
    metric_name: Optional[str] = Query(None, description="指标名称"),
    start: str = Query(..., description="开始时间 (ISO 8601)"),
    end: str = Query(..., description="结束时间 (ISO 8601)"),
    granularity: str = Query("5m", description="降采样粒度: 1m/5m/1h/1d"),
    group_by: Optional[str] = Query(None, description="分组维度"),
):
    """
    查询指标时序数据（含分位数）。

    支持：
    - 按实体/类型/指标筛选
    - 分位数聚合（P50/P75/P90/P99）
    - 降采样（1m/5m/1h/1d）
    - 分组查询
    """
    import time
    start_time = time.time()

    # 构建 WHERE 条件
    conditions = []
    if entity_guid:
        conditions.append(f"entity_guid = toUUID('{entity_guid}')")
    if entity_type:
        conditions.append(f"entity_type = '{entity_type}'")
    if metric_name:
        conditions.append(f"metric_name = '{metric_name}'")
    
    conditions.append(f"timestamp >= '{start}'")
    conditions.append(f"timestamp <= '{end}'")

    where = " AND ".join(conditions) if conditions else "1=1"
    bucket_func = get_granularity_func(granularity)

    # 分组字段
    group_fields = ""
    select_extra = ""
    if group_by:
        if group_by == "entity_guid":
            group_fields = ", entity_guid"
            select_extra = ", entity_guid"
        elif group_by == "entity_type":
            group_fields = ", entity_type"
            select_extra = ", entity_type"
        elif group_by == "metric_name":
            group_fields = ", metric_name"
            select_extra = ", metric_name"

    # 查询 SQL
    sql = f"""
    SELECT
        {bucket_func}(timestamp) AS bucket{select_extra},
        min(value) AS min_val,
        max(value) AS max_val,
        avg(value) AS avg_val,
        count() AS cnt,
        quantile(0.5)(value) AS p50,
        quantile(0.75)(value) AS p75,
        quantile(0.9)(value) AS p90,
        quantile(0.99)(value) AS p99
    FROM metrics_timeseries
    WHERE {where}
    GROUP BY bucket{group_fields}
    ORDER BY bucket ASC
    FORMAT JSON
    """

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(CLICKHOUSE_URL, data=sql)
            
            if r.status_code != 200:
                logger.error(f"ClickHouse query failed: {r.status_code} {r.text}")
                return {"error": f"Query failed: {r.status_code}", "series": []}

            data = r.json().get("data", [])
            elapsed_ms = (time.time() - start_time) * 1000

            # 转换结果
            series = []
            for row in data:
                point = {
                    "time": row.get("bucket", ""),
                    "min": round(float(row.get("min_val", 0)), 4),
                    "max": round(float(row.get("max_val", 0)), 4),
                    "avg": round(float(row.get("avg_val", 0)), 4),
                    "count": int(row.get("cnt", 0)),
                    "p50": round(float(row.get("p50", 0)), 4),
                    "p75": round(float(row.get("p75", 0)), 4),
                    "p90": round(float(row.get("p90", 0)), 4),
                    "p99": round(float(row.get("p99", 0)), 4),
                }
                # 添加分组字段
                if group_by:
                    point[group_by] = row.get(group_by, "")
                series.append(point)

            return {
                "total_points": len(series),
                "series": series,
                "query_time_ms": round(elapsed_ms, 2),
                "granularity": granularity,
                "time_range": {"start": start, "end": end}
            }

    except Exception as e:
        logger.error(f"Metrics query failed: {e}")
        return {"error": str(e), "series": []}


@router.get("/metrics/available")
async def get_available_metrics(
    entity_type: Optional[str] = Query(None),
    entity_guid: Optional[str] = Query(None),
):
    """获取可用的指标列表（从已有数据中）"""
    conditions = []
    if entity_type:
        conditions.append(f"entity_type = '{entity_type}'")
    if entity_guid:
        conditions.append(f"entity_guid = toUUID('{entity_guid}')")
    
    where = " AND ".join(conditions) if conditions else "1=1"

    sql = f"""
    SELECT
        entity_type,
        metric_name,
        metric_unit,
        count() AS data_points,
        min(timestamp) AS first_seen,
        max(timestamp) AS last_seen
    FROM metrics_timeseries
    WHERE {where}
    GROUP BY entity_type, metric_name, metric_unit
    ORDER BY entity_type, metric_name
    FORMAT JSON
    """

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(CLICKHOUSE_URL, data=sql)
            if r.status_code == 200:
                return {"items": r.json().get("data", [])}
            return {"items": [], "error": f"Status {r.status_code}"}
    except Exception as e:
        return {"items": [], "error": str(e)}


@router.get("/metrics/entity/{entity_guid}/summary")
async def get_entity_metrics_summary(
    entity_guid: str,
    time_range: str = Query("1h", description="时间范围: 1h/6h/24h/7d"),
):
    """获取实体的指标摘要（最新值 + 趋势）"""
    range_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}
    hours = range_map.get(time_range, 1)

    sql = f"""
    SELECT
        metric_name,
        metric_unit,
        argMax(value, timestamp) AS current_value,
        avg(value) AS avg_value,
        min(value) AS min_value,
        max(value) AS max_value,
        count() AS data_points,
        quantile(0.5)(value) AS p50,
        quantile(0.9)(value) AS p90
    FROM metrics_timeseries
    WHERE entity_guid = toUUID('{entity_guid}')
      AND timestamp > now() - INTERVAL {hours} HOUR
    GROUP BY metric_name, metric_unit
    ORDER BY metric_name
    FORMAT JSON
    """

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(CLICKHOUSE_URL, data=sql)
            if r.status_code == 200:
                items = []
                for row in r.json().get("data", []):
                    items.append({
                        "metric_name": row["metric_name"],
                        "metric_unit": row["metric_unit"],
                        "current_value": round(float(row["current_value"]), 4),
                        "avg_value": round(float(row["avg_value"]), 4),
                        "min_value": round(float(row["min_value"]), 4),
                        "max_value": round(float(row["max_value"]), 4),
                        "p50": round(float(row["p50"]), 4),
                        "p90": round(float(row["p90"]), 4),
                        "data_points": int(row["data_points"]),
                    })
                return {
                    "entity_guid": entity_guid,
                    "time_range": time_range,
                    "metrics": items
                }
            return {"metrics": [], "error": f"Status {r.status_code}"}
    except Exception as e:
        return {"metrics": [], "error": str(e)}
