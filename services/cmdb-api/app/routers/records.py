"""统一记录查询 API — 查询 ClickHouse records 表。"""

import logging
from typing import Optional
from datetime import datetime

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["records"])

CLICKHOUSE_URL = "http://47.93.61.196:8123"


@router.get("/records")
async def list_records(
    record_type: Optional[str] = Query(None),
    entity_guid: Optional[str] = Query(None),
    entity_name: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_status: Optional[str] = Query(None),
    time_range: str = Query("1h", description="时间范围: 1h/6h/24h/7d"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """查询统一记录（ClickHouse）。"""
    # 时间范围映射
    range_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}
    hours = range_map.get(time_range, 1)

    conditions = [f"timestamp > now() - INTERVAL {hours} HOUR"]

    if record_type:
        conditions.append(f"record_type = '{record_type}'")
    if entity_guid:
        conditions.append(f"entity_guid = toUUID('{entity_guid}')")
    if entity_name:
        conditions.append(f"entity_name LIKE '%{entity_name}%'")
    if severity:
        conditions.append(f"severity = '{severity}'")
    if alert_status:
        conditions.append(f"alert_status = '{alert_status}'")

    where = " AND ".join(conditions)

    count_sql = f"SELECT count() as cnt FROM records WHERE {where} FORMAT JSON"
    sql = f"""
    SELECT record_id, record_type, source, timestamp,
           entity_guid, entity_name, entity_type,
           severity, title, fingerprint, alert_status
    FROM records
    WHERE {where}
    ORDER BY timestamp DESC
    LIMIT {limit} OFFSET {offset}
    FORMAT JSON
    """

    try:
        with httpx.Client(timeout=15) as client:
            # Count
            r = client.post(CLICKHOUSE_URL, data=count_sql)
            total = 0
            if r.status_code == 200:
                total = r.json().get("data", [{}])[0].get("cnt", 0)

            # Query
            r = client.post(CLICKHOUSE_URL, data=sql)
            items = []
            if r.status_code == 200:
                items = r.json().get("data", [])

            return {
                "total": total,
                "items": items,
                "limit": limit,
                "offset": offset,
                "time_range": time_range,
            }
    except Exception as e:
        logger.error(f"ClickHouse query failed: {e}")
        return {"total": 0, "items": [], "error": str(e)}
