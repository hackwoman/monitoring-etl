# CMDB 关系模型设计 — 双维度关系

## 问题诊断

现有关系模型是**扁平的**，所有关系混在一个 `relationship` 表里：
- `includes`（业务→服务）— 纵向归属
- `calls`（服务→服务）— 横向调用
- `depends_on`（服务→DB）— 既有横向也有纵向
- `runs_on`（服务→主机）— 纵向归属

问题：没有区分关系的**语义维度**，导致：
1. 无法独立展示"调用链"（横向）和"归属树"（纵向）
2. 前端无法实现"先看横向调用链定位问题节点，再纵向展开看底层资源"
3. 健康度级联计算逻辑混乱（横向级联 vs 纵向聚合不分）

## 核心概念：双维度关系

```
                    横向维度（Flow / 调用链）
                    ┌─────────────────────────────┐
                    │  Business                    │
                    │    ↓ includes                │
                    │  [gateway] ──calls──→ [order-svc] ──calls──→ [payment-svc]
                    │                                  │                    │
                    │                              depends_on          depends_on
                    │                                  ↓                    ↓
                    │                              [order-db]         [payment-db]
                    └─────────────────────────────┘

纵向维度（Composition / 归属树）
┌─────────────────────────────────────────────────┐
│                                                  │
│  [在线支付] Business                              │
│    ├── includes → [gateway] Service              │
│    │               ├── runs_on → [web-01] Host   │
│    │               │              ├── os, cpu, mem│
│    │               │              └── connected_to→ [交换机]
│    │               └── endpoints: POST /api/order │
│    │                                             │
│    ├── includes → [payment-service] Service      │
│    │               ├── runs_on → [app-02] Host   │
│    │               └── depends_on → [payment-db] │
│    │                               └── runs_on → [db-master] Host
│    └── ...                                        │
└─────────────────────────────────────────────────┘
```

### 横向维度（Horizontal / Flow）

**定义**：一次业务请求从入口到终点的完整路径，由 trace 数据驱动。

**关系类型**：
- `calls`：服务→服务的同步调用（从 trace span 父子关系提取）
- `async_calls`：异步调用（MQ、事件）
- `depends_on`：服务→中间件的数据依赖（DB、Cache、MQ）

**数据来源**：
- 主要来自 trace（OpenTelemetry span 的 parent-child 关系自动发现）
- 可以从 CMDB 手动补充

**特征**：
- 有方向（A→B）
- 有 endpoint 粒度（不仅是服务，可以到接口：`POST /api/order`）
- 有频率/延迟/错误率等运行时指标
- 动态变化（新接口上线自动发现）

### 纵向维度（Vertical / Composition）

**定义**：一个对象的"构成"和"承载"关系，从上到下逐层展开。

**关系类型**：
- `includes`：业务→服务（业务包含哪些服务）
- `runs_on`：服务/DB → 主机（运行在哪里）
- `hosts`：主机→服务（反向）
- `contains`：集群→Pod / 机架→主机
- `connected_to`：主机→网络设备

**数据来源**：
- CMDB 手动录入 / 自动发现
- 相对静态（基础设施变化频率低）

**特征**：
- 有方向（上→下，从逻辑到物理）
- 形成树状层级：Business → Service → Host → NetworkDevice
- 用于故障下钻："服务有问题" → 点击 → "看底层主机的 CPU/内存/磁盘"

## 模型调整方案

### 1. relationship 表增加 `dimension` 字段

```sql
ALTER TABLE relationship ADD COLUMN dimension VARCHAR(16) DEFAULT 'vertical';
-- 'horizontal' = 横向调用链
-- 'vertical'   = 纵向归属树
```

### 2. entity 表增加 `layer` 字段（层级标识）

```sql
ALTER TABLE entity ADD COLUMN layer VARCHAR(32);
-- 'business'       = 业务层
-- 'application'    = 应用层（服务、接口）
-- 'middleware'     = 中间件层（DB、Cache、MQ）
-- 'infrastructure' = 基础设施层（主机、网络、存储）
```

对应现有 entity_type_def 的 category 字段，但更明确。

### 3. entity_type_def.definition 增加维度标注

在每个类型定义的 `relations` 中标注维度：

```json
{
  "relations": [
    {"type": "calls", "target": "Service", "direction": "out", "dimension": "horizontal"},
    {"type": "depends_on", "target": "Database", "direction": "out", "dimension": "horizontal"},
    {"type": "runs_on", "target": "Host", "direction": "out", "dimension": "vertical"}
  ]
}
```

### 4. 横向关系自动发现（从 Trace）

```sql
-- 从 trace span 自动提取横向调用关系
SELECT
    p.service_name as caller,
    s.service_name as callee,
    p.endpoint as caller_endpoint,
    s.endpoint as callee_endpoint,
    count() as call_count,
    round(avg(s.duration_ms), 2) as avg_latency_ms,
    round(quantile(0.99)(s.duration_ms), 2) as p99_latency_ms,
    round(countIf(s.status_code = 'error') * 100.0 / count(), 2) as error_rate
FROM traces.spans p
INNER JOIN traces.spans s
    ON p.trace_id = s.trace_id AND s.parent_span_id = p.span_id
WHERE p.service_name != s.service_name
GROUP BY caller, callee, caller_endpoint, callee_endpoint
ORDER BY call_count DESC
```

这个查询的结果直接生成 `calls` 关系并写入 relationship 表（dimension='horizontal'）。

### 5. 新增接口级实体（Endpoint）

横向维度可以细化到接口级别：

```sql
-- entity_type_def 中已有 Endpoint 定义
-- 接口实体示例：
-- type_name: Endpoint, name: POST /api/order
-- attributes: { method: POST, path: /api/order, service: gateway }
-- 关系: gateway --has_endpoint--> POST /api/order (vertical)
--       POST /api/order --calls--> POST /order/create (horizontal, 从 trace 发现)
```

## 场景实现：横向+纵向结合的可观测性

### 场景 1：从横向调用链定位问题，纵向下钻找根因

```
用户看到：
1. [横向] "在线支付" 业务调用链视图
   gateway → order-service → payment-service → payment-db
   发现 payment-service 延迟 931ms，错误率 10.36% 🔴

2. 点击 payment-service → [纵向] 展开该服务的归属树
   payment-service
     ├── runs_on: app-02 (Host)
     │     ├── cpu: 65% ⚠️
     │     ├── memory: 45% ✅
     │     └── connected_to: 核心交换机-01 ✅
     ├── depends_on: payment-db (MySQL)
     │     └── runs_on: db-master (Host)
     │           ├── cpu: 90% 🔴 ← 根因！
     │           └── disk_io: 85% 🔴
     └── has_endpoint:
           POST /pay/process (error_rate: 15%) 🔴
           GET /pay/status (error_rate: 2%) ⚠️

3. 结论：payment-service 问题根因是 db-master CPU 打满
```

### 场景 2：健康度级联计算（双维度）

**横向级联**：调用链上游受影响
```
payment-db 慢 → payment-service 超时 → order-service 重试失败 → gateway 返回 500
```
横向级联基于 `calls` / `depends_on` 关系，按调用链方向传播。

**纵向聚合**：父对象健康度 = 子对象加权聚合
```
Business.health = avg(Service.health)    [children_avg]
Host.health = weighted_avg(cpu, memory, disk, io)
Service.health = weighted_avg(latency, error_rate, saturation)
```
纵向聚合基于 `runs_on` / `includes` / `contains` 关系，自底向上聚合。

## API 设计

### 横向：调用链 API

```
GET /api/v1/cmdb/topology/flow?business=在线支付
→ 返回该业务的完整调用链（从 trace 自动发现 + CMDB 补充）

GET /api/v1/cmdb/topology/flow?trace_id=xxx
→ 返回某条 trace 的完整 span 树
```

### 纵向：归属树 API

```
GET /api/v1/cmdb/topology/tree?entity_guid=xxx
→ 返回该实体的纵向归属树（向下展开所有 runs_on / contains / connected_to）

GET /api/v1/cmdb/topology/tree?entity_guid=xxx&depth=3
→ 限制展开深度
```

### 结合：问题定位 API

```
GET /api/v1/cmdb/topology/impact?entity_guid=xxx
→ 横向：该实体故障会影响哪些上游（反向追溯 calls）
→ 纵向：该实体的底层资源健康状况
```

## 现有数据映射

| 关系 | 当前 | 维度 | 说明 |
|------|------|------|------|
| includes | Business → Service | vertical | 业务包含服务 |
| calls | Service → Service | horizontal | 服务间调用 |
| depends_on | Service → DB/Cache | horizontal* | 数据依赖 |
| runs_on | Service/DB → Host | vertical | 运行在哪台机器 |
| hosts | Host → Service | vertical | 反向，主机承载 |
| connected_to | Host → NetworkDevice | vertical | 网络连接 |
| has_endpoint | Service → Endpoint | vertical | 服务暴露的接口 |

*depends_on 可以是横向（调用链的一部分）也可以是纵向（依赖关系的归属）
