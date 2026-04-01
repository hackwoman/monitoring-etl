"""Trace 关系自动发现引擎 - 从 ClickHouse Span 数据提取服务调用关系。"""

import os
import json
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

CLICKHOUSE_URL = os.getenv("CLICKHOUSE_URL", "http://47.93.61.196:8123")
CMDB_API_URL = os.getenv("CMDB_API_URL", "http://8001/api/v1/cmdb")


@dataclass
class DiscoveredRelation:
    """从 Trace 发现的调用关系。"""
    caller: str           # 调用方服务名
    callee: str           # 被调方服务名
    call_count: int       # 调用次数
    avg_latency_ms: float # 平均延迟
    p99_latency_ms: float # P99 延迟
    error_rate: float     # 错误率 (%)
    first_seen: str       # 首次发现时间
    last_seen: str        # 最近发现时间


def query_service_topology_from_trace(window_minutes: int = 60) -> List[DiscoveredRelation]:
    """
    从 ClickHouse traces.spans 表提取服务调用拓扑。

    查询逻辑：
    1. 找所有 span 的父子关系
    2. 聚合 caller → callee 的调用次数、延迟、错误率
    3. 返回调用关系列表
    """
    sql = f"""
    SELECT
        p.service_name as caller,
        s.service_name as callee,
        count() as call_count,
        round(avg(s.duration_ms), 2) as avg_latency_ms,
        round(quantile(0.99)(s.duration_ms), 2) as p99_latency_ms,
        round(countIf(s.status_code = 'error') * 100.0 / count(), 2) as error_rate,
        min(p.start_time) as first_seen,
        max(p.start_time) as last_seen
    FROM traces.spans p
    INNER JOIN traces.spans s
        ON p.trace_id = s.trace_id AND s.parent_span_id = p.span_id
    WHERE p.start_time > now() - INTERVAL {window_minutes} MINUTE
      AND p.service_name != s.service_name
    GROUP BY caller, callee
    ORDER BY call_count DESC
    FORMAT JSON
    """

    try:
        r = httpx.post(CLICKHOUSE_URL, content=sql.encode("utf-8"), timeout=30)
        if not r.ok:
            logger.error(f"ClickHouse query failed: {r.status_code} {r.text[:200]}")
            return []

        data = r.json().get("data", [])
        relations = []
        for row in data:
            relations.append(DiscoveredRelation(
                caller=row["caller"],
                callee=row["callee"],
                call_count=row["call_count"],
                avg_latency_ms=row["avg_latency_ms"],
                p99_latency_ms=row["p99_latency_ms"],
                error_rate=row["error_rate"],
                first_seen=row.get("first_seen", ""),
                last_seen=row.get("last_seen", ""),
            ))
        return relations
    except Exception as e:
        logger.error(f"Trace topology query exception: {e}")
        return []


def query_endpoint_topology(window_minutes: int = 60) -> List[Dict[str, Any]]:
    """
    提取接口级调用关系（更细粒度）。
    """
    sql = f"""
    SELECT
        p.service_name as caller_service,
        p.endpoint as caller_endpoint,
        s.service_name as callee_service,
        s.endpoint as callee_endpoint,
        count() as call_count,
        round(avg(s.duration_ms), 2) as avg_latency_ms,
        round(quantile(0.99)(s.duration_ms), 2) as p99_latency_ms,
        round(countIf(s.status_code = 'error') * 100.0 / count(), 2) as error_rate
    FROM traces.spans p
    INNER JOIN traces.spans s
        ON p.trace_id = s.trace_id AND s.parent_span_id = p.span_id
    WHERE p.start_time > now() - INTERVAL {window_minutes} MINUTE
      AND p.service_name != s.service_name
    GROUP BY caller_service, caller_endpoint, callee_service, callee_endpoint
    ORDER BY call_count DESC
    FORMAT JSON
    """

    try:
        r = httpx.post(CLICKHOUSE_URL, content=sql.encode("utf-8"), timeout=30)
        if r.ok:
            return r.json().get("data", [])
        return []
    except Exception as e:
        logger.error(f"Endpoint topology query exception: {e}")
        return []


# ============================================================
# CMDB 融合
# ============================================================

def cmdb_get(path: str) -> Optional[dict]:
    """调用 CMDB API GET。"""
    try:
        r = httpx.get(f"{CMDB_API_URL}{path}", timeout=10)
        if r.ok:
            return r.json()
        return None
    except Exception as e:
        logger.error(f"CMDB GET {path} failed: {e}")
        return None


def cmdb_post(path: str, data: dict) -> Optional[dict]:
    """调用 CMDB API POST。"""
    try:
        r = httpx.post(f"{CMDB_API_URL}{path}", json=data, timeout=10)
        if r.ok:
            return r.json()
        return None
    except Exception as e:
        logger.error(f"CMDB POST {path} failed: {e}")
        return None


def cmdb_put(path: str, data: dict) -> bool:
    """调用 CMDB API PUT。"""
    try:
        r = httpx.put(f"{CMDB_API_URL}{path}", json=data, timeout=10)
        return r.ok
    except Exception as e:
        logger.error(f"CMDB PUT {path} failed: {e}")
        return False


def get_entity_guid_by_name(name: str, type_name: str = None) -> Optional[str]:
    """按名称查找实体 GUID。"""
    params = f"search={name}"
    if type_name:
        params += f"&type_name={type_name}"
    result = cmdb_get(f"/entities?{params}")
    if result and result.get("items"):
        for item in result["items"]:
            if item["name"] == name:
                return item["guid"]
    return None


def find_existing_relation(from_guid: str, to_guid: str) -> Optional[dict]:
    """查找已有的关系。"""
    result = cmdb_get(f"/entities/{from_guid}/relations")
    if result and result.get("items"):
        for rel in result["items"]:
            if rel.get("end2_guid") == to_guid and rel.get("type_name") == "calls":
                return rel
    return None


def merge_relation(discovered: DiscoveredRelation) -> Dict[str, Any]:
    """
    融合策略：将 Trace 发现的关系与 CMDB 现有关系合并。

    场景处理：
    1. CMDB 已有 + Trace 确认 → 更新 attributes（延迟/错误率），刷新 last_seen，confidence=1.0
    2. CMDB 无 + Trace 发现 → 创建新关系，source=trace_discovered，confidence=0.9
    3. 实体不存在 → 跳过（需要先创建实体）
    """
    # 查找实体 GUID
    caller_guid = get_entity_guid_by_name(discovered.caller, "Service")
    callee_guid = get_entity_guid_by_name(discovered.callee)

    if not caller_guid:
        logger.warning(f"Caller entity not found: {discovered.caller}")
        return {"status": "skipped", "reason": "caller_not_found", "caller": discovered.caller}

    if not callee_guid:
        logger.warning(f"Callee entity not found: {discovered.callee}")
        return {"status": "skipped", "reason": "callee_not_found", "callee": discovered.callee}

    # 查找已有关系
    existing = find_existing_relation(caller_guid, callee_guid)

    # 构建关系属性
    trace_attrs = {
        "call_count": discovered.call_count,
        "avg_latency_ms": discovered.avg_latency_ms,
        "p99_latency_ms": discovered.p99_latency_ms,
        "error_rate": discovered.error_rate,
        "last_discovered": datetime.now(timezone.utc).isoformat(),
    }

    if existing:
        # 场景1：已有关系 → 更新属性
        old_attrs = existing.get("attributes", {})
        merged_attrs = {**old_attrs, **trace_attrs}
        # 提升 confidence（Trace 确认了关系存在）
        merged_attrs["trace_confirmed"] = True

        success = cmdb_put(f"/entities/{caller_guid}/relations/{existing['guid']}", {
            "attributes": merged_attrs,
            "confidence": 1.0,  # Trace 确认 → 置信度 1.0
            "source": existing.get("source", "manual"),
            "is_active": True,
        })

        return {
            "status": "updated" if success else "update_failed",
            "relation_guid": existing["guid"],
            "caller": discovered.caller,
            "callee": discovered.callee,
        }
    else:
        # 场景2：新发现关系 → 创建（横向调用链维度）
        result = cmdb_post(f"/entities/{caller_guid}/relations", {
            "type_name": "calls",
            "end2_guid": callee_guid,
            "attributes": trace_attrs,
            "source": "trace_discovered",
            "confidence": 0.9,  # Trace 发现 → 置信度 0.9
            "dimension": "horizontal",  # Trace 驱动的关系属于横向维度
        })

        if result:
            logger.info(f"New relation discovered: {discovered.caller} → {discovered.callee}")
            return {
                "status": "created",
                "relation_guid": result.get("guid"),
                "caller": discovered.caller,
                "callee": discovered.callee,
            }
        else:
            return {
                "status": "create_failed",
                "caller": discovered.caller,
                "callee": discovered.callee,
            }


def mark_stale_relations(active_pairs: set, window_minutes: int = 60):
    """
    标记超时未见的关系为 inactive。

    如果一个 trace_discovered 关系在最近 N 分钟内没有被 Trace 再次确认，
    标记为 is_active=false（但不删除，需要人工确认）。
    """
    # 获取所有 trace_discovered 关系
    all_relations = cmdb_get("/entities?limit=500")
    if not all_relations:
        return

    stale_count = 0
    for entity in all_relations.get("items", []):
        relations = cmdb_get(f"/entities/{entity['guid']}/relations")
        if not relations:
            continue

        for rel in relations.get("items", []):
            if rel.get("source") != "trace_discovered":
                continue
            if not rel.get("is_active"):
                continue

            pair = (entity["name"], rel.get("end2_name", ""))
            if pair not in active_pairs:
                # 超时未见 → 标记 inactive
                cmdb_put(f"/entities/{entity['guid']}/relations/{rel['guid']}", {
                    "is_active": False,
                    "attributes": {
                        **rel.get("attributes", {}),
                        "marked_stale_at": datetime.now(timezone.utc).isoformat(),
                    }
                })
                stale_count += 1
                logger.info(f"Marked stale: {entity['name']} → {rel.get('end2_name')}")

    if stale_count > 0:
        logger.info(f"Marked {stale_count} relations as stale")


# ============================================================
# 主执行函数
# ============================================================

def run_discovery_once(window_minutes: int = 60) -> Dict[str, Any]:
    """
    单次执行 Trace 关系发现。

    返回：
    {
        "discovered": N,   # 发现的关系统计
        "created": N,      # 新创建的关系
        "updated": N,      # 更新的已有关系
        "skipped": N,      # 跳过（实体不存在）
        "stale": N,        # 标记为超时的关系
    }
    """
    logger.info(f"Starting trace discovery (window={window_minutes}min)")

    # 1. 从 Trace 数据提取调用拓扑
    relations = query_service_topology_from_trace(window_minutes)
    if not relations:
        logger.info("No trace data found")
        return {"discovered": 0, "created": 0, "updated": 0, "skipped": 0, "stale": 0}

    logger.info(f"Discovered {len(relations)} relations from trace")

    # 2. 融合到 CMDB
    stats = {"created": 0, "updated": 0, "skipped": 0}
    active_pairs = set()

    for rel in relations:
        active_pairs.add((rel.caller, rel.callee))
        result = merge_relation(rel)

        status = result.get("status")
        if status == "created":
            stats["created"] += 1
        elif status == "updated":
            stats["updated"] += 1
        else:
            stats["skipped"] += 1

    # 3. 标记超时关系
    mark_stale_relations(active_pairs, window_minutes)

    summary = {
        "discovered": len(relations),
        **stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"Discovery complete: {summary}")
    return summary


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Trace 关系发现引擎")
    parser.add_argument("--window", type=int, default=60, help="分析窗口（分钟）")
    parser.add_argument("--topology", action="store_true", help="只展示拓扑不写入 CMDB")
    parser.add_argument("--endpoints", action="store_true", help="展示接口级拓扑")
    args = parser.parse_args()

    if args.topology:
        relations = query_service_topology_from_trace(args.window)
        if not relations:
            print("⚠️ 无 Trace 数据")
        else:
            print(f"\n{'=' * 80}")
            print(f"  🌐 Trace 调用拓扑（最近 {args.window} 分钟）")
            print(f"{'=' * 80}")
            print(f"  {'调用方':<25} → {'被调方':<25} {'调用数':>6} {'P99延迟':>10} {'错误率':>8}")
            print(f"  {'-' * 80}")
            for r in relations:
                print(f"  {r.caller:<25} → {r.callee:<25} {r.call_count:>6} {r.p99_latency_ms:>8.1f}ms {r.error_rate:>6.1f}%")
    elif args.endpoints:
        data = query_endpoint_topology(args.window)
        if not data:
            print("⚠️ 无 Trace 数据")
        else:
            print(f"\n{'=' * 100}")
            print(f"  🔗 接口级调用拓扑（最近 {args.window} 分钟）")
            print(f"{'=' * 100}")
            for row in data:
                print(f"  {row['caller_service']}.{row['caller_endpoint']} → "
                      f"{row['callee_service']}.{row['callee_endpoint']}  "
                      f"×{row['call_count']}  P99={row['p99_latency_ms']}ms  err={row['error_rate']}%")
    else:
        result = run_discovery_once(args.window)
        print(f"\n✅ 发现完成:")
        print(f"  发现关系: {result['discovered']}")
        print(f"  新创建:   {result['created']}")
        print(f"  已更新:   {result['updated']}")
        print(f"  已跳过:   {result['skipped']}")
