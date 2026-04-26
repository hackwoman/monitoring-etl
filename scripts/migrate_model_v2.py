"""
数据模型重构迁移脚本
Phase 1: 基础模型重构

执行方式：
  在实例 B 上执行：
  cd /home/lily/monitoring-etl
  python3 scripts/migrate_model_v2.py

注意：
  - 执行前请备份数据库
  - 脚本会创建新表 + 修改现有表 + 迁移数据
"""
import asyncio
import asyncpg
import json
from datetime import datetime

# 数据库连接配置
DATABASE_URL = "postgresql://postgres:M9kX%23pL2vQ!zR7w@47.93.61.196:5432/cmdb"

# ══════════════════════════════════════════════════════════════
# 新表定义
# ══════════════════════════════════════════════════════════════

NEW_TABLES = """
-- 1. 指标定义表
CREATE TABLE IF NOT EXISTS metric_def (
    metric_id VARCHAR(256) PRIMARY KEY,
    display_name VARCHAR(256) NOT NULL,
    category VARCHAR(64) NOT NULL,          -- performance/reliability/resource/business/capacity/security
    sub_category VARCHAR(64),               -- latency/throughput/utilization/...
    entity_type VARCHAR(128),               -- 关联的实体类型（NULL表示通用）
    metric_type VARCHAR(32) DEFAULT 'gauge', -- gauge/counter/histogram/formula
    unit VARCHAR(32),
    description TEXT,
    warn_threshold FLOAT,
    crit_threshold FLOAT,
    comparison VARCHAR(8) DEFAULT 'gt',     -- gt/lt/eq/gte/lte
    formula TEXT,
    formula_vars JSONB DEFAULT '[]',
    source VARCHAR(64) DEFAULT 'builtin',
    is_custom BOOLEAN DEFAULT FALSE,
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 指标映射表（补偿机制）
CREATE TABLE IF NOT EXISTS metric_mapping (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(64) NOT NULL,
    source_metric VARCHAR(256) NOT NULL,
    target_metric_id VARCHAR(256) REFERENCES metric_def(metric_id),
    confidence FLOAT DEFAULT 1.0,
    status VARCHAR(32) DEFAULT 'pending',
    created_by VARCHAR(128) DEFAULT 'auto',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_system, source_metric)
);

-- 3. 元属性定义表
CREATE TABLE IF NOT EXISTS meta_attribute_def (
    attr_key VARCHAR(128) PRIMARY KEY,
    display_name VARCHAR(256) NOT NULL,
    data_type VARCHAR(32) NOT NULL,
    field_name VARCHAR(128),
    is_required BOOLEAN DEFAULT FALSE,
    is_dictionary BOOLEAN DEFAULT FALSE,
    default_value JSONB,
    min_value FLOAT,
    max_value FLOAT,
    min_length INTEGER,
    max_length INTEGER,
    pattern VARCHAR(512),
    enum_values JSONB,
    reference_count INTEGER DEFAULT 0,
    source VARCHAR(64) DEFAULT 'builtin',
    is_custom BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 字典表
CREATE TABLE IF NOT EXISTS dictionary (
    dict_key VARCHAR(128) PRIMARY KEY,
    dict_name VARCHAR(256),
    description TEXT,
    values JSONB NOT NULL,
    is_builtin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. 维度映射表（补偿机制）
CREATE TABLE IF NOT EXISTS dimension_mapping (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(64) NOT NULL,
    source_dimension VARCHAR(256) NOT NULL,
    target_label_key VARCHAR(128),
    transform_rule JSONB,
    status VARCHAR(32) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_system, source_dimension)
);

-- 6. 动态扩展指标表
CREATE TABLE IF NOT EXISTS dynamic_metric (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(64),
    source_metric VARCHAR(256),
    inferred_entity_type VARCHAR(128),
    inferred_metric_name VARCHAR(256),
    sample_dimensions JSONB,
    status VARCHAR(32) DEFAULT 'pending',
    confirmed_by VARCHAR(128),
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. 动态扩展实体类型表
CREATE TABLE IF NOT EXISTS dynamic_entity_type (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(128),
    source_type VARCHAR(128),
    inferred_type_name VARCHAR(128),
    inferred_layer VARCHAR(32),
    sample_entities JSONB,
    status VARCHAR(32) DEFAULT 'pending',
    confirmed_by VARCHAR(128),
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

# ══════════════════════════════════════════════════════════════
# 实体类型迁移映射
# ══════════════════════════════════════════════════════════════

# 旧分类 → 新层级 + 新分类
ENTITY_TYPE_MIGRATION = {
    # L1 业务层
    "Business": {"layer": "L1_business", "category": "business", "new_name": "BusinessModule"},
    
    # L2 应用层
    "Service": {"layer": "L2_application", "category": "backend"},
    "Endpoint": {"layer": "L2_application", "category": "backend", "new_name": "Interface"},
    "Page": {"layer": "L2_application", "category": "frontend"},
    "HttpRequest": {"layer": "L2_application", "category": "frontend"},
    
    # L3 服务层
    "Database": {"layer": "L3_service", "category": "database"},
    "Middleware": {"layer": "L3_service", "category": "middleware"},
    "MySQL": {"layer": "L3_service", "category": "database"},
    "Redis": {"layer": "L3_service", "category": "cache"},
    
    # L4 基础设施层
    "Host": {"layer": "L4_infrastructure", "category": "host"},
    "IP": {"layer": "L4_infrastructure", "category": "network"},
    "NetworkDevice": {"layer": "L4_infrastructure", "category": "network"},
    "K8sCluster": {"layer": "L4_infrastructure", "category": "k8s", "new_tags": {"type": "k8s-cluster"}},
    "K8sPod": {"layer": "L4_infrastructure", "category": "k8s", "new_tags": {"type": "k8s-pod"}},
}

# 新增实体类型
NEW_ENTITY_TYPES = [
    # L1 业务层
    {"type_name": "BusinessEvent", "display_name": "业务事件", "layer": "L1_business", "category": "business"},
    {"type_name": "E2ECallChain", "display_name": "端到端调用链", "layer": "L1_business", "category": "business"},
    
    # L2 应用层
    {"type_name": "TerminalApp", "display_name": "终端应用", "layer": "L2_application", "category": "frontend"},
    {"type_name": "ServiceInstance", "display_name": "服务实例", "layer": "L2_application", "category": "backend"},
    {"type_name": "KeyMethod", "display_name": "关键方法", "layer": "L2_application", "category": "backend"},
    {"type_name": "UserAction", "display_name": "用户操作", "layer": "L2_application", "category": "frontend"},
    
    # L3 服务层
    {"type_name": "Cache", "display_name": "缓存", "layer": "L3_service", "category": "cache"},
    {"type_name": "MessageQueue", "display_name": "消息队列", "layer": "L3_service", "category": "mq"},
    {"type_name": "ObjectStorage", "display_name": "对象存储", "layer": "L3_service", "category": "storage"},
    {"type_name": "SearchEngine", "display_name": "搜索引擎", "layer": "L3_service", "category": "search"},
    
    # L4 基础设施层
    {"type_name": "Container", "display_name": "容器", "layer": "L4_infrastructure", "category": "container"},
    {"type_name": "Process", "display_name": "进程", "layer": "L4_infrastructure", "category": "process"},
    {"type_name": "ProcessGroup", "display_name": "进程组", "layer": "L4_infrastructure", "category": "process"},
    {"type_name": "StorageDevice", "display_name": "存储设备", "layer": "L4_infrastructure", "category": "storage"},
    {"type_name": "CloudResource", "display_name": "云资源", "layer": "L4_infrastructure", "category": "cloud"},
    {"type_name": "K8sNode", "display_name": "K8s节点", "layer": "L4_infrastructure", "category": "k8s"},
    {"type_name": "K8sService", "display_name": "K8s服务", "layer": "L4_infrastructure", "category": "k8s"},
    {"type_name": "K8sWorkload", "display_name": "K8s工作负载", "layer": "L4_infrastructure", "category": "k8s"},
]


async def run_migration():
    """执行迁移"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        print("=== 开始数据模型重构迁移 ===")
        print()
        
        # Step 1: 创建新表
        print("Step 1: 创建新表...")
        await conn.execute(NEW_TABLES)
        print("  ✅ 7 个新表创建完成")
        
        # Step 2: 给 entity_type_def 添加 layer 字段
        print("Step 2: 给 entity_type_def 添加 layer 字段...")
        try:
            await conn.execute("ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS layer VARCHAR(32)")
            print("  ✅ layer 字段添加完成")
        except Exception as e:
            print(f"  ⚠️ 字段可能已存在: {e}")
        
        # Step 3: 迁移现有实体类型的层级
        print("Step 3: 迁移现有实体类型的层级...")
        for type_name, migration in ENTITY_TYPE_MIGRATION.items():
            layer = migration["layer"]
            category = migration["category"]
            new_name = migration.get("new_name")
            
            if new_name:
                # 重命名实体类型
                await conn.execute(
                    "UPDATE entity_type_def SET type_name = $1 WHERE type_name = $2",
                    new_name, type_name
                )
                # 更新引用
                await conn.execute(
                    "UPDATE entity SET type_name = $1 WHERE type_name = $2",
                    new_name, type_name
                )
                type_name = new_name
            
            await conn.execute(
                "UPDATE entity_type_def SET layer = $1, category = $2 WHERE type_name = $3",
                layer, category, type_name
            )
            print(f"  ✅ {type_name} → {layer}/{category}")
        
        # Step 4: 创建新实体类型
        print("Step 4: 创建新实体类型...")
        for etype in NEW_ENTITY_TYPES:
            try:
                await conn.execute(
                    """INSERT INTO entity_type_def (type_name, display_name, layer, category, is_custom, version)
                       VALUES ($1, $2, $3, $4, false, 1)
                       ON CONFLICT (type_name) DO UPDATE SET layer = $3, category = $4""",
                    etype["type_name"], etype["display_name"], etype["layer"], etype["category"]
                )
                print(f"  ✅ {etype['type_name']} ({etype['display_name']})")
            except Exception as e:
                print(f"  ⚠️ {etype['type_name']}: {e}")
        
        # Step 5: 验证
        print()
        print("Step 5: 验证迁移结果...")
        rows = await conn.fetch(
            "SELECT type_name, layer, category FROM entity_type_def ORDER BY layer, category, type_name"
        )
        print(f"  总实体类型数: {len(rows)}")
        print()
        current_layer = None
        for row in rows:
            if row['layer'] != current_layer:
                current_layer = row['layer']
                print(f"  [{current_layer}]")
            print(f"    {row['type_name']:30s} | {row['category']}")
        
        print()
        print("=== 迁移完成 ===")
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
