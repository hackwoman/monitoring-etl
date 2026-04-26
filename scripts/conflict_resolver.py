"""
Phase 4: 补偿机制实现
模型冲突检测 + 自动映射 + 动态扩展
"""
import asyncpg
import json
from datetime import datetime


class ModelConflictResolver:
    """模型冲突解决器"""
    
    def __init__(self, conn):
        self.conn = conn
    
    async def resolve_metric(self, source_system: str, source_metric: str, dimensions: dict = None) -> dict:
        """
        解析第三方指标，尝试映射到标准模型
        
        返回：
        {
            "status": "mapped" | "dynamic" | "unknown",
            "target_metric_id": str | None,
            "confidence": float,
            "entity_type": str | None,
            "message": str
        }
        """
        # Step 1: 查询指标映射表
        row = await self.conn.fetchrow(
            """SELECT target_metric_id, confidence, status 
               FROM metric_mapping 
               WHERE source_system = $1 AND source_metric = $2""",
            source_system, source_metric
        )
        
        if row and row['status'] == 'confirmed':
            return {
                "status": "mapped",
                "target_metric_id": row['target_metric_id'],
                "confidence": row['confidence'],
                "entity_type": None,
                "message": f"已映射到标准指标: {row['target_metric_id']}"
            }
        
        # Step 2: 尝试模糊匹配（基于指标名前缀）
        fuzzy_match = await self._fuzzy_match_metric(source_metric)
        if fuzzy_match and fuzzy_match['confidence'] > 0.7:
            return {
                "status": "mapped",
                "target_metric_id": fuzzy_match['metric_id'],
                "confidence": fuzzy_match['confidence'],
                "entity_type": fuzzy_match.get('entity_type'),
                "message": f"模糊匹配到: {fuzzy_match['metric_id']} (置信度: {fuzzy_match['confidence']:.2f})"
            }
        
        # Step 3: 推断实体类型（基于指标名前缀）
        inferred_type = self._infer_entity_type(source_metric)
        
        # Step 4: 创建动态扩展记录
        dynamic_id = await self._create_dynamic_metric(
            source_system, source_metric, inferred_type, dimensions
        )
        
        return {
            "status": "dynamic",
            "target_metric_id": None,
            "confidence": 0.0,
            "entity_type": inferred_type,
            "message": f"未知指标，已创建待确认记录 (ID: {dynamic_id})，推断实体类型: {inferred_type or 'unknown'}"
        }
    
    async def resolve_dimension(self, source_system: str, source_dimension: str) -> dict:
        """
        解析第三方维度，尝试映射到标准标签
        """
        row = await self.conn.fetchrow(
            """SELECT target_label_key, transform_rule, status
               FROM dimension_mapping 
               WHERE source_system = $1 AND source_dimension = $2""",
            source_system, source_dimension
        )
        
        if row and row['status'] == 'confirmed':
            return {
                "status": "mapped",
                "target_key": row['target_label_key'],
                "transform_rule": row['transform_rule'],
                "message": f"已映射到标签: {row['target_label_key']}"
            }
        
        return {
            "status": "unknown",
            "target_key": None,
            "transform_rule": None,
            "message": f"未知维度: {source_dimension}"
        }
    
    async def _fuzzy_match_metric(self, source_metric: str) -> dict:
        """模糊匹配指标"""
        # 基于关键词匹配
        keywords = {
            "cpu": "host.cpu.usage",
            "memory": "host.memory.usage",
            "disk": "host.disk.usage",
            "network": "host.network.bandwidth.in",
            "load": "host.cpu.load.1m",
            "qps": "service.http.request.qps",
            "latency": "service.http.request.duration.p99",
            "error": "service.http.request.error_rate",
            "request": "service.http.request.qps",
            "connection": "db.connection.active",
            "query": "db.query.qps",
        }
        
        source_lower = source_metric.lower()
        for keyword, metric_id in keywords.items():
            if keyword in source_lower:
                # 验证目标指标是否存在
                exists = await self.conn.fetchval(
                    "SELECT COUNT(*) FROM metric_def WHERE metric_id = $1",
                    metric_id
                )
                if exists:
                    return {
                        "metric_id": metric_id,
                        "confidence": 0.7,
                        "entity_type": None
                    }
        
        return None
    
    def _infer_entity_type(self, source_metric: str) -> str:
        """推断实体类型"""
        prefix_map = {
            "node_": "Host",
            "host_": "Host",
            "container_": "Container",
            "kube_pod_": "K8sPod",
            "kube_node_": "K8sNode",
            "kube_cluster_": "K8sCluster",
            "http_": "Service",
            "grpc_": "Service",
            "redis_": "Redis",
            "mysql_": "Database",
            "postgres_": "Database",
            "kafka_": "MessageQueue",
            "process_": "Process",
        }
        
        source_lower = source_metric.lower()
        for prefix, entity_type in prefix_map.items():
            if source_lower.startswith(prefix):
                return entity_type
        
        return None
    
    async def _create_dynamic_metric(self, source_system: str, source_metric: str, 
                                      inferred_type: str, dimensions: dict) -> int:
        """创建动态扩展指标记录"""
        row = await self.conn.fetchrow(
            """INSERT INTO dynamic_metric (source_system, source_metric, inferred_entity_type, sample_dimensions, status)
               VALUES ($1, $2, $3, $4, 'pending')
               RETURNING id""",
            source_system, source_metric, inferred_type,
            json.dumps(dimensions or {})
        )
        return row['id']
    
    async def get_pending_metrics(self) -> list:
        """获取待确认的动态指标"""
        rows = await self.conn.fetch(
            """SELECT id, source_system, source_metric, inferred_entity_type, 
                      sample_dimensions, created_at
               FROM dynamic_metric 
               WHERE status = 'pending'
               ORDER BY created_at DESC"""
        )
        return [dict(r) for r in rows]
    
    async def confirm_metric(self, metric_id: int, target_metric_id: str, confirmed_by: str) -> bool:
        """确认动态指标"""
        try:
            await self.conn.execute(
                """UPDATE dynamic_metric 
                   SET status = 'confirmed', confirmed_by = $1, confirmed_at = NOW()
                   WHERE id = $2""",
                confirmed_by, metric_id
            )
            
            # 同时创建映射记录
            row = await self.conn.fetchrow(
                "SELECT source_system, source_metric FROM dynamic_metric WHERE id = $1",
                metric_id
            )
            if row:
                await self.conn.execute(
                    """INSERT INTO metric_mapping (source_system, source_metric, target_metric_id, confidence, status, created_by)
                       VALUES ($1, $2, $3, 1.0, 'confirmed', $4)
                       ON CONFLICT (source_system, source_metric) DO UPDATE SET target_metric_id=$3, status='confirmed'""",
                    row['source_system'], row['source_metric'], target_metric_id, confirmed_by
                )
            
            return True
        except Exception as e:
            print(f"确认失败: {e}")
            return False
    
    async def reject_metric(self, metric_id: int) -> bool:
        """拒绝动态指标"""
        try:
            await self.conn.execute(
                "UPDATE dynamic_metric SET status = 'rejected' WHERE id = $1",
                metric_id
            )
            return True
        except Exception as e:
            print(f"拒绝失败: {e}")
            return False


async def demo_conflict_resolution():
    """演示冲突解决流程"""
    conn = await asyncpg.connect('postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb')
    
    resolver = ModelConflictResolver(conn)
    
    print("=== 补偿机制演示 ===\n")
    
    # 测试1: 已知 Prometheus 指标
    print("测试1: Prometheus 已知指标")
    result = await resolver.resolve_metric("prometheus", "node_cpu_seconds_total")
    print(f"  状态: {result['status']}")
    print(f"  映射: {result['target_metric_id']}")
    print(f"  消息: {result['message']}")
    print()
    
    # 测试2: 已知但未映射的指标
    print("测试2: Prometheus 未映射指标")
    result = await resolver.resolve_metric("prometheus", "node_disk_read_bytes_total")
    print(f"  状态: {result['status']}")
    print(f"  消息: {result['message']}")
    print()
    
    # 测试3: 完全未知的指标
    print("测试3: 完全未知指标")
    result = await resolver.resolve_metric("custom_system", "business_order_count")
    print(f"  状态: {result['status']}")
    print(f"  推断实体类型: {result['entity_type']}")
    print(f"  消息: {result['message']}")
    print()
    
    # 测试4: 维度映射
    print("测试4: Prometheus 维度映射")
    result = await resolver.resolve_dimension("prometheus", "job")
    print(f"  状态: {result['status']}")
    print(f"  映射: {result.get('target_key')}")
    print(f"  消息: {result['message']}")
    print()
    
    # 测试5: 未知维度
    print("测试5: 未知维度")
    result = await resolver.resolve_dimension("prometheus", "custom_label")
    print(f"  状态: {result['status']}")
    print(f"  消息: {result['message']}")
    print()
    
    # 查看待确认的动态指标
    print("=== 待确认的动态指标 ===")
    pending = await resolver.get_pending_metrics()
    for p in pending:
        print(f"  ID:{p['id']} | {p['source_system']}/{p['source_metric']} | 推断:{p['inferred_entity_type']}")
    
    await conn.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_conflict_resolution())
