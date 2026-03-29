#!/usr/bin/env python3
"""Phase 2 数据模型迁移脚本。

功能：
1. entity_type_def 重构（新增 category/icon/definition/is_custom/version）
2. entity 表增强（health/risk/biz 字段）
3. attribute_template 表创建
4. relationship 表增强（重命名列语义化）
5. 预置数据通过 seed_phase2.py 加载
"""

import os
import sys
import psycopg2

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    "dbname": os.getenv("CMDB_DATABASE", "cmdb"),
}

MIGRATION_SQL = """
-- ============================================================
-- Phase 2: 认知层数据模型迁移
-- ============================================================

BEGIN;

-- 1. entity_type_def 重构
ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS display_name VARCHAR(256);
ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS category VARCHAR(64) DEFAULT 'custom';
ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS icon VARCHAR(128);
ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS super_type VARCHAR(128);
ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS definition JSONB DEFAULT '{}';
ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS is_custom BOOLEAN DEFAULT false;
ALTER TABLE entity_type_def ADD COLUMN IF NOT EXISTS version INT DEFAULT 1;

-- 2. entity 表增强
ALTER TABLE entity ADD COLUMN IF NOT EXISTS expected_metrics JSONB DEFAULT '[]';
ALTER TABLE entity ADD COLUMN IF NOT EXISTS expected_relations JSONB DEFAULT '[]';
ALTER TABLE entity ADD COLUMN IF NOT EXISTS health_score INT;
ALTER TABLE entity ADD COLUMN IF NOT EXISTS health_level VARCHAR(16);
ALTER TABLE entity ADD COLUMN IF NOT EXISTS health_detail JSONB;
ALTER TABLE entity ADD COLUMN IF NOT EXISTS last_observed TIMESTAMPTZ;
ALTER TABLE entity ADD COLUMN IF NOT EXISTS biz_service VARCHAR(256);
ALTER TABLE entity ADD COLUMN IF NOT EXISTS risk_score INT;
ALTER TABLE entity ADD COLUMN IF NOT EXISTS propagation_hops INT;
ALTER TABLE entity ADD COLUMN IF NOT EXISTS blast_radius INT;

-- 新增索引
CREATE INDEX IF NOT EXISTS idx_entity_health ON entity(health_level) 
    WHERE health_level IN ('warning', 'critical', 'down');
CREATE INDEX IF NOT EXISTS idx_entity_risk ON entity(risk_score DESC) 
    WHERE risk_score > 50;
CREATE INDEX IF NOT EXISTS idx_entity_biz ON entity(biz_service) 
    WHERE biz_service IS NOT NULL;

-- 3. attribute_template 表
CREATE TABLE IF NOT EXISTS attribute_template (
    template_name   VARCHAR(128) PRIMARY KEY,
    category        VARCHAR(64),
    attributes      JSONB NOT NULL DEFAULT '[]',
    description     TEXT,
    is_builtin      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 4. relationship 表语义化列名（添加新列，保留旧列兼容）
ALTER TABLE relationship ADD COLUMN IF NOT EXISTS from_guid UUID;
ALTER TABLE relationship ADD COLUMN IF NOT EXISTS to_guid UUID;

-- 将旧数据迁移到新列
UPDATE relationship SET from_guid = end1_guid WHERE from_guid IS NULL;
UPDATE relationship SET to_guid = end2_guid WHERE to_guid IS NULL;

-- 新增索引
CREATE INDEX IF NOT EXISTS idx_rel_from_new ON relationship(from_guid) WHERE from_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rel_to_new ON relationship(to_guid) WHERE to_guid IS NOT NULL;

-- 5. 事件订阅表
CREATE TABLE IF NOT EXISTS cmdb_event_subscription (
    subscription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber      VARCHAR(256) NOT NULL,
    event_types     VARCHAR(64)[] NOT NULL,
    filter          JSONB DEFAULT '{}',
    callback_url    VARCHAR(512),
    callback_mode   VARCHAR(16) DEFAULT 'webhook',
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cmdb_event_log (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      VARCHAR(64) NOT NULL,
    entity_guid     UUID,
    payload         JSONB,
    published_at    TIMESTAMPTZ DEFAULT now(),
    status          VARCHAR(16) DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_event_log_status ON cmdb_event_log(status) WHERE status = 'pending';

-- 6. 数据质量检查规则表
CREATE TABLE IF NOT EXISTS data_check_rule (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name       VARCHAR(256) NOT NULL,
    rule_type       VARCHAR(32) NOT NULL,       -- completeness / consistency / accuracy / uniqueness
    target_type     VARCHAR(128),               -- 检查的实体类型, NULL=全部
    check_sql       TEXT NOT NULL,
    expected_result VARCHAR(32) DEFAULT 'empty', -- empty = 期望返回0行
    severity        VARCHAR(16) DEFAULT 'warning',
    check_schedule  VARCHAR(64) DEFAULT '0 2 * * *',
    is_builtin      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_quality_snapshot (
    snapshot_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_time   TIMESTAMPTZ DEFAULT now(),
    overall_score   INT,
    total_entities  INT,
    total_rules     INT,
    passed_rules    INT,
    failed_rules    INT,
    type_scores     JSONB DEFAULT '{}',
    issues          JSONB DEFAULT '[]'
);

COMMIT;
"""


def migrate():
    """Run Phase 2 migration."""
    print("🔧 Phase 2 数据模型迁移")
    print(f"   目标数据库: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute(MIGRATION_SQL)
        conn.commit()
        print("✅ 迁移完成")

        # 验证
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'entity_type_def' ORDER BY ordinal_position")
        cols = [r[0] for r in cur.fetchall()]
        print(f"   entity_type_def 列: {cols}")

        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'entity' ORDER BY ordinal_position")
        cols = [r[0] for r in cur.fetchall()]
        print(f"   entity 列: {cols}")

        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        tables = [r[0] for r in cur.fetchall()]
        print(f"   所有表: {tables}")

    except Exception as e:
        conn.rollback()
        print(f"❌ 迁移失败: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrate()
