"""指标定义体系 - Phase 4.1 按实体类型定义完整指标维度和阈值。"""

# 指标维度分类
METRIC_DIMENSIONS = {
    "performance": "性能维度",
    "error": "错误维度",
    "resource": "资源维度",
    "business": "业务维度",
    "capacity": "容量维度",
    "connection": "连接维度",
}

# 实体类型指标定义
ENTITY_METRIC_DEFINITIONS = {
    # ========== Service 服务指标 ==========
    "Service": {
        "performance": [
            {
                "name": "http.server.request.duration.p99",
                "display_name": "P99 延迟",
                "unit": "ms",
                "warn_threshold": 500,
                "crit_threshold": 2000,
                "description": "HTTP 请求 P99 延迟",
            },
            {
                "name": "http.server.request.duration.p50",
                "display_name": "P50 延迟",
                "unit": "ms",
                "warn_threshold": 200,
                "crit_threshold": 800,
                "description": "HTTP 请求 P50 延迟",
            },
            {
                "name": "http.server.request.qps",
                "display_name": "QPS",
                "unit": "req/s",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "每秒请求数",
            },
        ],
        "error": [
            {
                "name": "http.server.request.error_rate",
                "display_name": "错误率",
                "unit": "%",
                "warn_threshold": 1,
                "crit_threshold": 5,
                "description": "HTTP 请求错误率 (4xx + 5xx)",
            },
            {
                "name": "http.server.request.5xx_count",
                "display_name": "5xx 错误数",
                "unit": "count",
                "warn_threshold": 10,
                "crit_threshold": 50,
                "description": "5xx 错误计数 (15分钟窗口)",
            },
        ],
        "resource": [
            {
                "name": "system.cpu.usage",
                "display_name": "CPU 使用率",
                "unit": "%",
                "warn_threshold": 70,
                "crit_threshold": 90,
                "description": "宿主机 CPU 使用率",
            },
            {
                "name": "system.memory.usage",
                "display_name": "内存使用率",
                "unit": "%",
                "warn_threshold": 80,
                "crit_threshold": 95,
                "description": "宿主机内存使用率",
            },
            {
                "name": "system.disk.usage",
                "display_name": "磁盘使用率",
                "unit": "%",
                "warn_threshold": 80,
                "crit_threshold": 90,
                "description": "宿主机磁盘使用率",
            },
        ],
        "business": [
            {
                "name": "business.order.success_rate",
                "display_name": "订单成功率",
                "unit": "%",
                "warn_threshold": 99,
                "crit_threshold": 95,
                "description": "业务订单成功率 (低于阈值告警)",
                "comparison": "lt",  # 小于阈值告警
            },
        ],
    },

    # ========== Host 主机指标 ==========
    "Host": {
        "resource": [
            {
                "name": "system.cpu.usage",
                "display_name": "CPU 使用率",
                "unit": "%",
                "warn_threshold": 70,
                "crit_threshold": 90,
                "description": "CPU 使用率",
            },
            {
                "name": "system.memory.usage",
                "display_name": "内存使用率",
                "unit": "%",
                "warn_threshold": 80,
                "crit_threshold": 95,
                "description": "内存使用率",
            },
            {
                "name": "system.disk.usage",
                "display_name": "磁盘使用率",
                "unit": "%",
                "warn_threshold": 80,
                "crit_threshold": 90,
                "description": "磁盘使用率",
            },
            {
                "name": "system.disk.io.util",
                "display_name": "磁盘 IO 利用率",
                "unit": "%",
                "warn_threshold": 80,
                "crit_threshold": 95,
                "description": "磁盘 IO 利用率",
            },
        ],
        "performance": [
            {
                "name": "system.load.1m",
                "display_name": "1分钟负载",
                "unit": "",
                "warn_threshold": None,  # 动态计算: CPU核数 * 0.7
                "crit_threshold": None,  # 动态计算: CPU核数 * 1.0
                "description": "1分钟系统负载",
                "dynamic_threshold": True,
            },
            {
                "name": "system.network.io.bytes_recv",
                "display_name": "网络入流量",
                "unit": "MB/s",
                "warn_threshold": 100,
                "crit_threshold": 500,
                "description": "网络接收字节数",
            },
            {
                "name": "system.network.io.bytes_sent",
                "display_name": "网络出流量",
                "unit": "MB/s",
                "warn_threshold": 100,
                "crit_threshold": 500,
                "description": "网络发送字节数",
            },
        ],
    },

    # ========== MySQL 数据库指标 ==========
    "MySQL": {
        "connection": [
            {
                "name": "mysql.connections.active",
                "display_name": "活跃连接数",
                "unit": "count",
                "warn_threshold": 100,
                "crit_threshold": 200,
                "description": "当前活跃连接数",
            },
            {
                "name": "mysql.connections.usage_rate",
                "display_name": "连接池使用率",
                "unit": "%",
                "warn_threshold": 70,
                "crit_threshold": 90,
                "description": "连接池使用率 (活跃/最大)",
            },
        ],
        "performance": [
            {
                "name": "mysql.queries.slow_rate",
                "display_name": "慢查询率",
                "unit": "%",
                "warn_threshold": 1,
                "crit_threshold": 5,
                "description": "慢查询占比",
            },
            {
                "name": "mysql.queries.slow_count",
                "display_name": "慢查询数",
                "unit": "count/5m",
                "warn_threshold": 10,
                "crit_threshold": 50,
                "description": "5分钟内慢查询数量",
            },
            {
                "name": "mysql.query.duration.p99",
                "display_name": "查询 P99 延迟",
                "unit": "ms",
                "warn_threshold": 100,
                "crit_threshold": 500,
                "description": "SQL 查询 P99 延迟",
            },
        ],
        "capacity": [
            {
                "name": "mysql.disk.usage",
                "display_name": "数据盘使用率",
                "unit": "%",
                "warn_threshold": 75,
                "crit_threshold": 90,
                "description": "数据文件所在磁盘使用率",
            },
            {
                "name": "mysql.table.rows",
                "display_name": "总行数",
                "unit": "count",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "所有表总行数",
            },
        ],
    },

    # ========== Redis 缓存指标 ==========
    "Redis": {
        "connection": [
            {
                "name": "redis.clients.connected",
                "display_name": "已连接客户端",
                "unit": "count",
                "warn_threshold": 500,
                "crit_threshold": 1000,
                "description": "当前连接的客户端数量",
            },
            {
                "name": "redis.clients.blocked",
                "display_name": "阻塞客户端",
                "unit": "count",
                "warn_threshold": 10,
                "crit_threshold": 50,
                "description": "被阻塞的客户端数量",
            },
        ],
        "performance": [
            {
                "name": "redis.commands.duration.p99",
                "display_name": "命令 P99 延迟",
                "unit": "ms",
                "warn_threshold": 10,
                "crit_threshold": 50,
                "description": "Redis 命令 P99 延迟",
            },
            {
                "name": "redis.commands.per_sec",
                "display_name": "每秒命令数",
                "unit": "cmd/s",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "每秒处理的命令数",
            },
        ],
        "capacity": [
            {
                "name": "redis.memory.usage_rate",
                "display_name": "内存使用率",
                "unit": "%",
                "warn_threshold": 70,
                "crit_threshold": 90,
                "description": "Redis 内存使用率 (used/maxmemory)",
            },
            {
                "name": "redis.memory.fragmentation_ratio",
                "display_name": "内存碎片率",
                "unit": "ratio",
                "warn_threshold": 1.5,
                "crit_threshold": 2.0,
                "description": "内存碎片率 (rss/used)",
            },
            {
                "name": "redis.keyspace.hit_rate",
                "display_name": "缓存命中率",
                "unit": "%",
                "warn_threshold": 90,
                "crit_threshold": 80,
                "description": "缓存命中率 (低于阈值告警)",
                "comparison": "lt",
            },
        ],
    },

    # ========== Kafka 消息队列指标 ==========
    "Kafka": {
        "performance": [
            {
                "name": "kafka.messages.in_per_sec",
                "display_name": "写入速率",
                "unit": "msg/s",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "每秒写入消息数",
            },
            {
                "name": "kafka.messages.out_per_sec",
                "display_name": "消费速率",
                "unit": "msg/s",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "每秒消费消息数",
            },
        ],
        "capacity": [
            {
                "name": "kafka.consumer.lag",
                "display_name": "消费延迟",
                "unit": "count",
                "warn_threshold": 10000,
                "crit_threshold": 100000,
                "description": "消费者组延迟消息数",
            },
            {
                "name": "kafka.topic.partitions.under_replicated",
                "display_name": "副本不足分区",
                "unit": "count",
                "warn_threshold": 1,
                "crit_threshold": 5,
                "description": "副本不足的分区数",
            },
        ],
        "resource": [
            {
                "name": "kafka.disk.usage",
                "display_name": "磁盘使用率",
                "unit": "%",
                "warn_threshold": 75,
                "crit_threshold": 90,
                "description": "Kafka 数据盘使用率",
            },
        ],
    },

    # ========== Elasticsearch 搜索引擎指标 ==========
    "Elasticsearch": {
        "performance": [
            {
                "name": "es.search.duration.p99",
                "display_name": "搜索 P99 延迟",
                "unit": "ms",
                "warn_threshold": 500,
                "crit_threshold": 2000,
                "description": "搜索请求 P99 延迟",
            },
            {
                "name": "es.indexing.duration.p99",
                "display_name": "索引 P99 延迟",
                "unit": "ms",
                "warn_threshold": 100,
                "crit_threshold": 500,
                "description": "索引请求 P99 延迟",
            },
        ],
        "capacity": [
            {
                "name": "es.disk.usage",
                "display_name": "磁盘使用率",
                "unit": "%",
                "warn_threshold": 75,
                "crit_threshold": 85,
                "description": "ES 数据盘使用率",
            },
            {
                "name": "es.docs.count",
                "display_name": "文档总数",
                "unit": "count",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "索引文档总数",
            },
        ],
        "resource": [
            {
                "name": "es.jvm.heap.usage",
                "display_name": "JVM 堆内存",
                "unit": "%",
                "warn_threshold": 75,
                "crit_threshold": 90,
                "description": "JVM 堆内存使用率",
            },
            {
                "name": "es.cluster.status",
                "display_name": "集群状态",
                "unit": "enum",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "集群状态 (green/yellow/red)",
            },
        ],
    },

    # ========== Nginx 网关指标 ==========
    "Nginx": {
        "performance": [
            {
                "name": "nginx.connections.active",
                "display_name": "活跃连接",
                "unit": "count",
                "warn_threshold": 1000,
                "crit_threshold": 5000,
                "description": "当前活跃连接数",
            },
            {
                "name": "nginx.request.duration.p99",
                "display_name": "请求 P99 延迟",
                "unit": "ms",
                "warn_threshold": 500,
                "crit_threshold": 2000,
                "description": "请求 P99 延迟",
            },
        ],
        "error": [
            {
                "name": "nginx.request.5xx_rate",
                "display_name": "5xx 错误率",
                "unit": "%",
                "warn_threshold": 1,
                "crit_threshold": 5,
                "description": "5xx 响应占比",
            },
        ],
    },

    # ========== Business 业务指标 ==========
    "Business": {
        "business": [
            {
                "name": "business.health_score",
                "display_name": "健康度评分",
                "unit": "score",
                "warn_threshold": 70,
                "crit_threshold": 50,
                "description": "业务整体健康度 (聚合子实体)",
                "comparison": "lt",
            },
            {
                "name": "business.availability",
                "display_name": "可用性",
                "unit": "%",
                "warn_threshold": 99.9,
                "crit_threshold": 99.0,
                "description": "业务整体可用性",
                "comparison": "lt",
            },
        ],
    },

    # ========== Endpoint 端点指标 ==========
    "Endpoint": {
        "performance": [
            {
                "name": "http.endpoint.duration.p99",
                "display_name": "端点 P99 延迟",
                "unit": "ms",
                "warn_threshold": 500,
                "crit_threshold": 2000,
                "description": "端点 P99 延迟",
            },
            {
                "name": "http.endpoint.qps",
                "display_name": "端点 QPS",
                "unit": "req/s",
                "warn_threshold": None,
                "crit_threshold": None,
                "description": "端点每秒请求数",
            },
        ],
        "error": [
            {
                "name": "http.endpoint.error_rate",
                "display_name": "端点错误率",
                "unit": "%",
                "warn_threshold": 1,
                "crit_threshold": 5,
                "description": "端点错误率",
            },
        ],
    },
}


def get_metrics_for_type(type_name: str) -> dict:
    """获取指定实体类型的完整指标定义。"""
    return ENTITY_METRIC_DEFINITIONS.get(type_name, {})


def get_all_metrics_flat(type_name: str) -> list:
    """获取指定实体类型的扁平化指标列表。"""
    type_metrics = ENTITY_METRIC_DEFINITIONS.get(type_name, {})
    flat_list = []
    for dimension, metrics in type_metrics.items():
        for metric in metrics:
            flat_list.append({
                **metric,
                "dimension": dimension,
                "dimension_label": METRIC_DIMENSIONS.get(dimension, dimension),
            })
    return flat_list


def get_metric_threshold(metric_name: str, type_name: str) -> dict:
    """获取指定指标的阈值配置。"""
    type_metrics = ENTITY_METRIC_DEFINITIONS.get(type_name, {})
    for dimension, metrics in type_metrics.items():
        for metric in metrics:
            if metric["name"] == metric_name:
                return {
                    "warn": metric.get("warn_threshold"),
                    "crit": metric.get("crit_threshold"),
                    "comparison": metric.get("comparison", "gt"),
                    "unit": metric.get("unit"),
                }
    return {}


def validate_metric_value(metric_name: str, type_name: str, value: float) -> str:
    """根据阈值判断指标状态。"""
    threshold = get_metric_threshold(metric_name, type_name)
    if not threshold or threshold.get("warn") is None:
        return "ok"
    
    warn = threshold["warn"]
    crit = threshold["crit"]
    comparison = threshold.get("comparison", "gt")
    
    if comparison == "lt":
        # 小于阈值告警（如成功率）
        if value < crit:
            return "critical"
        elif value < warn:
            return "warning"
        return "ok"
    else:
        # 大于阈值告警（如延迟、错误率）
        if value >= crit:
            return "critical"
        elif value >= warn:
            return "warning"
        return "ok"
