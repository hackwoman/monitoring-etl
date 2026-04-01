"""AI 问答 API - 基础版（关键词解析）。"""

import re
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

CMDB_API = os.getenv("CMDB_API_URL", "http://8001/api/v1/cmdb")
CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://47.93.61.196:8123")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")


class ChatResponse(BaseModel):
    reply: str
    data: Optional[Dict[str, Any]] = None
    charts: Optional[List[Dict]] = None


def cmdb_get(path: str) -> Optional[dict]:
    """调用 CMDB API GET。"""
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{CMDB_API}{path}")
            if r.status_code == 200:
                return r.json()
        return None
    except:
        return None


def ch_query(sql: str) -> Optional[list]:
    """查询 ClickHouse。"""
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(CLICKHOUSE_URL, content=sql.encode('utf-8'))
            if r.status_code == 200:
                return r.json().get("data", [])
        return None
    except:
        return None


# ============================================================
# 关键词匹配引擎
# ============================================================

def handle_health_query(entity_name: str) -> ChatResponse:
    """查询实体健康度。"""
    result = cmdb_get(f"/entities?search={entity_name}")
    if not result or not result.get("items"):
        return ChatResponse(reply=f"未找到实体: {entity_name}")

    entity = result["items"][0]
    health_score = entity.get("health_score")
    health_level = entity.get("health_level", "unknown")
    risk_score = entity.get("risk_score")

    level_emoji = {
        "healthy": "🟢", "warning": "🟡", "critical": "🔴", "down": "⚫"
    }.get(health_level, "⚪")

    reply = f"{level_emoji} **{entity['name']}** ({entity['type_name']})\n"
    if health_score is not None:
        reply += f"- 健康评分: {health_score}/100\n"
    reply += f"- 健康等级: {health_level}\n"
    if risk_score is not None:
        reply += f"- 风险评分: {risk_score}/100\n"

    return ChatResponse(
        reply=reply,
        data={"entity": entity}
    )


def handle_abnormal_query() -> ChatResponse:
    """查询异常实体。"""
    result = cmdb_get("/entities?health_level=critical&limit=20")
    result2 = cmdb_get("/entities?health_level=warning&limit=20")
    result3 = cmdb_get("/entities?health_level=down&limit=20")

    abnormal = []
    for r in [result, result2, result3]:
        if r and r.get("items"):
            abnormal.extend(r["items"])

    if not abnormal:
        return ChatResponse(reply="🟢 当前没有异常实体，一切正常！")

    # 按风险度排序
    abnormal.sort(key=lambda x: x.get("risk_score") or 0, reverse=True)

    reply = f"🔴 当前有 {len(abnormal)} 个异常实体:\n\n"
    for e in abnormal[:10]:
        emoji = {"critical": "🔴", "warning": "🟡", "down": "⚫"}.get(e.get("health_level"), "⚪")
        reply += f"{emoji} {e['name']} ({e['type_name']}) — 健康:{e.get('health_score', '?')} 风险:{e.get('risk_score', '?')}\n"

    return ChatResponse(reply=reply, data={"entities": abnormal})


def handle_count_query(type_name: str) -> ChatResponse:
    """按类型统计实体数量。"""
    type_name_map = {
        "服务": "Service", "主机": "Host", "数据库": "Database",
        "业务": "Business", "中间件": "Middleware", "网络设备": "NetworkDevice",
        "service": "Service", "host": "Host", "database": "Database",
        "business": "Business", "middleware": "Middleware",
    }
    mapped_type = type_name_map.get(type_name.lower(), type_name)

    result = cmdb_get(f"/entities?type_name={mapped_type}&limit=500")
    if result:
        count = result.get("total", len(result.get("items", [])))
        return ChatResponse(
            reply=f"📦 {mapped_type} 类型共有 **{count}** 个实体。",
            data={"type": mapped_type, "count": count}
        )
    return ChatResponse(reply=f"未找到 {mapped_type} 类型的实体。")


def handle_dependency_query(entity_name: str) -> ChatResponse:
    """查询实体依赖关系。"""
    result = cmdb_get(f"/entities?search={entity_name}")
    if not result or not result.get("items"):
        return ChatResponse(reply=f"未找到实体: {entity_name}")

    entity = result["items"][0]
    rels = cmdb_get(f"/entities/{entity['guid']}/relations")
    if not rels or not rels.get("items"):
        return ChatResponse(reply=f"{entity['name']} 没有已知的依赖关系。")

    reply = f"🔗 **{entity['name']}** 的关系:\n\n"
    for rel in rels["items"]:
        direction = "→" if rel.get("end1_guid") == entity["guid"] else "←"
        reply += f"  {direction} {rel['type_name']}: {rel.get('end2_name', rel.get('end1_name', '?'))}\n"

    return ChatResponse(reply=reply, data={"relations": rels["items"]})


def handle_slowest_query() -> ChatResponse:
    """查询最慢的服务（从 Trace 数据）。"""
    sql = """
    SELECT service_name, endpoint,
           round(avg(duration_ms), 2) as avg_latency,
           round(quantile(0.99)(duration_ms), 2) as p99_latency,
           count() as call_count
    FROM traces.spans
    WHERE start_time > now() - INTERVAL 1 HOUR
      AND span_kind = 'client'
    GROUP BY service_name, endpoint
    ORDER BY p99_latency DESC
    LIMIT 10
    FORMAT JSON
    """
    data = ch_query(sql)
    if not data:
        return ChatResponse(reply="⚠️ 暂无 Trace 数据，请先生成 Trace。")

    reply = "🐌 **最慢的接口**（最近1小时 P99 延迟）:\n\n"
    for row in data:
        reply += f"  {row['service_name']}.{row['endpoint']} — P99: {row['p99_latency']:.1f}ms (×{row['call_count']})\n"

    return ChatResponse(reply=reply, data={"slowest": data})


def handle_error_query() -> ChatResponse:
    """查询错误率最高的服务。"""
    sql = """
    SELECT service_name,
           count() as total,
           countIf(status_code = 'error') as errors,
           round(countIf(status_code = 'error') * 100.0 / count(), 2) as error_rate
    FROM traces.spans
    WHERE start_time > now() - INTERVAL 1 HOUR
    GROUP BY service_name
    HAVING errors > 0
    ORDER BY error_rate DESC
    LIMIT 10
    FORMAT JSON
    """
    data = ch_query(sql)
    if not data:
        return ChatResponse(reply="🟢 最近1小时没有检测到错误。")

    reply = "❌ **错误率最高的服务**（最近1小时）:\n\n"
    for row in data:
        reply += f"  {row['service_name']} — 错误率: {row['error_rate']}% ({row['errors']}/{row['total']})\n"

    return ChatResponse(reply=reply, data={"errors": data})


# ============================================================
# 主入口
# ============================================================

def parse_and_respond(message: str) -> ChatResponse:
    """关键词解析 + 路由到对应处理函数。"""
    msg = message.strip().lower()

    # 1. 健康度查询："XX 的健康度" / "XX 健康" / "XX status"
    health_patterns = [
        r'(.+?)的健康度', r'(.+?)健康', r'(.+?) status',
        r'(.+?)怎么样', r'(.+?)状态',
    ]
    for pattern in health_patterns:
        m = re.search(pattern, msg)
        if m:
            return handle_health_query(m.group(1).strip())

    # 2. 异常查询："异常" / "问题" / "出错"
    if any(kw in msg for kw in ['异常', '问题', '出错', '故障', 'abnormal', 'issue', 'problem']):
        return handle_abnormal_query()

    # 3. 数量查询："有多少个 XX" / "XX 数量"
    count_patterns = [
        r'有多少个(.+)', r'(.+?)数量', r'(.+?)有多少',
        r'how many (.+)', r'count (.+)',
    ]
    for pattern in count_patterns:
        m = re.search(pattern, msg)
        if m:
            return handle_count_query(m.group(1).strip())

    # 4. 依赖查询："XX 依赖" / "XX 关系"
    dep_patterns = [
        r'(.+?)依赖', r'(.+?)关系', r'(.+?) depends',
    ]
    for pattern in dep_patterns:
        m = re.search(pattern, msg)
        if m:
            return handle_dependency_query(m.group(1).strip())

    # 5. 最慢查询："最慢" / "延迟" / "slow"
    if any(kw in msg for kw in ['最慢', '延迟', '慢', 'slow', 'latency']):
        return handle_slowest_query()

    # 6. 错误查询："错误" / "error" / "报错"
    if any(kw in msg for kw in ['错误', '报错', 'error', '故障']):
        return handle_error_query()

    # 7. 帮助
    if any(kw in msg for kw in ['帮助', 'help', '怎么用', '怎么查']):
        return ChatResponse(
            reply="🤖 **AI 问答助手** 支持以下查询:\n\n"
                  "- XX 的健康度 — 查询实体健康状态\n"
                  "- 异常的实体 — 查看所有异常\n"
                  "- 有多少个服务 — 统计实体数量\n"
                  "- XX 依赖什么 — 查询依赖关系\n"
                  "- 最慢的服务 — 查询延迟最高的接口\n"
                  "- 错误率 — 查询错误率最高的服务\n"
        )

    return ChatResponse(
        reply="🤔 抱歉，我没有理解你的问题。试试输入「帮助」查看支持的查询类型。"
    )


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    AI 问答接口（基础版 - 关键词解析）。

    支持自然语言查询实体状态、健康度、关系、性能数据。
    """
    try:
        return parse_and_respond(request.message)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(reply=f"⚠️ 处理请求时出错: {str(e)}")
