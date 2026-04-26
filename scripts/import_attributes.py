"""
Phase 3: 元属性体系填充
导入各实体类型的属性定义到 meta_attribute_def 表
"""
import asyncpg, asyncio

# ══════════════════════════════════════════════════════════════
# 元属性定义（按实体类型组织）
# ══════════════════════════════════════════════════════════════

META_ATTRIBUTES = {
    # ========== 通用属性（所有实体类型共享） ==========
    "_common": [
        {"key": "name", "name": "名称", "type": "string", "required": True, "max_length": 512},
        {"key": "display_name", "name": "显示名称", "type": "string", "max_length": 256},
        {"key": "description", "name": "描述", "type": "string", "max_length": 2048},
        {"key": "environment", "name": "环境", "type": "enum", "enum": ["production", "staging", "development", "test"]},
        {"key": "datacenter", "name": "数据中心", "type": "string"},
        {"key": "region", "name": "地域", "type": "string"},
        {"key": "team", "name": "负责团队", "type": "string"},
        {"key": "business_line", "name": "业务线", "type": "string"},
        {"key": "owner", "name": "负责人", "type": "string"},
        {"key": "created_by", "name": "创建者", "type": "string"},
        {"key": "last_modified_by", "name": "最后修改者", "type": "string"},
    ],

    # ========== Service 服务属性 ==========
    "Service": [
        {"key": "service.type", "name": "服务类型", "type": "enum", "enum": ["web", "api", "grpc", "mq", "job", "other"]},
        {"key": "service.language", "name": "开发语言", "type": "enum", "enum": ["java", "go", "python", "nodejs", "rust", "c++", "other"]},
        {"key": "service.framework", "name": "框架", "type": "string"},
        {"key": "service.version", "name": "版本", "type": "string"},
        {"key": "service.port", "name": "服务端口", "type": "int", "min": 1, "max": 65535},
        {"key": "service.health_check_url", "name": "健康检查URL", "type": "url"},
        {"key": "service.sla_target", "name": "SLA目标(%)", "type": "float", "min": 0, "max": 100},
        {"key": "service.deployment_mode", "name": "部署方式", "type": "enum", "enum": ["k8s", "docker", "vm", "bare_metal", "serverless"]},
        {"key": "service.replicas", "name": "副本数", "type": "int", "min": 1},
        {"key": "service.namespace", "name": "K8s命名空间", "type": "string"},
    ],

    # ========== Host 主机属性 ==========
    "Host": [
        {"key": "host.ip", "name": "IP地址", "type": "ip"},
        {"key": "host.hostname", "name": "主机名", "type": "string"},
        {"key": "host.os", "name": "操作系统", "type": "string"},
        {"key": "host.os_version", "name": "OS版本", "type": "string"},
        {"key": "host.arch", "name": "架构", "type": "enum", "enum": ["x86_64", "arm64", "aarch64"]},
        {"key": "host.cpu_cores", "name": "CPU核数", "type": "int", "min": 1},
        {"key": "host.memory_gb", "name": "内存(GB)", "type": "float", "min": 0},
        {"key": "host.disk_gb", "name": "磁盘(GB)", "type": "float", "min": 0},
        {"key": "host.cloud_provider", "name": "云厂商", "type": "enum", "enum": ["aliyun", "huawei", "tencent", "aws", "azure", "gcp", "on_premise"]},
        {"key": "host.instance_type", "name": "实例规格", "type": "string"},
        {"key": "host.zone", "name": "可用区", "type": "string"},
    ],

    # ========== Container 容器属性 ==========
    "Container": [
        {"key": "container.image", "name": "镜像", "type": "string"},
        {"key": "container.image_tag", "name": "镜像标签", "type": "string"},
        {"key": "container.runtime", "name": "运行时", "type": "enum", "enum": ["docker", "containerd", "cri-o"]},
        {"key": "container.cpu_limit", "name": "CPU限制", "type": "string"},
        {"key": "container.memory_limit", "name": "内存限制", "type": "string"},
        {"key": "container.restart_count", "name": "重启次数", "type": "int"},
        {"key": "container.namespace", "name": "命名空间", "type": "string"},
        {"key": "container.pod_name", "name": "所属Pod", "type": "string"},
    ],

    # ========== Database 数据库属性 ==========
    "Database": [
        {"key": "db.type", "name": "数据库类型", "type": "enum", "enum": ["mysql", "postgresql", "mongodb", "redis", "elasticsearch", "clickhouse", "oracle", "sqlserver"]},
        {"key": "db.version", "name": "版本", "type": "string"},
        {"key": "db.host", "name": "主机", "type": "string"},
        {"key": "db.port", "name": "端口", "type": "int", "min": 1, "max": 65535},
        {"key": "db.name", "name": "数据库名", "type": "string"},
        {"key": "db.max_connections", "name": "最大连接数", "type": "int", "min": 1},
        {"key": "db.charset", "name": "字符集", "type": "string"},
        {"key": "db.replication_mode", "name": "复制模式", "type": "enum", "enum": ["master_slave", "cluster", "standalone"]},
    ],

    # ========== Redis 缓存属性 ==========
    "Redis": [
        {"key": "redis.version", "name": "版本", "type": "string"},
        {"key": "redis.host", "name": "主机", "type": "string"},
        {"key": "redis.port", "name": "端口", "type": "int", "min": 1, "max": 65535},
        {"key": "redis.max_memory", "name": "最大内存", "type": "string"},
        {"key": "redis.eviction_policy", "name": "淘汰策略", "type": "enum", "enum": ["noeviction", "allkeys-lru", "volatile-lru", "allkeys-random", "volatile-random", "volatile-ttl"]},
        {"key": "redis.mode", "name": "模式", "type": "enum", "enum": ["standalone", "sentinel", "cluster"]},
        {"key": "redis.database_count", "name": "数据库数量", "type": "int"},
    ],

    # ========== MessageQueue 消息队列属性 ==========
    "MessageQueue": [
        {"key": "mq.type", "name": "MQ类型", "type": "enum", "enum": ["kafka", "rocketmq", "rabbitmq", "pulsar", "nats"]},
        {"key": "mq.version", "name": "版本", "type": "string"},
        {"key": "mq.broker_count", "name": "Broker数量", "type": "int"},
        {"key": "mq.topic_count", "name": "Topic数量", "type": "int"},
        {"key": "mq.replication_factor", "name": "复制因子", "type": "int"},
    ],

    # ========== Page 页面属性 ==========
    "Page": [
        {"key": "page.url", "name": "页面URL", "type": "url"},
        {"key": "page.title", "name": "页面标题", "type": "string"},
        {"key": "page.app_type", "name": "应用类型", "type": "enum", "enum": ["web", "android", "ios", "harmonyos", "mini_program"]},
        {"key": "page.framework", "name": "前端框架", "type": "enum", "enum": ["react", "vue", "angular", "svelte", "nextjs", "nuxt", "other"]},
        {"key": "page.bundle_size", "name": "包大小(bytes)", "type": "int"},
    ],

    # ========== Process 进程属性 ==========
    "Process": [
        {"key": "process.pid", "name": "PID", "type": "int", "min": 1},
        {"key": "process.name", "name": "进程名", "type": "string"},
        {"key": "process.user", "name": "运行用户", "type": "string"},
        {"key": "process.cmdline", "name": "启动命令", "type": "string"},
        {"key": "process.start_time", "name": "启动时间", "type": "datetime"},
        {"key": "process.pid_file", "name": "PID文件", "type": "string"},
    ],

    # ========== K8sCluster 属性 ==========
    "K8sCluster": [
        {"key": "k8s.version", "name": "K8s版本", "type": "string"},
        {"key": "k8s.provider", "name": "K8s发行版", "type": "enum", "enum": ["kubernetes", "openshift", "rancher", "aks", "eks", "gke", "ack"]},
        {"key": "k8s.api_server", "name": "API Server地址", "type": "url"},
        {"key": "k8s.node_count", "name": "节点数", "type": "int"},
        {"key": "k8s.namespace_count", "name": "命名空间数", "type": "int"},
    ],

    # ========== K8sNode 属性 ==========
    "K8sNode": [
        {"key": "k8s.node.ip", "name": "节点IP", "type": "ip"},
        {"key": "k8s.node.role", "name": "角色", "type": "enum", "enum": ["master", "worker", "infrastructure"]},
        {"key": "k8s.node.os", "name": "操作系统", "type": "string"},
        {"key": "k8s.node.kernel", "name": "内核版本", "type": "string"},
        {"key": "k8s.node.container_runtime", "name": "容器运行时", "type": "string"},
        {"key": "k8s.node.allocatable_cpu", "name": "可分配CPU", "type": "string"},
        {"key": "k8s.node.allocatable_memory", "name": "可分配内存", "type": "string"},
    ],

    # ========== K8sPod 属性 ==========
    "K8sPod": [
        {"key": "k8s.pod.namespace", "name": "命名空间", "type": "string"},
        {"key": "k8s.pod.node", "name": "所在节点", "type": "string"},
        {"key": "k8s.pod.status", "name": "状态", "type": "enum", "enum": ["running", "pending", "succeeded", "failed", "unknown"]},
        {"key": "k8s.pod.restart_count", "name": "重启次数", "type": "int"},
        {"key": "k8s.pod.ip", "name": "Pod IP", "type": "ip"},
        {"key": "k8s.pod.workload", "name": "所属工作负载", "type": "string"},
    ],

    # ========== NetworkDevice 网络设备属性 ==========
    "NetworkDevice": [
        {"key": "net.vendor", "name": "厂商", "type": "string"},
        {"key": "net.model", "name": "型号", "type": "string"},
        {"key": "net.ip", "name": "管理IP", "type": "ip"},
        {"key": "net.snmp_version", "name": "SNMP版本", "type": "enum", "enum": ["v1", "v2c", "v3"]},
        {"key": "net.location", "name": "物理位置", "type": "string"},
    ],
}


async def import_attributes():
    """导入元属性定义"""
    conn = await asyncpg.connect('postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb')
    
    total = 0
    for entity_type, attrs in META_ATTRIBUTES.items():
        for attr in attrs:
            try:
                await conn.execute(
                    """INSERT INTO meta_attribute_def (attr_key, display_name, data_type, is_required, max_length, enum_values, source)
                       VALUES ($1, $2, $3, $4, $5, $6, 'builtin')
                       ON CONFLICT (attr_key) DO UPDATE SET display_name=$2, data_type=$3, is_required=$4""",
                    attr["key"], attr["name"], attr["type"], attr.get("required", False),
                    attr.get("max_length"), 
                    __import__('json').dumps(attr.get("enum")) if attr.get("enum") else None
                )
                total += 1
            except Exception as e:
                print(f'  ! {attr["key"]}: {e}')
    
    # 验证
    count = await conn.fetchval("SELECT COUNT(*) FROM meta_attribute_def")
    print(f'✅ 导入完成：{total} 个元属性')
    print(f'✅ 数据库中总计：{count} 个元属性')
    
    # 按类型统计
    rows = await conn.fetch(
        "SELECT data_type, COUNT(*) as cnt FROM meta_attribute_def GROUP BY data_type ORDER BY cnt DESC"
    )
    print()
    print('按数据类型统计：')
    for r in rows:
        print(f'  {r["data_type"]:15s} {r["cnt"]:3d} 个')
    
    await conn.close()

asyncio.run(import_attributes())
