"""
Phase 2 补充：配置指标映射和维度映射（补偿机制）
"""
import asyncpg, asyncio

# Prometheus 指标映射（常见指标）
PROMETHEUS_MAPPINGS = [
    ("prometheus", "node_cpu_seconds_total", "host.cpu.usage", 0.9),
    ("prometheus", "node_memory_MemTotal_bytes", "host.memory.available", 0.9),
    ("prometheus", "node_filesystem_avail_bytes", "host.disk.usage", 0.8),
    ("prometheus", "node_network_receive_bytes_total", "host.network.bandwidth.in", 0.9),
    ("prometheus", "node_network_transmit_bytes_total", "host.network.bandwidth.out", 0.9),
    ("prometheus", "node_load1", "host.cpu.load.1m", 0.95),
    ("prometheus", "node_load5", "host.cpu.load.5m", 0.95),
    ("prometheus", "node_load15", "host.cpu.load.15m", 0.95),
    ("prometheus", "container_cpu_usage_seconds_total", "container.cpu.usage", 0.9),
    ("prometheus", "container_memory_working_set_bytes", "container.memory.usage", 0.9),
    ("prometheus", "kube_pod_status_phase", "k8s.pod.restarts", 0.8),
    ("prometheus", "kube_node_status_condition", "k8s.node.cpu.usage", 0.7),
    ("prometheus", "http_requests_total", "service.http.request.qps", 0.9),
    ("prometheus", "http_request_duration_seconds", "service.http.request.duration.p99", 0.9),
    ("prometheus", "redis_connected_clients", "redis.connected.clients", 0.95),
    ("prometheus", "redis_memory_used_bytes", "redis.memory.usage", 0.9),
    ("prometheus", "mysql_global_status_threads_connected", "db.connection.active", 0.9),
    ("prometheus", "mysql_global_status_slow_queries", "db.slow_query.count", 0.9),
]

# 维度映射
DIMENSION_MAPPINGS = [
    ("prometheus", "job", "service"),
    ("prometheus", "instance", "host"),
    ("prometheus", "namespace", "k8s.namespace"),
    ("prometheus", "pod", "k8s.pod"),
    ("prometheus", "container", "k8s.container"),
    ("prometheus", "node", "k8s.node"),
    ("prometheus", "env", "environment"),
    ("prometheus", "region", "datacenter"),
    ("zabbix", "host", "host"),
    ("zabbix", "service", "service"),
    ("zabbix", "env", "environment"),
]

async def import_mappings():
    conn = await asyncpg.connect('postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb')
    
    # 导入指标映射
    for source, source_metric, target_metric, confidence in PROMETHEUS_MAPPINGS:
        try:
            await conn.execute(
                """INSERT INTO metric_mapping (source_system, source_metric, target_metric_id, confidence, status, created_by)
                   VALUES ($1, $2, $3, $4, 'confirmed', 'system')
                   ON CONFLICT (source_system, source_metric) DO UPDATE SET target_metric_id=$3, confidence=$4""",
                source, source_metric, target_metric, confidence
            )
        except Exception as e:
            print(f'  ! metric mapping: {e}')
    
    count = await conn.fetchval("SELECT COUNT(*) FROM metric_mapping")
    print(f'✅ 指标映射：{count} 条')
    
    # 导入维度映射
    for source, source_dim, target_key in DIMENSION_MAPPINGS:
        try:
            await conn.execute(
                """INSERT INTO dimension_mapping (source_system, source_dimension, target_label_key, status)
                   VALUES ($1, $2, $3, 'confirmed')
                   ON CONFLICT (source_system, source_dimension) DO UPDATE SET target_label_key=$3""",
                source, source_dim, target_key
            )
        except Exception as e:
            print(f'  ! dimension mapping: {e}')
    
    count = await conn.fetchval("SELECT COUNT(*) FROM dimension_mapping")
    print(f'✅ 维度映射：{count} 条')
    
    await conn.close()

asyncio.run(import_mappings())
