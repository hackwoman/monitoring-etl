# Phase 3: Trace 关系自动发现 + 智能运维层

_计划日期：2026-04-01_
_分支：phase2/cognition-layer（延续）
_基于：Phase 2 完成的四维度实体认知 + 健康度引擎 + 前端三视图_

---

## 背景

Phase 2 已经完成：
- ✅ 实体四维度模型（身份/期望/观测/影响）
- ✅ entity_type_def.definition JSONB 收敛
- ✅ 健康度计算引擎（weighted_avg + children_avg）
- ✅ 前端三视图（Overview / Topology / Chat）
- ✅ Demo 数据工厂（含 Trace Span 模拟）

**当前差距：**
- Trace Span 数据已能写入 ClickHouse，但尚未自动发现关系写入 CMDB
- 前端 Chat 页面是静态 UI，未接入真正的 AI 问答
- 健康度引擎只读 ClickHouse 指标，未读 Trace 数据

---

## Step 1: Trace 关系自动发现引擎（Trace Discovery Engine）

### 目标
从 ClickHouse `traces.spans` 表自动提取服务调用关系，写入 CMDB `relationship` 表。

### 设计

#### 1.1 核心查询（已有 `query_service_topology()`）

```sql
SELECT
    p.service_name as caller,
    s.service_name as callee,
    count() as call_count,
    round(avg(s.duration_ms), 2) as avg_latency_ms,
    round(quantile(0.99)(s.duration_ms), 2) as p99_latency_ms,
    round(countIf(s.status_code = 'error') * 100.0 / count(), 2) as error_rate
FROM traces.spans p
INNER JOIN traces.spans s ON p.trace_id = s.trace_id AND s.parent_span_id = p.span_id
WHERE p.start_time > now() - INTERVAL {window_minutes} MINUTE
GROUP BY caller, callee
```

#### 1.2 融合策略

| 场景 | 动作 | confidence |
|------|------|-----------|
| CMDB 已有 + Trace 确认 | 更新 attributes（延迟/错误率），刷新 last_seen | 1.0 |
| CMDB 无 + Trace 发现 | 创建新关系，source=trace_discovered | 0.9 |
| CMDB 有 + Trace 超时未见 | 标记 is_active=false（需人工确认） | - |

#### 1.3 实现

**文件：`services/cmdb-api/app/services/trace_discovery.py`**

- `discover_relations(window_minutes=60)` → 从 ClickHouse 查询调用拓扑
- `merge_relation(caller, callee, stats)` → 与 CMDB 现有关系合并
- `run_discovery_once()` → 单次执行
- 定时循环（由 health-engine 或独立进程调用）

**API 端点：`POST /api/v1/cmdb/discover/trace`**

**自动注册为 CMDB 内部事件：发现新关系时写入 cmdb_event_log**

---

## Step 2: 健康度引擎集成 Trace 数据

### 目标
健康度计算不仅看 ClickHouse 指标，还看 Trace 的延迟/错误率。

### 改动

**文件：`services/health-engine/app/main.py`**

在 ClickHouse 查询阶段增加：
```python
# 查询 Trace 延迟/错误率
trace_sql = f"""
SELECT service_name, endpoint,
       round(avg(duration_ms), 2) as avg_latency,
       round(quantile(0.99)(duration_ms), 2) as p99_latency,
       round(countIf(status_code='error')*100.0/count(), 2) as error_rate
FROM traces.spans
WHERE start_time > now() - INTERVAL {window} MINUTE
GROUP BY service_name, endpoint
"""
```

**文件：`services/health-engine/app/calculator.py`**

在 `calculate_entity_health()` 中：
- 如果 entity.type_name == "Service"，优先用 Trace 数据填充 latency/error_rate 维度
- Trace 数据缺失时降级到 ClickHouse metrics

---

## Step 3: AI 问答接入（智能运维层基础版）

### 目标
Chat 页面接入真实的 AI 问答，支持自然语言查询实体状态。

### 设计

#### 3.1 后端：AI Chat API

**文件：`services/cmdb-api/app/routers/chat.py`**

```
POST /api/v1/chat
Body: { "message": "payment-service 的健康度怎么样？" }
Response: { "reply": "...", "data": {...}, "charts": [...] }
```

**实现方式（基础版）：关键词解析 + API 调用，不接 LLM**

解析规则：
- "XX 的健康度" → 查询实体 health_score
- "异常的实体" → 查询 health_level != healthy
- "有多少个 XX" → 按类型计数
- "XX 依赖什么" → 查询关系
- "最慢的服务" → 查询 Trace 延迟 TopN

#### 3.2 前端：Chat 页面对接 API

**文件：`frontend/src/pages/Chat.tsx`**

- 发送消息到 `/api/v1/chat`
- 展示回复 + 关联数据

---

## Step 4: 关系维度标注（双维度关系）

### 目标
relationship 表增加 `dimension` 字段，区分横向（调用链）和纵向（归属树）。

### 改动

```sql
ALTER TABLE relationship ADD COLUMN dimension VARCHAR(16) DEFAULT 'vertical';
```

**数据迁移：**
- `calls` / `depends_on` → dimension = 'horizontal'
- `includes` / `runs_on` / `hosts` → dimension = 'vertical'

**前端 Topology 视图增强：**
- 支持按维度切换视图
- 横向：调用链（Trace 驱动）
- 纵向：归属树（CMDB 驱动）

---

## Step 5: 部署验证

### 改动汇总

| 文件 | 改动 |
|------|------|
| `services/cmdb-api/app/services/trace_discovery.py` | 新建 - Trace 关系发现引擎 |
| `services/cmdb-api/app/routers/` | 新增 chat.py + discover.py |
| `services/health-engine/app/main.py` | 增加 Trace 数据查询 |
| `services/health-engine/app/calculator.py` | Trace 数据优先策略 |
| `frontend/src/pages/Chat.tsx` | 对接真实 API |
| `frontend/src/pages/Topology.tsx` | 双维度切换 |
| `storage/postgres/schema.sql` | dimension 字段 |

### 验证命令

```bash
# 1. 生成 Trace 数据
cd demo && python factory.py trace --count 200 --scenario slow_db

# 2. 触发关系发现
curl -X POST http://8.146.232.9:8001/api/v1/cmdb/discover/trace

# 3. 验证关系写入
curl http://8.146.232.9:8001/api/v1/cmdb/entities?source=trace_discovered

# 4. 验证健康度引擎读取 Trace
curl http://8.146.232.9:8001/api/v1/cmdb/entities/payment-service/cognition

# 5. 验证 AI 问答
curl -X POST http://8.146.232.9:8001/api/v1/chat -H "Content-Type: application/json" -d '{"message": "最慢的服务是什么？"}'

# 6. 前端验证
# 浏览器访问 http://8.146.232.9:3000 → Chat 页面测试
```

---

## 实施顺序

1. **Step 1** - Trace 关系发现引擎（核心）
2. **Step 2** - 健康度引擎集成 Trace 数据
3. **Step 3** - AI 问答基础版
4. **Step 4** - 关系维度标注
5. **Step 5** - 部署验证

---

## 预计工作量

- Step 1: ~2h（核心逻辑 + API + 融合策略）
- Step 2: ~1h（health-engine 改动）
- Step 3: ~2h（关键词解析 + 前端对接）
- Step 4: ~1h（SQL 迁移 + 前端切换）
- Step 5: ~1h（部署 + 验证）

总计：~7h

---

_计划完成，进入 Validate（编码实现）阶段_
