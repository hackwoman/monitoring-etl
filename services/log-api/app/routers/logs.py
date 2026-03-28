"""Log query API routes."""
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from app.clickhouse import query

router = APIRouter()


class LogSearchRequest(BaseModel):
    search_text: Optional[str] = None
    service_name: Optional[str] = None
    host_name: Optional[str] = None
    level: Optional[str] = None
    start_time: Optional[str] = None  # ISO format
    end_time: Optional[str] = None
    labels: dict = Field(default_factory=dict)
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


@router.post("/search")
async def search_logs(body: LogSearchRequest):
    """Search logs with filters."""
    conditions = ["1=1"]

    if body.search_text:
        escaped = body.search_text.replace("'", "\\'")
        conditions.append(f"message LIKE '%{escaped}%'")
    if body.service_name:
        conditions.append(f"service_name = '{body.service_name}'")
    if body.host_name:
        conditions.append(f"host_name = '{body.host_name}'")
    if body.level:
        conditions.append(f"level = '{body.level}'")
    if body.start_time:
        conditions.append(f"timestamp >= '{body.start_time}'")
    if body.end_time:
        conditions.append(f"timestamp <= '{body.end_time}'")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT timestamp, service_name, host_name, level, message, labels
        FROM logs.log_entries
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT {body.limit} OFFSET {body.offset}
    """
    results = await query(sql)
    return {"total": len(results), "items": results}


@router.get("/search")
async def search_logs_get(
    q: Optional[str] = Query(None, description="Search text"),
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    start: Optional[str] = Query(None, description="Start time (ISO)"),
    end: Optional[str] = Query(None, description="End time (ISO)"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Search logs via GET (for simple queries)."""
    conditions = ["1=1"]

    if q:
        escaped = q.replace("'", "\\'")
        conditions.append(f"message LIKE '%{escaped}%'")
    if service:
        conditions.append(f"service_name = '{service}'")
    if level:
        conditions.append(f"level = '{level}'")
    if start:
        conditions.append(f"timestamp >= '{start}'")
    if end:
        conditions.append(f"timestamp <= '{end}'")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT timestamp, service_name, host_name, level, message, labels
        FROM logs.log_entries
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT {limit}
    """
    results = await query(sql)
    return {"total": len(results), "items": results}


@router.get("/aggregation")
async def log_aggregation(
    group_by: str = Query("level", description="Group by field: level/service_name/host_name"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    interval: str = Query("1h", description="Time interval for histogram"),
):
    """Aggregate logs by field or time bucket."""
    conditions = ["1=1"]
    if start:
        conditions.append(f"timestamp >= '{start}'")
    if end:
        conditions.append(f"timestamp <= '{end}'")

    where = " AND ".join(conditions)

    # Count by group
    sql = f"""
        SELECT {group_by}, count() as count
        FROM logs.log_entries
        WHERE {where}
        GROUP BY {group_by}
        ORDER BY count DESC
        LIMIT 50
    """
    results = await query(sql)
    return {"group_by": group_by, "items": results}


@router.get("/completeness")
async def data_completeness(
    source_id: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
):
    """Check data completeness."""
    conditions = [f"time_bucket >= now() - INTERVAL {hours} HOUR"]
    if source_id:
        conditions.append(f"source_id = '{source_id}'")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT source_id, time_bucket, actual_count, gap_seconds, status
        FROM logs.data_completeness
        WHERE {where}
        ORDER BY time_bucket DESC
        LIMIT 100
    """
    results = await query(sql)
    return {"items": results}
