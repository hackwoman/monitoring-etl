#!/usr/bin/env python3
"""Database initialization script for PostgreSQL CMDB."""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    "dbname": "postgres",
}

CMDB_DB = os.getenv("CMDB_DATABASE", "cmdb")

INIT_SQL = """
-- ============================================================
-- CMDB Core Schema
-- ============================================================

-- Entity Type Definitions
CREATE TABLE IF NOT EXISTS entity_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    super_types     JSONB DEFAULT '[]',
    attribute_defs  JSONB DEFAULT '{}',
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Seed default entity types
INSERT INTO entity_type_def (type_name, description) VALUES
    ('Host',        '物理机/虚拟机/云主机'),
    ('Service',     '微服务'),
    ('Application', '应用实例'),
    ('Database',    '数据库实例'),
    ('Middleware',  '中间件: Redis/MQ/ES 等'),
    ('IP',          'IP 地址'),
    ('Endpoint',    'API 端点')
ON CONFLICT (type_name) DO NOTHING;

-- Entity Instances
CREATE TABLE IF NOT EXISTS entity (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL REFERENCES entity_type_def(type_name),
    name            VARCHAR(512) NOT NULL,
    qualified_name  VARCHAR(1024) UNIQUE NOT NULL,
    attributes      JSONB DEFAULT '{}',
    labels          JSONB DEFAULT '{}',
    status          VARCHAR(32) DEFAULT 'active',
    source          VARCHAR(64) DEFAULT 'manual',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entity_type ON entity(type_name);
CREATE INDEX IF NOT EXISTS idx_entity_name ON entity(name);
CREATE INDEX IF NOT EXISTS idx_entity_labels ON entity USING GIN(labels);

-- Relationship Type Definitions
CREATE TABLE IF NOT EXISTS relationship_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    end1_type       VARCHAR(128),
    end1_name       VARCHAR(128),
    end2_type       VARCHAR(128),
    end2_name       VARCHAR(128),
    description     TEXT
);

INSERT INTO relationship_type_def VALUES
    ('runs_on',      'Application', 'app',  'Host',       'host',  '应用运行在主机上'),
    ('Host_runs',    'Host',        'host', 'Application','app',   '主机运行应用'),
    ('depends_on',   'Service',     'service','Database',  'db',    '服务依赖数据库'),
    ('calls',        'Service',     'caller','Service',    'callee','服务调用服务')
ON CONFLICT (type_name) DO NOTHING;

-- Relationship Instances
CREATE TABLE IF NOT EXISTS relationship (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL REFERENCES relationship_type_def(type_name),
    end1_guid       UUID NOT NULL REFERENCES entity(guid),
    end2_guid       UUID NOT NULL REFERENCES entity(guid),
    attributes      JSONB DEFAULT '{}',
    source          VARCHAR(64) DEFAULT 'manual',
    confidence      FLOAT DEFAULT 1.0,
    is_active       BOOLEAN DEFAULT true,
    first_seen      TIMESTAMPTZ DEFAULT now(),
    last_seen       TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rel_type ON relationship(type_name);
CREATE INDEX IF NOT EXISTS idx_rel_end1 ON relationship(end1_guid);
CREATE INDEX IF NOT EXISTS idx_rel_end2 ON relationship(end2_guid);
CREATE INDEX IF NOT EXISTS idx_rel_active ON relationship(is_active) WHERE is_active = true;

-- Label Definitions
CREATE TABLE IF NOT EXISTS label_definition (
    label_key       VARCHAR(128) PRIMARY KEY,
    label_name      VARCHAR(256),
    value_type      VARCHAR(32) DEFAULT 'string',
    enum_values     JSONB,
    description     TEXT,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ DEFAULT now()
);

INSERT INTO label_definition (label_key, label_name, description) VALUES
    ('env',         '环境',         'production/staging/dev'),
    ('team',        '团队',         '负责团队'),
    ('business',    '业务线',       '业务归属'),
    ('region',      '地域',         '部署地域')
ON CONFLICT (label_key) DO NOTHING;
"""


def init_database():
    """Create CMDB database and initialize schema."""
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Check if database exists
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (CMDB_DB,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE {CMDB_DB}')
        print(f"✅ Database '{CMDB_DB}' created")
    else:
        print(f"ℹ️  Database '{CMDB_DB}' already exists")

    cur.close()
    conn.close()

    # Connect to CMDB database and run init SQL
    cmdb_config = {**DB_CONFIG, "dbname": CMDB_DB}
    conn = psycopg2.connect(**cmdb_config)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(INIT_SQL)
    cur.close()
    conn.close()
    print("✅ CMDB schema initialized")


if __name__ == "__main__":
    print("Initializing CMDB database...")
    init_database()
    print("Done!")
