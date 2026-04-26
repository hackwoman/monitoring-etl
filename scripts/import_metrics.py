"""
Phase 2: 指标体系填充
导入各实体类型的指标定义到 metric_def 表
"""
import asyncpg, asyncio
import json

# ══════════════════════════════════════════════════════════════
# 指标定义（按实体类型 + 维度组织）
# ══════════════════════════════════════════════════════════════

METRICS = {
    # ========== Service 服务指标 ==========
    "Service": {
        "performance": [
            {"id": "service.http.request.duration.p99", "name": "P99延迟", "unit": "ms", "warn": 500, "crit": 2000},
            {"id": "service.http.request.duration.p50", "name": "P50延迟", "unit": "ms", "warn": 200, "crit": 800},
            {"id": "service.http.request.qps", "name": "QPS", "unit": "req/s"},
            {"id": "service.http.request.tps", "name": "TPS", "unit": "req/s"},
        ],
        "reliability": [
            {"id": "service.http.request.error_rate", "name": "错误率", "unit": "%", "warn": 1, "crit": 5, "cmp": "gt"},
            {"id": "service.http.request.5xx_count", "name": "5xx错误数", "unit": "count", "warn": 10, "crit": 50},
            {"id": "service.http.request.timeout_rate", "name": "超时率", "unit": "%", "warn": 0.5, "crit": 2},
        ],
        "resource": [
            {"id": "service.jvm.heap.usage", "name": "JVM堆内存使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "service.jvm.thread.count", "name": "JVM线程数", "unit": "count"},
            {"id": "service.jvm.gc.pause", "name": "GC暂停时间", "unit": "ms", "warn": 100, "crit": 500},
        ],
        "capacity": [
            {"id": "service.connection.pool.active", "name": "连接池活跃连接数", "unit": "count"},
            {"id": "service.connection.pool.utilization", "name": "连接池利用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "service.thread.pool.utilization", "name": "线程池利用率", "unit": "%", "warn": 70, "crit": 90},
        ],
    },

    # ========== Host 主机指标 ==========
    "Host": {
        "performance": [
            {"id": "host.cpu.usage", "name": "CPU使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "host.cpu.load.1m", "name": "1分钟负载", "unit": ""},
            {"id": "host.cpu.load.5m", "name": "5分钟负载", "unit": ""},
            {"id": "host.cpu.load.15m", "name": "15分钟负载", "unit": ""},
        ],
        "resource": [
            {"id": "host.memory.usage", "name": "内存使用率", "unit": "%", "warn": 80, "crit": 95},
            {"id": "host.memory.available", "name": "可用内存", "unit": "bytes"},
            {"id": "host.disk.usage", "name": "磁盘使用率", "unit": "%", "warn": 80, "crit": 90},
            {"id": "host.disk.iops.read", "name": "磁盘读IOPS", "unit": "iops"},
            {"id": "host.disk.iops.write", "name": "磁盘写IOPS", "unit": "iops"},
            {"id": "host.disk.throughput.read", "name": "磁盘读吞吐", "unit": "bytes/s"},
            {"id": "host.disk.throughput.write", "name": "磁盘写吞吐", "unit": "bytes/s"},
            {"id": "host.network.bandwidth.in", "name": "网络入带宽", "unit": "bytes/s"},
            {"id": "host.network.bandwidth.out", "name": "网络出带宽", "unit": "bytes/s"},
            {"id": "host.network.packet_loss", "name": "网络丢包率", "unit": "%", "warn": 0.1, "crit": 1},
            {"id": "host.network.latency", "name": "网络延迟", "unit": "ms", "warn": 10, "crit": 50},
        ],
        "capacity": [
            {"id": "host.file descriptor.usage", "name": "文件描述符使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "host.process.count", "name": "进程数", "unit": "count"},
        ],
    },

    # ========== Container 容器指标 ==========
    "Container": {
        "performance": [
            {"id": "container.cpu.usage", "name": "CPU使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "container.cpu.throttle", "name": "CPU限流", "unit": "%", "warn": 25, "crit": 50},
        ],
        "resource": [
            {"id": "container.memory.usage", "name": "内存使用率", "unit": "%", "warn": 80, "crit": 95},
            {"id": "container.memory.limit", "name": "内存限制", "unit": "bytes"},
            {"id": "container.network.rx", "name": "网络接收", "unit": "bytes/s"},
            {"id": "container.network.tx", "name": "网络发送", "unit": "bytes/s"},
        ],
    },

    # ========== Database 数据库指标 ==========
    "Database": {
        "performance": [
            {"id": "db.query.duration.p99", "name": "查询P99延迟", "unit": "ms", "warn": 100, "crit": 500},
            {"id": "db.query.qps", "name": "查询QPS", "unit": "qps"},
            {"id": "db.slow_query.count", "name": "慢查询数", "unit": "count", "warn": 10, "crit": 50},
        ],
        "reliability": [
            {"id": "db.connection.error_rate", "name": "连接错误率", "unit": "%", "warn": 0.5, "crit": 2},
            {"id": "db.replication.lag", "name": "复制延迟", "unit": "s", "warn": 1, "crit": 10},
        ],
        "resource": [
            {"id": "db.connection.active", "name": "活跃连接数", "unit": "count"},
            {"id": "db.connection.utilization", "name": "连接利用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "db.storage.usage", "name": "存储使用率", "unit": "%", "warn": 70, "crit": 85},
            {"id": "db.buffer.pool.hit_rate", "name": "缓冲池命中率", "unit": "%", "warn": 95, "crit": 90, "cmp": "lt"},
        ],
    },

    # ========== Redis 缓存指标 ==========
    "Redis": {
        "performance": [
            {"id": "redis.cmd.latency.p99", "name": "命令P99延迟", "unit": "ms", "warn": 5, "crit": 20},
            {"id": "redis.cmd.qps", "name": "命令QPS", "unit": "qps"},
        ],
        "reliability": [
            {"id": "redis.eviction.count", "name": "淘汰键数", "unit": "count", "warn": 100, "crit": 1000},
            {"id": "redis.keyspace.misses", "name": "缓存未命中", "unit": "count"},
        ],
        "resource": [
            {"id": "redis.memory.usage", "name": "内存使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "redis.memory.fragmentation", "name": "内存碎片率", "unit": "", "warn": 1.5, "crit": 2},
            {"id": "redis.connected.clients", "name": "连接客户端数", "unit": "count"},
            {"id": "redis.hit_rate", "name": "缓存命中率", "unit": "%", "warn": 90, "crit": 80, "cmp": "lt"},
        ],
    },

    # ========== MessageQueue 消息队列指标 ==========
    "MessageQueue": {
        "performance": [
            {"id": "mq.produce.rate", "name": "生产速率", "unit": "msg/s"},
            {"id": "mq.consume.rate", "name": "消费速率", "unit": "msg/s"},
            {"id": "mq.consume.lag", "name": "消费延迟", "unit": "msg", "warn": 1000, "crit": 10000},
        ],
        "reliability": [
            {"id": "mq.message.failed.count", "name": "失败消息数", "unit": "count", "warn": 10, "crit": 100},
            {"id": "mq.message.retry.count", "name": "重试消息数", "unit": "count", "warn": 50, "crit": 500},
        ],
        "resource": [
            {"id": "mq.topic.partitions", "name": "分区数", "unit": "count"},
            {"id": "mq.consumer.group.members", "name": "消费者组成员数", "unit": "count"},
        ],
    },

    # ========== K8sPod 指标 ==========
    "K8sPod": {
        "performance": [
            {"id": "k8s.pod.cpu.usage", "name": "CPU使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "k8s.pod.cpu.throttle", "name": "CPU限流", "unit": "%", "warn": 25, "crit": 50},
        ],
        "resource": [
            {"id": "k8s.pod.memory.usage", "name": "内存使用率", "unit": "%", "warn": 80, "crit": 95},
            {"id": "k8s.pod.memory_working_set", "name": "工作集内存", "unit": "bytes"},
            {"id": "k8s.pod.network.rx", "name": "网络接收", "unit": "bytes/s"},
            {"id": "k8s.pod.network.tx", "name": "网络发送", "unit": "bytes/s"},
            {"id": "k8s.pod.restarts", "name": "重启次数", "unit": "count", "warn": 1, "crit": 5},
        ],
    },

    # ========== K8sNode 指标 ==========
    "K8sNode": {
        "performance": [
            {"id": "k8s.node.cpu.usage", "name": "CPU使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "k8s.node.cpu.allocatable", "name": "可分配CPU", "unit": "cores"},
        ],
        "resource": [
            {"id": "k8s.node.memory.usage", "name": "内存使用率", "unit": "%", "warn": 80, "crit": 95},
            {"id": "k8s.node.pod.count", "name": "Pod数量", "unit": "count"},
            {"id": "k8s.node.pod.capacity", "name": "Pod容量", "unit": "count"},
            {"id": "k8s.node.disk.pressure", "name": "磁盘压力", "unit": "bool"},
            {"id": "k8s.node.memory.pressure", "name": "内存压力", "unit": "bool"},
            {"id": "k8s.node.network.pressure", "name": "网络压力", "unit": "bool"},
        ],
    },

    # ========== K8sCluster 指标 ==========
    "K8sCluster": {
        "resource": [
            {"id": "k8s.cluster.node.count", "name": "节点数", "unit": "count"},
            {"id": "k8s.cluster.pod.count", "name": "Pod总数", "unit": "count"},
            {"id": "k8s.cluster.namespace.count", "name": "命名空间数", "unit": "count"},
            {"id": "k8s.cluster.service.count", "name": "服务数", "unit": "count"},
        ],
        "reliability": [
            {"id": "k8s.cluster.component.health", "name": "组件健康状态", "unit": "bool"},
        ],
    },

    # ========== Endpoint/API端点 指标 ==========
    "Interface": {
        "performance": [
            {"id": "endpoint.request.duration.p99", "name": "端点P99延迟", "unit": "ms", "warn": 500, "crit": 2000},
            {"id": "endpoint.request.duration.p50", "name": "端点P50延迟", "unit": "ms", "warn": 200, "crit": 800},
            {"id": "endpoint.request.qps", "name": "端点QPS", "unit": "req/s"},
        ],
        "reliability": [
            {"id": "endpoint.request.error_rate", "name": "端点错误率", "unit": "%", "warn": 1, "crit": 5, "cmp": "gt"},
            {"id": "endpoint.request.5xx_rate", "name": "5xx比率", "unit": "%", "warn": 0.5, "crit": 2},
        ],
    },

    # ========== Page 页面指标 ==========
    "Page": {
        "performance": [
            {"id": "page.load.time", "name": "页面加载时间", "unit": "ms", "warn": 3000, "crit": 5000},
            {"id": "page.dom.ready", "name": "DOM Ready时间", "unit": "ms", "warn": 1500, "crit": 3000},
            {"id": "page.first.paint", "name": "首次绘制时间", "unit": "ms", "warn": 1000, "crit": 2000},
            {"id": "page.largest.contentful.paint", "name": "LCP", "unit": "ms", "warn": 2500, "crit": 4000},
        ],
        "reliability": [
            {"id": "page.js.error.rate", "name": "JS错误率", "unit": "%", "warn": 0.5, "crit": 2},
            {"id": "page.resource.failed.count", "name": "资源加载失败数", "unit": "count", "warn": 5, "crit": 20},
        ],
        "resource": [
            {"id": "page.resource.size.total", "name": "页面总大小", "unit": "bytes"},
            {"id": "page.resource.count", "name": "资源请求数", "unit": "count"},
        ],
    },

    # ========== Process 进程指标 ==========
    "Process": {
        "performance": [
            {"id": "process.cpu.usage", "name": "CPU使用率", "unit": "%", "warn": 70, "crit": 90},
            {"id": "process.cpu.user", "name": "用户态CPU", "unit": "%"},
            {"id": "process.cpu.system", "name": "内核态CPU", "unit": "%"},
        ],
        "resource": [
            {"id": "process.memory.rss", "name": "RSS内存", "unit": "bytes"},
            {"id": "process.memory.vsz", "name": "VSZ内存", "unit": "bytes"},
            {"id": "process.memory.usage", "name": "内存使用率", "unit": "%", "warn": 80, "crit": 95},
            {"id": "process.fd.open", "name": "打开文件数", "unit": "count"},
            {"id": "process.thread.count", "name": "线程数", "unit": "count"},
        ],
    },
}


async def import_metrics():
    """导入指标定义"""
    conn = await asyncpg.connect('postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb')
    
    total = 0
    for entity_type, dimensions in METRICS.items():
        for dim_name, metrics in dimensions.items():
            for m in metrics:
                try:
                    await conn.execute(
                        """INSERT INTO metric_def (metric_id, display_name, category, entity_type, metric_type, unit, warn_threshold, crit_threshold, comparison, source)
                           VALUES ($1, $2, $3, $4, 'gauge', $5, $6, $7, $8, 'builtin')
                           ON CONFLICT (metric_id) DO UPDATE SET display_name=$2, warn_threshold=$6, crit_threshold=$7""",
                        m["id"], m["name"], dim_name, entity_type, m.get("unit", ""),
                        m.get("warn"), m.get("crit"), m.get("cmp", "gt")
                    )
                    total += 1
                except Exception as e:
                    print(f'  ! {m["id"]}: {e}')
    
    # 验证
    count = await conn.fetchval("SELECT COUNT(*) FROM metric_def")
    print(f'✅ 导入完成：{total} 个指标')
    print(f'✅ 数据库中总计：{count} 个指标')
    
    # 按实体类型统计
    rows = await conn.fetch(
        "SELECT entity_type, COUNT(*) as cnt FROM metric_def WHERE entity_type IS NOT NULL GROUP BY entity_type ORDER BY cnt DESC"
    )
    print()
    print('按实体类型统计：')
    for r in rows:
        print(f'  {r["entity_type"]:20s} {r["cnt"]:3d} 个')
    
    await conn.close()

asyncio.run(import_metrics())
