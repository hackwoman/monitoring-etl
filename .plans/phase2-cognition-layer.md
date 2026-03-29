# Phase 2: 认知层 (Cognition Layer)

_设计日期：2026-03-29_
_分支：phase2/cognition-layer_
_基于：博睿 ONE + 蓝鲸 CMDB 的融合设计_

---

## 设计原则

1. **一张实体表** — entity + relationship，不拆分
2. **一个定义表** — entity_type_def 的 JSONB 收敛属性/指标/关系/健康规则
3. **三个视图** — 总览 / 资源 / 问答
4. **四个维度** — 是什么 / 该关注什么 / 现在怎么样 / 影响多大

## 分步计划

### Step 1: 数据模型迁移 (Phase 2.1)

#### 1.1 entity_type_def 重构

**改动：**
- `super_types` (JSONB list) → `super_type` (单继承 string) + `category` + `icon`
- `attribute_defs` (JSONB) → 保留，但引入 `definition` JSONB 收敛一切
- 新增 `is_custom`, `version` 字段

**definition JSONB 结构：**
```json
{
  "attributes": [
    {"key": "port", "name": "端口", "type": "int", "required": true},
    {"key": "language", "name": "编程语言", "type": "string"}
  ],
  "templates": ["base_hardware"],
  "metrics": [
    {
      "name": "http.server.request.duration",
      "display": "HTTP 请求延迟",
      "type": "histogram",
      "unit": "ms",
      "thresholds": {"p99_warn": 500, "p99_crit": 2000},
      "dimensions": ["method", "route", "status_code"]
    }
  ],
  "relations": [
    {"type": "calls", "direction": "out", "target": "Service"},
    {"type": "depends_on", "direction": "out", "target": "Database"}
  ],
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name": "latency", "metric": "http.server.request.duration.p99", "weight": 0.4},
      {"name": "error_rate", "metric": "http.server.request.error_rate", "weight": 0.3},
      {"name": "saturation", "metric": "system.cpu.usage", "weight": 0.3}
    ]
  },
  "discovery": {
    "auto_match": ["service.name", "host.name"],
    "reconcile_priority": ["qualified_name", "attributes.sn", "name"]
  }
}
```

**迁移策略：** 
- 添加新列，不删除旧列（向后兼容）
- 写 Alembic 迁移脚本
- 预置数据通过 seed 脚本加载

#### 1.2 entity 表增强

**新增字段：**
```sql
ALTER TABLE entity ADD COLUMN expected_metrics JSONB DEFAULT '[]';
ALTER TABLE entity ADD COLUMN expected_relations JSONB DEFAULT '[]';
ALTER TABLE entity ADD COLUMN health_score INT;
ALTER TABLE entity ADD COLUMN health_level VARCHAR(16);
ALTER TABLE entity ADD COLUMN health_detail JSONB;
ALTER TABLE entity ADD COLUMN last_observed TIMESTAMPTZ;
ALTER TABLE entity ADD COLUMN biz_service VARCHAR(256);
ALTER TABLE entity ADD COLUMN risk_score INT;
ALTER TABLE entity ADD COLUMN propagation_hops INT;
ALTER TABLE entity ADD COLUMN blast_radius INT;
```

**新增索引：**
```sql
CREATE INDEX idx_entity_health ON entity(health_level) WHERE health_level IN ('warning', 'critical', 'down');
CREATE INDEX idx_entity_risk ON entity(risk_score DESC) WHERE risk_score > 50;
CREATE INDEX idx_entity_biz ON entity(biz_service) WHERE biz_service IS NOT NULL;
```

#### 1.3 attribute_template 表

```sql
CREATE TABLE attribute_template (
    template_name   VARCHAR(128) PRIMARY KEY,
    category        VARCHAR(64),
    attributes      JSONB NOT NULL,
    description     TEXT,
    is_builtin      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

预置 6 套模板：base_hardware, base_network, base_database, base_container, base_cloud, base_software

#### 1.4 预置 10 种内置类型

Business, Service, Host, Database, MySQL, PostgreSQL, Redis, NetworkDevice, K8sCluster, K8sPod

每种类型包含完整 definition。

#### 1.5 relationship 表

- 重命名列：end1_guid → from_guid, end2_guid → to_guid（语义更清晰）
- 移除外键到 relationship_type_def（允许动态关系类型）

---

### Step 2: CMDB API 扩展 (Phase 2.2)

#### 2.1 类型 API 增强
- `GET /api/v1/cmdb/types/{type_name}` — 获取单个类型的完整 definition
- `GET /api/v1/cmdb/types/{type_name}/metrics` — 获取该类型的指标模板
- `GET /api/v1/cmdb/types/{type_name}/health-model` — 获取健康模型
- `POST /api/v1/cmdb/types` — 创建自定义类型（支持 definition JSONB）

#### 2.2 实体 API 增强
- `GET /api/v1/cmdb/entities/{guid}/cognition` — 获取实体完整认知（4个维度）
- `GET /api/v1/cmdb/entities/{guid}/health` — 实体健康度
- `GET /api/v1/cmdb/entities?health_level=critical` — 按健康度筛选
- `GET /api/v1/cmdb/entities?sort=risk_score` — 按风险度排序

#### 2.3 属性模板 API
- `GET /api/v1/cmdb/attribute-templates` — 列表
- `GET /api/v1/cmdb/attribute-templates/{name}` — 详情

#### 2.4 总览 API (Overview)
- `GET /api/v1/overview` — 全局概览：健康度分布 + 告警统计 + 资源规模

---

### Step 3: 健康度 + 风险度引擎 (Phase 2.3)

#### 3.1 健康度计算服务
- 独立 Python 模块 `services/cognition/`
- 定时任务：每分钟刷新 entity_health
- 按 type_def.definition.health 计算
- 写入 entity.health_score / health_level / health_detail

#### 3.2 风险度计算
- 传播距离：通过 relationship 表 BFS 到用户端点
- 影响面：下游实体数量
- 业务权重：biz_service 的 business_weight

#### 3.3 数据质量检查（轻量版）
- 预置 10 条检查规则
- 定时扫描 → data_quality_snapshot
- 生成修正待办

---

### Step 4: 前端三视图 (Phase 2.4)

#### 4.1 总览页
- 业务健康度卡片
- 异常实体列表（按风险度排序）
- 资源规模统计

#### 4.2 资源页
- 按业务/类型/健康度分组
- 实体卡片（健康度仪表盘 + 关键指标 + 关系图）
- 属性模板管理

#### 4.3 问答页
- 自然语言输入
- AI 集成（后续 Phase 3 深化）

---

## Git 策略

- 分支: `phase2/cognition-layer`
- 每个 Step 完成后 commit + push
- commit 格式: `<tag>: <简短描述>`
- Step 完成后合并到 main

## 验证命令

```bash
# Step 1 验证
cd monitoring-etl
docker compose up -d postgres
python scripts/migrate_phase2.py  # 迁移
python scripts/seed_phase2.py     # 预置数据
# 验证: psql 查询 entity_type_def.definition 和 entity 新字段

# Step 2 验证
docker compose up -d cmdb-api
curl http://localhost:8001/api/v1/cmdb/types
curl http://localhost:8001/api/v1/cmdb/types/Service
curl http://localhost:8001/api/v1/cmdb/attribute-templates

# Step 3 验证
python -m services.cognition.health_engine --once  # 单次运行测试

# Step 4 验证
docker compose up -d
# 浏览器访问 http://localhost:3000
```
