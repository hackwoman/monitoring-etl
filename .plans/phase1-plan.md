# Phase 1 实施计划：日志采集 + 基础 CMDB + 查询

_计划日期：2026-03-28_
_预计周期：4-6 周_
_前置条件：架构设计文档 `.plans/etl-architecture-design.md` 已完成_

---

## 1. Phase 1 目标

交付一个可运行的最小可用版本：
- ✅ 主机日志采集（OTel Collector）
- ✅ 日志解析 + 写入 ClickHouse（Vector ETL）
- ✅ 基础 CMDB 实体管理（PostgreSQL）
- ✅ 日志搜索 API（FastAPI）
- ✅ 基础前端（日志查询 + CMDB 实体列表）
- ✅ Docker Compose 一键部署

**不包含（Phase 2/3）：** Trace 融合、Prometheus、告警、AI 诊断、风险度引擎

---

## 2. 模块拆分与任务清单

### 模块 1：项目脚手架

- [ ] 创建 monorepo 目录结构
- [ ] 配置 Python 项目（pyproject.toml / requirements）
- [ ] 配置前端项目（React + Vite）
- [ ] Docker Compose 基础编排
- [ ] CI 基础配置（lint + test）

### 模块 2：OTel Collector 日志采集

- [ ] 编写 Collector 配置（filelog receiver + otlphttp exporter）
- [ ] 支持多行日志合并（Java stacktrace 等）
- [ ] 自动注入 resource 属性（host.name, service.name）
- [ ] systemd 部署脚本（裸机）
- [ ] DaemonSet 配置（K8s，可选）

### 模块 3：Vector ETL 管道

- [ ] OTel source 接收配置
- [ ] 日志解析 Transform（JSON + Grok fallback）
- [ ] 实体提取 Transform（从日志识别 service/host）
- [ ] CMDB 关联 Transform（HTTP 调 CMDB API）
- [ ] ClickHouse sink 配置
- [ ] 磁盘 buffer 配置（数据可靠性）

### 模块 4：PostgreSQL CMDB 核心

- [ ] entity_type_def 表 + 预置类型
- [ ] entity 表
- [ ] relationship_type_def 表 + 预置关系
- [ ] relationship 表
- [ ] label_definition 表
- [ ] 基础 CRUD SQL

### 模块 5：ClickHouse 日志存储

- [ ] log_entries 表设计（MergeTree + TTL）
- [ ] 常用查询索引设计
- [ ] 数据完整性追踪表

### 模块 6：FastAPI 服务

- [ ] CMDB API（实体 CRUD、关系查询、类型管理）
- [ ] 日志 API（搜索、聚合、时间范围查询）
- [ ] 健康检查 / 元监控 endpoint
- [ ] 多租户中间件（基础版：标签过滤）
- [ ] API 文档自动生成

### 模块 7：前端基础

- [ ] 日志查询页面（搜索框 + 时间选择 + 表格 + JSON 展开）
- [ ] CMDB 实体列表 + 详情页
- [ ] 基础布局和导航

### 模块 8：部署与集成

- [ ] Docker Compose 完整编排
- [ ] 一键启动脚本
- [ ] 健康检查和等待逻辑
- [ ] 示例数据和 demo 场景

---

## 3. 目录结构

```
monitoring-etl/
├── docker-compose.yml
├── .env
├── README.md
│
├── services/
│   ├── cmdb-api/               # CMDB 服务
│   │   ├── app/
│   │   │   ├── main.py         # FastAPI 入口
│   │   │   ├── models/         # SQLAlchemy 模型
│   │   │   ├── routers/        # API 路由
│   │   │   ├── services/       # 业务逻辑
│   │   │   └── database.py     # DB 连接
│   │   ├── migrations/         # Alembic 迁移
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── log-api/                # 日志查询服务
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   ├── services/
│   │   │   └── clickhouse.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── api-gateway/            # API 网关（聚合层）
│       ├── app/
│       │   ├── main.py
│       │   └── middleware/      # 认证、租户过滤
│       ├── Dockerfile
│       └── requirements.txt
│
├── pipeline/
│   ├── otel-collector/
│   │   └── config.yaml         # OTel Collector 配置
│   └── vector/
│       └── vector.toml          # Vector ETL 配置
│
├── storage/
│   ├── postgres/
│   │   └── init.sql             # CMDB 表初始化
│   └── clickhouse/
│       └── init.sql             # 日志表初始化
│
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Logs.tsx         # 日志查询
│   │   │   └── Cmdb.tsx         # CMDB 管理
│   │   ├── components/
│   │   ├── api/                 # API 调用
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
│
├── deploy/
│   ├── agent/
│   │   ├── install.sh           # Agent 安装脚本
│   │   └── otel-agent.service   # systemd 服务
│   └── demo/
│       └── sample-app/          # 演示用应用
│
└── .plans/
    ├── etl-architecture-design.md
    └── phase1-plan.md           # 本文件
```

---

## 4. 核心表设计（Phase 1 范围）

### CMDB 表（PostgreSQL）

```sql
-- 实体类型定义
CREATE TABLE entity_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    super_types     JSONB DEFAULT '[]',
    attribute_defs  JSONB DEFAULT '{}',
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 预置类型
INSERT INTO entity_type_def (type_name, description) VALUES
    ('Host',        '物理机/虚拟机/云主机'),
    ('Service',     '微服务'),
    ('Application', '应用实例'),
    ('Database',    '数据库实例'),
    ('Middleware',  '中间件'),
    ('IP',          'IP 地址');

-- 实体实例
CREATE TABLE entity (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL REFERENCES entity_type_def(type_name),
    name            VARCHAR(512) NOT NULL,
    qualified_name  VARCHAR(1024) UNIQUE NOT NULL,
    attributes      JSONB DEFAULT '{}',
    labels          JSONB DEFAULT '{}',       -- 自定义标签
    status          VARCHAR(32) DEFAULT 'active',
    source          VARCHAR(64) DEFAULT 'manual',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_entity_type ON entity(type_name);
CREATE INDEX idx_entity_labels ON entity USING GIN(labels);

-- 关系类型定义
CREATE TABLE relationship_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    end1_type       VARCHAR(128),
    end1_name       VARCHAR(128),
    end2_type       VARCHAR(128),
    end2_name       VARCHAR(128),
    description     TEXT
);

INSERT INTO relationship_type_def VALUES
    ('runs_on',      'Application', 'app',  'Host',       'host', '应用运行在主机上'),
    ('Host_runs',    'Host',        'host', 'Application','app',  '主机运行应用'),
    ('depends_on',   'Service',     'service','Database',  'db',   '服务依赖数据库'),
    ('calls',        'Service',     'caller','Service',    'callee','服务调用服务');

-- 关系实例
CREATE TABLE relationship (
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

CREATE INDEX idx_rel_type ON relationship(type_name);
CREATE INDEX idx_rel_end1 ON relationship(end1_guid);
CREATE INDEX idx_rel_end2 ON relationship(end2_guid);

-- 标签定义
CREATE TABLE label_definition (
    label_key       VARCHAR(128) PRIMARY KEY,
    label_name      VARCHAR(256),
    value_type      VARCHAR(32) DEFAULT 'string',
    enum_values     JSONB,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### 日志表（ClickHouse）

```sql
CREATE TABLE IF NOT EXISTS logs.log_entries
(
    -- 时间
    timestamp       DateTime64(3, 'UTC'),
    ingest_time     DateTime64(3, 'UTC') DEFAULT now64(3),
    
    -- 来源
    source          LowCardinality(String) DEFAULT 'otel',
    agent_id        String DEFAULT '',
    
    -- 实体
    service_name    LowCardinality(String) DEFAULT 'unknown',
    host_name       LowCardinality(String) DEFAULT 'unknown',
    
    -- 日志内容
    level           LowCardinality(String) DEFAULT 'info',
    message         String,
    body            String DEFAULT '',
    
    -- 结构化字段（解析后的 JSON）
    attributes      Map(String, String) DEFAULT map(),
    
    -- Trace 关联（Phase 2 才有值）
    trace_id        String DEFAULT '',
    span_id         String DEFAULT '',
    
    -- 标签
    labels          Map(String, String) DEFAULT map(),
    
    -- 时效标记
    timeliness      Enum8('hot'=1, 'warm'=2, 'cool'=3, 'cold'=4) DEFAULT 'hot',
    delay_seconds   UInt32 DEFAULT 0
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (service_name, host_name, level, timestamp)
TTL timestamp + INTERVAL 30 DAY DELETE
SETTINGS index_granularity = 8192;

-- 常用查询索引
ALTER TABLE logs.log_entries ADD INDEX idx_level level TYPE set(20) GRANULARITY 4;
ALTER TABLE logs.log_entries ADD INDEX idx_message message TYPE tokenbf_v1(30720, 2, 0) GRANULARITY 1;
```

### 数据完整性追踪

```sql
CREATE TABLE IF NOT EXISTS logs.data_completeness
(
    source_id       String,
    time_bucket     DateTime,
    expected_count  UInt64 DEFAULT 0,
    actual_count    UInt64 DEFAULT 0,
    first_event     Nullable(DateTime64(3, 'UTC')),
    last_event      Nullable(DateTime64(3, 'UTC')),
    gap_seconds     UInt32 DEFAULT 0,
    status          Enum8('complete'=1, 'partial'=2, 'gap_detected'=3) DEFAULT 'complete',
    updated_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree()
ORDER BY (source_id, time_bucket);
```

---

## 5. API 设计（Phase 1）

### CMDB API

```
POST   /api/v1/cmdb/entities              创建实体
GET    /api/v1/cmdb/entities              列表（支持 type/label 过滤）
GET    /api/v1/cmdb/entities/:id          详情
PUT    /api/v1/cmdb/entities/:id          更新
DELETE /api/v1/cmdb/entities/:id          删除

POST   /api/v1/cmdb/entities/:id/relations    创建关系
GET    /api/v1/cmdb/entities/:id/relations    查询关系

GET    /api/v1/cmdb/types                 类型列表
POST   /api/v1/cmdb/types                 注册新类型

POST   /api/v1/cmdb/enrich                日志实体关联（Vector 调用）
POST   /api/v1/cmdb/heartbeat             实体心跳（Agent 调用）
```

### 日志 API

```
POST   /api/v1/logs/search                日志搜索（全文 + 条件）
POST   /api/v1/logs/query                 SQL 查询（高级用户）
GET    /api/v1/logs/aggregation           聚合统计（按时间/服务/级别）
GET    /api/v1/logs/completeness          数据完整性查询
```

### 系统 API

```
GET    /api/v1/health                     健康检查
GET    /api/v1/metrics                    Prometheus 格式指标
```

---

## 6. 前端页面（Phase 1）

### 页面 1：日志查询

```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 日志查询                                                  │
├─────────────────────────────────────────────────────────────┤
│ 查询: [________________________] [搜索]                      │
│ 时间: [最近1小时 ▼] 服务: [全部 ▼]  级别: [全部 ▼]           │
├─────────────────────────────────────────────────────────────┤
│ 时间               │ 服务      │ 级别  │ 日志内容            │
│ 10:23:45.123      │ payment   │ ERROR │ ConnectionTimeout... │
│ 10:23:44.891      │ order     │ WARN  │ Slow query: 1200ms   │
│ 10:23:44.502      │ payment   │ INFO  │ Request completed    │
│ ...                                                          │
└─────────────────────────────────────────────────────────────┘
```

### 页面 2：CMDB 管理

```
┌─────────────────────────────────────────────────────────────┐
│ 📦 CMDB 实体管理                                             │
├─────────────────────────────────────────────────────────────┤
│ 类型: [全部 ▼]  搜索: [____________] [+ 新建实体]            │
├─────────────────────────────────────────────────────────────┤
│ 名称              │ 类型      │ 状态  │ 关系数 │ 标签        │
│ payment-service   │ Service   │ ✅    │ 3      │ env:prod    │
│ order-service     │ Service   │ ✅    │ 5      │ env:prod    │
│ db-master-01      │ Database  │ ✅    │ 2      │ env:prod    │
│ host-001          │ Host      │ ✅    │ 4      │ region:cn   │
│ ...                                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 部署架构（Phase 1）

```yaml
# docker-compose.yml 核心服务
services:
  postgres:          # CMDB 核心
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]
    ports: ["5432:5432"]

  clickhouse:        # 日志存储
    image: clickhouse/clickhouse-server:latest
    volumes: [chdata:/var/lib/clickhouse]
    ports: ["8123:8123", "9000:9000"]

  vector:            # ETL 管道
    image: timberio/vector:latest-alpine
    volumes: [./pipeline/vector/vector.toml:/etc/vector/vector.toml]
    ports: ["4317:4317", "4318:4318"]

  cmdb-api:          # CMDB 服务
    build: ./services/cmdb-api
    depends_on: [postgres]
    ports: ["8001:8000"]

  log-api:           # 日志查询服务
    build: ./services/log-api
    depends_on: [clickhouse]
    ports: ["8002:8000"]

  api-gateway:       # API 网关
    build: ./services/api-gateway
    depends_on: [cmdb-api, log-api]
    ports: ["8000:8000"]

  frontend:          # 前端
    build: ./frontend
    depends_on: [api-gateway]
    ports: ["3000:80"]
```

**启动流程：**
```bash
git clone <repo>
cd monitoring-etl
docker compose up -d
# 等待所有服务就绪
./scripts/health-check.sh
# 访问 http://localhost:3000
```

---

## 8. 开发顺序

```
Week 1: 项目脚手架 + Docker Compose + DB 初始化
Week 2: CMDB API + 实体 CRUD + ClickHouse 表
Week 3: Vector ETL 管道 + 日志解析
Week 4: 日志搜索 API + Agent 部署脚本
Week 5: 前端页面（日志查询 + CMDB）
Week 6: 集成测试 + 文档 + Demo
```

---

## 9. 验证标准

### 单元测试
- [ ] CMDB CRUD 正常
- [ ] 日志查询返回正确结果
- [ ] 标签过滤生效

### 集成测试
- [ ] docker compose up 一键启动全部服务
- [ ] Agent 采集日志 → Vector 解析 → ClickHouse 存储 → API 查询 → 前端展示 全链路通
- [ ] 断网恢复后数据不丢

### 性能基线
- [ ] 单机 Agent CPU < 5%, 内存 < 200MB
- [ ] Vector 吞吐 > 10K logs/s
- [ ] 日志查询 P99 < 3s (最近 1 小时)

---

_Plan 阶段完成，待主人确认后进入 Validate（编码实现）_
