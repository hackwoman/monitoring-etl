"""
Phase 3 补充：创建字典表数据
"""
import asyncpg, asyncio
import json

DICTIONARIES = [
    {
        "key": "env",
        "name": "环境",
        "values": [
            {"code": "production", "label": "生产环境"},
            {"code": "staging", "label": "预发布环境"},
            {"code": "development", "label": "开发环境"},
            {"code": "test", "label": "测试环境"},
        ]
    },
    {
        "key": "cloud_provider",
        "name": "云厂商",
        "values": [
            {"code": "aliyun", "label": "阿里云"},
            {"code": "huawei", "label": "华为云"},
            {"code": "tencent", "label": "腾讯云"},
            {"code": "aws", "label": "AWS"},
            {"code": "azure", "label": "Azure"},
            {"code": "gcp", "label": "GCP"},
            {"code": "on_premise", "label": "自建"},
        ]
    },
    {
        "key": "service_type",
        "name": "服务类型",
        "values": [
            {"code": "web", "label": "Web服务"},
            {"code": "api", "label": "API服务"},
            {"code": "grpc", "label": "gRPC服务"},
            {"code": "mq", "label": "消息队列"},
            {"code": "job", "label": "定时任务"},
            {"code": "other", "label": "其他"},
        ]
    },
    {
        "key": "db_type",
        "name": "数据库类型",
        "values": [
            {"code": "mysql", "label": "MySQL"},
            {"code": "postgresql", "label": "PostgreSQL"},
            {"code": "mongodb", "label": "MongoDB"},
            {"code": "redis", "label": "Redis"},
            {"code": "elasticsearch", "label": "Elasticsearch"},
            {"code": "clickhouse", "label": "ClickHouse"},
            {"code": "oracle", "label": "Oracle"},
            {"code": "sqlserver", "label": "SQL Server"},
        ]
    },
    {
        "key": "mq_type",
        "name": "消息队列类型",
        "values": [
            {"code": "kafka", "label": "Kafka"},
            {"code": "rocketmq", "label": "RocketMQ"},
            {"code": "rabbitmq", "label": "RabbitMQ"},
            {"code": "pulsar", "label": "Pulsar"},
            {"code": "nats", "label": "NATS"},
        ]
    },
    {
        "key": "k8s_provider",
        "name": "K8s发行版",
        "values": [
            {"code": "kubernetes", "label": "原生Kubernetes"},
            {"code": "openshift", "label": "OpenShift"},
            {"code": "rancher", "label": "Rancher"},
            {"code": "aks", "label": "Azure AKS"},
            {"code": "eks", "label": "AWS EKS"},
            {"code": "gke", "label": "GCP GKE"},
            {"code": "ack", "label": "阿里云ACK"},
        ]
    },
    {
        "key": "k8s_node_role",
        "name": "K8s节点角色",
        "values": [
            {"code": "master", "label": "Master节点"},
            {"code": "worker", "label": "Worker节点"},
            {"code": "infrastructure", "label": "基础设施节点"},
        ]
    },
    {
        "key": "process_runtime",
        "name": "容器运行时",
        "values": [
            {"code": "docker", "label": "Docker"},
            {"code": "containerd", "label": "containerd"},
            {"code": "cri-o", "label": "CRI-O"},
        ]
    },
    {
        "key": "frontend_framework",
        "name": "前端框架",
        "values": [
            {"code": "react", "label": "React"},
            {"code": "vue", "label": "Vue"},
            {"code": "angular", "label": "Angular"},
            {"code": "svelte", "label": "Svelte"},
            {"code": "nextjs", "label": "Next.js"},
            {"code": "nuxt", "label": "Nuxt"},
            {"code": "other", "label": "其他"},
        ]
    },
    {
        "key": "app_type",
        "name": "应用类型",
        "values": [
            {"code": "web", "label": "Web应用"},
            {"code": "android", "label": "Android"},
            {"code": "ios", "label": "iOS"},
            {"code": "harmonyos", "label": "HarmonyOS"},
            {"code": "mini_program", "label": "小程序"},
        ]
    },
]

async def import_dictionaries():
    conn = await asyncpg.connect('postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb')
    
    for d in DICTIONARIES:
        try:
            await conn.execute(
                """INSERT INTO dictionary (dict_key, dict_name, values, is_builtin)
                   VALUES ($1, $2, $3, true)
                   ON CONFLICT (dict_key) DO UPDATE SET dict_name=$2, values=$3""",
                d["key"], d["name"], json.dumps(d["values"], ensure_ascii=False)
            )
            print(f'  ✅ {d["key"]} ({d["name"]})')
        except Exception as e:
            print(f'  ! {d["key"]}: {e}')
    
    count = await conn.fetchval("SELECT COUNT(*) FROM dictionary")
    print(f'\n✅ 字典总数：{count} 个')
    
    await conn.close()

asyncio.run(import_dictionaries())
