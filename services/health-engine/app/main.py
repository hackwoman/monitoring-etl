"""
健康度计算引擎 — 主循环。

定时从 ClickHouse 拉取指标数据，计算每个实体的健康评分，写回 Postgres。

用法:
  python -m app.main              # 持续运行（默认 60s 间隔）
  python -m app.main --once       # 单次计算后退出
  python -m app.main --interval 30  # 自定义间隔
"""

import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("health-engine")

# ---- 配置 ----
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cmdb",
)
CLICKHOUSE_URL = os.getenv(
    "CLICKHOUSE_URL",
    "http://localhost:8123",
)
INTERVAL = int(os.getenv("HEALTH_ENGINE_INTERVAL", "60"))


def get_pg_conn():
    """获取 Postgres 连接。"""
    return psycopg2.connect(DATABASE_URL)


def load_entities_and_types(pg):
    """从 Postgres 加载所有 active 实体及其类型定义。"""
    with pg.cursor(cursor_factory=RealDictCursor) as cur:
        # 加载类型定义
        cur.execute("SELECT * FROM entity_type_def")
        type_defs = {row["type_name"]: dict(row) for row in cur.fetchall()}

        # 加载 active 实体
        cur.execute("SELECT * FROM entity WHERE status = 'active'")
        entities = [dict(row) for row in cur.fetchall()]

    return entities, type_defs


def load_relationships(pg):
    """加载所有关系。"""
    with pg.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT guid, type_name, 
                   COALESCE(from_guid::text, end1_guid::text) as from_guid,
                   COALESCE(to_guid::text, end2_guid::text) as to_guid
            FROM relationship 
            WHERE is_active = true
        """)
        return [dict(row) for row in cur.fetchall()]


def fetch_metrics_from_clickhouse(entities: list) -> dict:
    """
    从 ClickHouse 批量查询实体的最新指标值。
    
    按 service_name / host_name 分组查询最近 5 分钟的日志/指标。
    
    Returns:
        {
            "Service:gateway": {
                "http.server.request.duration.p99": 150.5,
                "http.server.request.error_rate": 0.5,
                "system.cpu.usage": 45.2,
            },
            ...
        }
    """
    result = {}

    if not entities:
        return result

    # 构建查询映射：type_name:name → 实体
    entity_map = {}
    for e in entities:
        key = f"{e['type_name']}:{e['name']}"
        entity_map[key] = e

    try:
        with httpx.Client(timeout=15) as client:
            # 查询服务错误率和延迟（从日志表）
            service_entities = [e for e in entities if e["type_name"] == "Service"]
            if service_entities:
                names = ",".join(f"'{e['name']}'" for e in service_entities)
                sql = f"""
                SELECT 
                    service_name,
                    count() as total_requests,
                    countIf(level = 'error') as error_count,
                    round(countIf(level = 'error') * 100.0 / count(), 2) as error_rate,
                    round(quantile(0.99)(duration_ms), 2) as p99_latency_ms
                FROM logs.log_entries
                WHERE service_name IN ({names})
                  AND timestamp > now() - INTERVAL 60 MINUTE
                GROUP BY service_name
                FORMAT JSON
                """
                r = client.post(CLICKHOUSE_URL, data=sql)
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    for row in data:
                        svc_name = row["service_name"]
                        key = f"Service:{svc_name}"
                        result[key] = {
                            "http.server.request.error_rate": float(row.get("error_rate", 0)),
                            "http.server.request.duration.p99": float(row.get("p99_latency_ms", 0)),
                            "system.cpu.usage": 0,  # 需要真实指标数据
                        }

            # 查询主机指标（从日志表的 host_name 统计）
            host_entities = [e for e in entities if e["type_name"] == "Host"]
            if host_entities:
                names = ",".join(f"'{e['name']}'" for e in host_entities)
                sql = f"""
                SELECT 
                    host_name,
                    count() as log_count,
                    countIf(level = 'error') as error_count
                FROM logs.log_entries
                WHERE host_name IN ({names})
                  AND timestamp > now() - INTERVAL 60 MINUTE
                GROUP BY host_name
                FORMAT JSON
                """
                r = client.post(CLICKHOUSE_URL, data=sql)
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    for row in data:
                        host_name = row["host_name"]
                        key = f"Host:{host_name}"
                        log_count = int(row.get("log_count", 0))
                        error_count = int(row.get("error_count", 0))
                        # 日志量间接反映负载
                        result[key] = {
                            "system.cpu.usage": min(100, log_count / 10),
                            "system.memory.usage": min(100, log_count / 20),
                            "system.disk.usage": 50,  # 无真实数据
                        }

            # 查询 Trace 数据中的服务延迟和错误
            trace_sql = """
            SELECT 
                service_name,
                round(quantile(0.99)(duration_ms), 2) as p99_latency,
                round(countIf(status_code = 'error') * 100.0 / count(), 2) as error_rate
            FROM traces.spans
            WHERE start_time > now() - INTERVAL 60 MINUTE
            GROUP BY service_name
            FORMAT JSON
            """
            r = client.post(CLICKHOUSE_URL, data=trace_sql)
            if r.status_code == 200:
                data = r.json().get("data", [])
                for row in data:
                    svc_name = row["service_name"]
                    key = f"Service:{svc_name}"
                    if key not in result:
                        result[key] = {}
                    result[key]["http.server.request.duration.p99"] = float(row.get("p99_latency", 0))
                    result[key]["http.server.request.error_rate"] = float(row.get("error_rate", 0))

    except Exception as e:
        logger.warning(f"ClickHouse query failed: {e}")

    return result


def update_entity_health(pg, entity_guid: str, health: dict):
    """更新实体的健康度信息。"""
    with pg.cursor() as cur:
        cur.execute("""
            UPDATE entity 
            SET health_score = %s,
                health_level = %s,
                health_detail = %s,
                risk_score = %s,
                blast_radius = %s,
                propagation_hops = %s,
                updated_at = now()
            WHERE guid = %s
        """, (
            health["health_score"],
            health["health_level"],
            json.dumps(health["health_detail"]),
            health.get("risk_score", 0),
            health.get("blast_radius", 0),
            health.get("propagation_hops", 0),
            entity_guid,
        ))


def run_once():
    """单次健康度计算。"""
    logger.info("🏥 健康度计算开始...")

    from app.calculator import calculate_entity_health, score_to_level
    from app.impact import calculate_all_impacts

    pg = get_pg_conn()
    try:
        # 1. 加载实体和类型定义
        entities, type_defs = load_entities_and_types(pg)
        logger.info(f"  加载 {len(entities)} 个实体, {len(type_defs)} 种类型")

        if not entities:
            logger.info("  无实体，跳过")
            return

        # 2. 加载关系
        relationships = load_relationships(pg)
        logger.info(f"  加载 {len(relationships)} 条关系")

        # 3. 计算影响范围
        impacts = calculate_all_impacts(entities, relationships)

        # 4. 从 ClickHouse 获取指标数据
        metrics_data = fetch_metrics_from_clickhouse(entities)
        logger.info(f"  获取 {len(metrics_data)} 组指标数据")

        # 5. 计算每个实体的健康度
        updated = 0
        # 建立 entity guid → entity 映射
        entity_by_guid = {str(e["guid"]): e for e in entities}

        # 先计算叶子节点（无 children_avg 的），再计算父节点
        leaf_entities = []
        parent_entities = []
        for e in entities:
            type_def = type_defs.get(e["type_name"], {})
            health_model = (type_def.get("definition") or {}).get("health", {})
            if health_model.get("method") == "children_avg":
                parent_entities.append(e)
            else:
                leaf_entities.append(e)

        # 叶子节点先算
        health_scores = {}  # guid → health_score
        for entity in leaf_entities:
            type_def = type_defs.get(entity["type_name"], {})
            entity_key = f"{entity['type_name']}:{entity['name']}"
            entity_metrics = metrics_data.get(entity_key, {})

            impact = impacts.get(str(entity["guid"]), {})
            health = calculate_entity_health(
                entity=dict(entity),
                type_def=dict(type_def),
                metrics_data=entity_metrics,
            )
            health["blast_radius"] = impact.get("blast_radius", 0)
            health["propagation_hops"] = impact.get("propagation_hops", 0)

            health_scores[str(entity["guid"])] = health["health_score"]
            update_entity_health(pg, str(entity["guid"]), health)
            updated += 1

        # 父节点后算（需要子节点分数）
        for entity in parent_entities:
            type_def = type_defs.get(entity["type_name"], {})
            entity_key = f"{entity['type_name']}:{entity['name']}"

            # 找到直接子实体的 health_score
            child_scores = []
            for rel in relationships:
                if str(rel.get("from_guid")) == str(entity["guid"]):
                    child_guid = str(rel["to_guid"])
                    if child_guid in health_scores:
                        child_scores.append(health_scores[child_guid])

            impact = impacts.get(str(entity["guid"]), {})
            health = calculate_entity_health(
                entity=dict(entity),
                type_def=dict(type_def),
                metrics_data={},
                child_health_scores=child_scores,
            )
            health["blast_radius"] = impact.get("blast_radius", 0)
            health["propagation_hops"] = impact.get("propagation_hops", 0)

            health_scores[str(entity["guid"])] = health["health_score"]
            update_entity_health(pg, str(entity["guid"]), health)
            updated += 1

        pg.commit()
        logger.info(f"  ✅ 更新 {updated} 个实体的健康度")

        # 统计
        levels = {}
        for guid, score in health_scores.items():
            level = score_to_level(score)
            levels[level] = levels.get(level, 0) + 1
        logger.info(f"  📊 健康分布: {levels}")

    except Exception as e:
        logger.error(f"  ❌ 计算失败: {e}")
        pg.rollback()
        raise
    finally:
        pg.close()


def main():
    parser = argparse.ArgumentParser(description="健康度计算引擎")
    parser.add_argument("--once", action="store_true", help="单次计算后退出")
    parser.add_argument("--interval", type=int, default=INTERVAL, help="计算间隔（秒）")
    args = parser.parse_args()

    if args.once:
        run_once()
        return

    logger.info(f"🏥 健康度计算引擎启动，间隔 {args.interval}s")
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"计算异常: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
