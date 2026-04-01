#!/usr/bin/env python3
"""生成模拟数据并插入到 CMDB 数据库。"""

import os
import sys
import json
import psycopg2
from datetime import datetime, timezone

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    "dbname": os.getenv("CMDB_DATABASE", "cmdb"),
}

# 模拟业务数据
BUSINESSES = [
    {
        "type_name": "Business",
        "name": "在线支付",
        "qualified_name": "business:在线支付",
        "attributes": {
            "business_domain": "电商",
            "business_owner": "张三",
            "tech_owner": "李四",
            "slo_availability": 99.9,
            "slo_latency_p99": 200,
            "business_weight": 1.0
        },
        "labels": {"env": "prod", "business_line": "支付"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 85,
        "health_level": "healthy",
        "risk_score": 15
    },
    {
        "type_name": "Business",
        "name": "用户注册",
        "qualified_name": "business:用户注册",
        "attributes": {
            "business_domain": "电商",
            "business_owner": "王五",
            "tech_owner": "赵六",
            "slo_availability": 99.5,
            "slo_latency_p99": 500,
            "business_weight": 0.6
        },
        "labels": {"env": "prod", "business_line": "用户"},
        "biz_service": "用户注册",
        "source": "demo",
        "health_score": 92,
        "health_level": "healthy",
        "risk_score": 8
    }
]

# 模拟主机数据
HOSTS = [
    {
        "type_name": "Host",
        "name": "web-01",
        "qualified_name": "host:web-01",
        "attributes": {"ip": "10.0.1.10", "cpu_cores": 8, "memory_gb": 32, "os": "CentOS 7.9"},
        "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 78,
        "health_level": "healthy",
        "risk_score": 22
    },
    {
        "type_name": "Host",
        "name": "web-02",
        "qualified_name": "host:web-02",
        "attributes": {"ip": "10.0.1.11", "cpu_cores": 8, "memory_gb": 32, "os": "CentOS 7.9"},
        "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 85,
        "health_level": "healthy",
        "risk_score": 15
    },
    {
        "type_name": "Host",
        "name": "app-01",
        "qualified_name": "host:app-01",
        "attributes": {"ip": "10.0.1.20", "cpu_cores": 16, "memory_gb": 64, "os": "CentOS 7.9"},
        "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 92,
        "health_level": "healthy",
        "risk_score": 8
    },
    {
        "type_name": "Host",
        "name": "app-02",
        "qualified_name": "host:app-02",
        "attributes": {"ip": "10.0.1.21", "cpu_cores": 16, "memory_gb": 64, "os": "CentOS 7.9"},
        "labels": {"env": "prod", "region": "cn-east-1", "team": "infra"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 88,
        "health_level": "healthy",
        "risk_score": 12
    },
    {
        "type_name": "Host",
        "name": "db-master",
        "qualified_name": "host:db-master",
        "attributes": {"ip": "10.0.1.30", "cpu_cores": 32, "memory_gb": 128, "os": "CentOS 7.9"},
        "labels": {"env": "prod", "region": "cn-east-1", "team": "DBA"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 65,
        "health_level": "warning",
        "risk_score": 35
    }
]

# 模拟服务数据
SERVICES = [
    {
        "type_name": "Service",
        "name": "gateway",
        "qualified_name": "service:gateway",
        "attributes": {"language": "Java", "framework": "SpringCloudGateway", "port": 80, "team": "架构组"},
        "labels": {"env": "prod", "team": "架构组", "business_line": "支付"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 95,
        "health_level": "healthy",
        "risk_score": 5
    },
    {
        "type_name": "Service",
        "name": "order-service",
        "qualified_name": "service:order-service",
        "attributes": {"language": "Java", "framework": "SpringBoot", "port": 8081, "team": "订单组"},
        "labels": {"env": "prod", "team": "订单组", "business_line": "支付"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 72,
        "health_level": "warning",
        "risk_score": 78
    },
    {
        "type_name": "Service",
        "name": "payment-service",
        "qualified_name": "service:payment-service",
        "attributes": {"language": "Java", "framework": "SpringBoot", "port": 8080, "team": "支付组"},
        "labels": {"env": "prod", "team": "支付组", "business_line": "支付"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 68,
        "health_level": "warning",
        "risk_score": 82
    },
    {
        "type_name": "Service",
        "name": "user-service",
        "qualified_name": "service:user-service",
        "attributes": {"language": "Go", "framework": "Gin", "port": 8083, "team": "用户组"},
        "labels": {"env": "prod", "team": "用户组", "business_line": "用户"},
        "biz_service": "用户注册",
        "source": "demo",
        "health_score": 88,
        "health_level": "healthy",
        "risk_score": 12
    }
]

# 模拟数据库数据
DATABASES = [
    {
        "type_name": "MySQL",
        "name": "payment-db",
        "qualified_name": "mysql:payment-db",
        "attributes": {"db_type": "MySQL", "port": 3306, "db_version": "8.0", "max_connections": 500},
        "labels": {"env": "prod", "team": "DBA"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 55,
        "health_level": "critical",
        "risk_score": 85
    },
    {
        "type_name": "MySQL",
        "name": "order-db",
        "qualified_name": "mysql:order-db",
        "attributes": {"db_type": "MySQL", "port": 3306, "db_version": "8.0", "max_connections": 500},
        "labels": {"env": "prod", "team": "DBA"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 78,
        "health_level": "healthy",
        "risk_score": 22
    },
    {
        "type_name": "Redis",
        "name": "user-cache",
        "qualified_name": "redis:user-cache",
        "attributes": {"db_type": "Redis", "port": 6379, "redis_version": "7.0"},
        "labels": {"env": "prod", "team": "DBA"},
        "biz_service": "在线支付",
        "source": "demo",
        "health_score": 92,
        "health_level": "healthy",
        "risk_score": 8
    }
]

# 模拟网络设备数据
NETWORK_DEVICES = [
    {
        "type_name": "NetworkDevice",
        "name": "核心交换机-01",
        "qualified_name": "network:核心交换机-01",
        "attributes": {"vendor": "Cisco", "model": "C9300", "mgmt_ip": "10.0.0.1", "port_count": 48},
        "labels": {"env": "prod", "region": "cn-east-1"},
        "biz_service": None,
        "source": "demo",
        "health_score": 95,
        "health_level": "healthy",
        "risk_score": 5
    }
]

# 模拟关系数据
RELATIONS = [
    # 业务包含服务
    ("在线支付", "gateway", "includes"),
    ("在线支付", "order-service", "includes"),
    ("在线支付", "payment-service", "includes"),
    ("用户注册", "user-service", "includes"),
    
    # 服务调用关系
    ("gateway", "order-service", "calls"),
    ("gateway", "payment-service", "calls"),
    
    # 服务依赖数据库
    ("payment-service", "payment-db", "depends_on"),
    ("order-service", "order-db", "depends_on"),
    ("user-service", "user-cache", "depends_on"),
    
    # 服务运行在主机上
    ("gateway", "web-01", "runs_on"),
    ("order-service", "app-01", "runs_on"),
    ("payment-service", "app-02", "runs_on"),
    ("user-service", "app-02", "runs_on"),
    ("payment-db", "db-master", "runs_on"),
    ("order-db", "db-master", "runs_on"),
    
    # 主机连接网络设备
    ("web-01", "核心交换机-01", "connected_to"),
    ("app-01", "核心交换机-01", "connected_to"),
    ("app-02", "核心交换机-01", "connected_to"),
    ("db-master", "核心交换机-01", "connected_to")
]

def insert_entity(cur, entity):
    """插入实体数据。"""
    cur.execute("""
        INSERT INTO entity (
            type_name, name, qualified_name, attributes, labels, 
            biz_service, source, health_score, health_level, risk_score,
            status, created_at, updated_at
        ) VALUES (
            %(type_name)s, %(name)s, %(qualified_name)s, %(attributes)s, %(labels)s,
            %(biz_service)s, %(source)s, %(health_score)s, %(health_level)s, %(risk_score)s,
            'active', now(), now()
        ) ON CONFLICT (qualified_name) DO UPDATE SET
            attributes = EXCLUDED.attributes,
            labels = EXCLUDED.labels,
            biz_service = EXCLUDED.biz_service,
            health_score = EXCLUDED.health_score,
            health_level = EXCLUDED.health_level,
            risk_score = EXCLUDED.risk_score,
            updated_at = now()
        RETURNING guid
    """, {
        "type_name": entity["type_name"],
        "name": entity["name"],
        "qualified_name": entity["qualified_name"],
        "attributes": json.dumps(entity["attributes"]),
        "labels": json.dumps(entity["labels"]),
        "biz_service": entity.get("biz_service"),
        "source": entity.get("source", "demo"),
        "health_score": entity.get("health_score"),
        "health_level": entity.get("health_level"),
        "risk_score": entity.get("risk_score")
    })
    return cur.fetchone()[0]

def insert_relationship(cur, from_name, to_name, rel_type):
    """插入关系数据。"""
    # 先获取实体 GUID
    cur.execute("SELECT guid FROM entity WHERE name = %s", (from_name,))
    from_result = cur.fetchone()
    cur.execute("SELECT guid FROM entity WHERE name = %s", (to_name,))
    to_result = cur.fetchone()
    
    if from_result and to_result:
        from_guid = from_result[0]
        to_guid = to_result[0]
        
        cur.execute("""
            INSERT INTO relationship (
                type_name, from_guid, to_guid,
                end1_guid, end2_guid,
                source, confidence, is_active, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, 'demo', 1.0, true, now()
            ) ON CONFLICT DO NOTHING
        """, (rel_type, from_guid, to_guid, from_guid, to_guid))

def generate_demo_data():
    """生成模拟数据。"""
    print("🎭 生成模拟数据")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        cur = conn.cursor()
        
        print("   🏢 业务实体...")
        business_guids = {}
        for biz in BUSINESSES:
            guid = insert_entity(cur, biz)
            business_guids[biz["name"]] = guid
            print(f"      ✅ {biz['name']}")
        
        print("   🖥️  主机实体...")
        host_guids = {}
        for host in HOSTS:
            guid = insert_entity(cur, host)
            host_guids[host["name"]] = guid
            print(f"      ✅ {host['name']}")
        
        print("   🔧 服务实体...")
        service_guids = {}
        for svc in SERVICES:
            guid = insert_entity(cur, svc)
            service_guids[svc["name"]] = guid
            print(f"      ✅ {svc['name']}")
        
        print("   🗄️  数据库实体...")
        db_guids = {}
        for db in DATABASES:
            guid = insert_entity(cur, db)
            db_guids[db["name"]] = guid
            print(f"      ✅ {db['name']}")
        
        print("   🌐 网络设备实体...")
        net_guids = {}
        for net in NETWORK_DEVICES:
            guid = insert_entity(cur, net)
            net_guids[net["name"]] = guid
            print(f"      ✅ {net['name']}")
        
        print("   🔗 关系数据...")
        for from_name, to_name, rel_type in RELATIONS:
            insert_relationship(cur, from_name, to_name, rel_type)
        print(f"      ✅ {len(RELATIONS)} 条关系")
        
        conn.commit()
        
        # 验证数据
        cur.execute("SELECT COUNT(*) FROM entity WHERE source = 'demo'")
        entity_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM relationship WHERE source = 'demo'")
        rel_count = cur.fetchone()[0]
        
        print(f"\n✅ 模拟数据生成完成")
        print(f"   实体: {entity_count} 个")
        print(f"   关系: {rel_count} 条")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 生成失败: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    generate_demo_data()