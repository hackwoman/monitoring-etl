# 拓扑视图重构设计 — 三类型拓扑 + 下钻关联分析

_设计日期：2026-04-01_
_参考：bonree 全局拓扑形态 + 主人需求_

---

## 1. 设计理念

**核心思路：三种拓扑视图，一个入口，下钻关联。**

```
用户看到的拓扑页面
┌─────────────────────────────────────────────────────────┐
│  [调用拓扑]  [基础设施拓扑]  [全局拓扑]                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  默认展示：全局拓扑（混合视图）                            │
│  - 东西横向：服务调用链（Trace 驱动）                      │
│  - 南北纵向：业务→服务→主机→网络设备                      │
│                                                         │
│  点击任意实体 → 右侧弹出详情面板                          │
│  ├─ 实时指标                                            │
│  ├─ 告警/事件                                           │
│  ├─ 纵向下钻拓扑（该实体的完整归属树）                     │
│  └─ 相关 Trace                                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 三种拓扑的区别

| 视图 | 维度 | 关系类型 | 数据来源 | 展示内容 |
|------|------|---------|---------|---------|
| **A. 调用拓扑** | 横向 | calls, depends_on | Trace Span | 服务间调用链，延迟/错误率标注 |
| **B. 基础设施拓扑** | 纵向 | runs_on, hosts, connected_to | CMDB | 网络设备→主机→服务的物理连接 |
| **C. 全局拓扑** | 混合 | 全部 | CMDB + Trace | 业务→服务→DB 的完整链路，点击下钻 |

---

## 2. 视图 A：调用拓扑（APM 东西横向）

### 2.1 展示形式

```
                    ┌─────────┐
                    │ gateway │  P99: 15ms · ✅
                    └────┬────┘
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼─────┐  ┌─────▼─────┐  ┌────▼──────┐
    │ order-svc │  │ payment-svc│  │ inventory │  P99: 35ms · ✅
    │ P99: 120ms│  │ P99: 450ms │  │           │
    │ ⚠️ warning│  │ 🔴 critical│  └─────┬─────┘
    └─────┬─────┘  └─────┬─────┘        │
          │              │              │
    ┌─────▼─────┐  ┌─────▼─────┐  ┌────▼──────┐
    │ order-db  │  │ payment-db │  │ order-db  │
    │ P99: 3ms  │  │ P99: 450ms │  │           │
    │ ✅        │  │ 🔴 root!   │  └───────────┘
    └───────────┘  └───────────┘

    边的粗细 = 调用量(QPS)
    边的颜色 = 错误率(绿→黄→红)
    节点大小 = 被调用次数
    节点颜色 = 健康度
```

### 2.2 关键特性

- **边的粗细**：按 QPS 分 3 档（<100 细 / 100-1000 中 / >1000 粗）
- **边的颜色**：错误率渐变（0% 绿 → 5% 黄 → 10%+ 红）
- **边的标签**：hover 显示 P99 延迟 + 调用次数 + 错误率
- **节点动画**：异常节点脉冲闪烁
- **根因高亮**：health-engine 检测到的根因节点加红色边框
- **自动布局**：Dagre 分层布局（从左到右或从上到下）

### 2.3 数据来源

```sql
-- 从 Trace 数据提取调用拓扑（已有 query_service_topology）
SELECT p.service_name as caller, s.service_name as callee,
       count() as qps,
       round(avg(s.duration_ms), 2) as avg_latency,
       round(quantile(0.99)(s.duration_ms), 2) as p99_latency,
       round(countIf(s.status_code='error')*100.0/count(), 2) as error_rate
FROM traces.spans p
INNER JOIN traces.spans s ON p.trace_id=s.trace_id AND s.parent_span_id=p.span_id
WHERE p.start_time > now() - INTERVAL 15 MINUTE
GROUP BY caller, callee
```

---

## 3. 视图 B：基础设施拓扑（物理连接）

### 3.1 展示形式

```
    ┌──────────────────┐
    │  核心交换机-01    │  ✅
    │  Cisco C9300     │
    └────────┬─────────┘
     ┌───────┼───────┬───────────┐
     │       │       │           │
┌────▼──┐┌───▼──┐┌───▼───┐┌─────▼────┐
│web-01 ││web-02││app-01 ││ db-master │  ✅
│8C 32G ││8C 32G││16C 64G││ 32C 128G │
│CPU:45%││CPU:30││CPU:65%││ CPU:90%  │
│MEM:60%││MEM:40││MEM:55%││ MEM:70%  │
└───┬───┘└──────┘└───┬───┘└────┬────┘
    │                │         │
┌───▼───┐      ┌─────▼─────┐  │
│gateway│      │order-svc  │  │  ← 上层实体（悬停显示）
│:80    │      │:8081      │  │
└───────┘      └───────────┘  │
                          ┌───▼────┐
                          │payment │
                          │  -db   │
                          └────────┘
```

### 3.2 关键特性

- **分层展示**：网络设备层 → 主机层 → 服务/DB 层
- **节点信息**：每个主机显示 CPU/内存/磁盘实时指标（从 ClickHouse 查询）
- **连线含义**：物理连接（网线、VLAN）
- **异常高亮**：主机指标超阈值时节点变红
- **点击下钻**：点击主机 → 查看该主机上运行的所有服务和数据库

### 3.3 数据来源

```sql
-- 从 CMDB 获取基础设施实体和关系
SELECT e1.name as from_name, e1.type_name as from_type,
       r.type_name, 
       e2.name as to_name, e2.type_name as to_type
FROM relationship r
JOIN entity e1 ON r.from_guid = e1.guid
JOIN entity e2 ON r.to_guid = e2.guid
WHERE r.type_name IN ('runs_on', 'hosts', 'connected_to')
  AND r.is_active = true
```

---

## 4. 视图 C：全局拓扑（混合视图）⭐ 核心

### 4.1 设计理念

**参考 bonree 全局拓扑：默认展示"业务视角"的完整链路，点击任意实体进行纵向下钻。**

```
全局拓扑 = 横向调用链（东西向）+ 纵向归属树（南北向）的混合

顶层：Business（业务）
  │
  ├── 横向展开：业务包含的服务之间的调用关系
  │
  └── 点击任意实体 → 纵向下钻：
      ├─ 该实体的完整归属树（runs_on → Host → Network）
      ├─ 实时指标面板
      ├─ 告警/事件列表
      └─ 相关 Trace
```

### 4.2 展示形式

```
┌─────────────────────────────────────────────────────────────────┐
│ 🗺️ 全局拓扑 — 在线支付                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐     calls      ┌──────────┐     calls             │
│  │ gateway ├───────────────→│ order-svc├──────────┐            │
│  │ P99:15ms│                │ P99:120ms│          │            │
│  │ ✅      │                │ ⚠️       │          ↓            │
│  └────┬────┘                └─────┬────┘    ┌─────────┐        │
│       │                           │         │inventory│        │
│       │ calls                     │         │  -svc   │        │
│       ↓                           │         │ ✅      │        │
│  ┌──────────┐                     │         └────┬────┘        │
│  │payment   │←────────────────────┘              │             │
│  │  -svc    │  calls               depends_on    │             │
│  │ P99:450ms│                                    │             │
│  │ 🔴 root! ├──────┐               ┌─────────────┘             │
│  └──────────┘      ↓               ↓                           │
│              ┌──────────┐   ┌──────────┐                       │
│              │payment-db│   │ order-db │                       │
│              │ P99:450ms│   │ P99:3ms  │                       │
│              │ 🔴 root! │   │ ✅       │                       │
│              └──────────┘   └──────────┘                       │
│                                                                 │
│  [点击 payment-service 查看下钻详情 →]                          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ 侧边详情面板（点击实体后展开）                                     │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ payment-service                                     [X]  │   │
│ │ 类型: Service · 健康度: 55/100 🔴 · 风险度: 85            │   │
│ ├──────────────────────────────────────────────────────────┤   │
│ │ 📊 指标     │ 🔔 告警     │ 🌲 下钻拓扑     │ 🔗 Trace   │   │
│ ├──────────────────────────────────────────────────────────┤   │
│ │                                                          │   │
│ │ 🌲 纵向下钻拓扑:                                          │   │
│ │                                                          │   │
│ │   payment-service                                        │   │
│ │   ├── runs_on → app-02 (Host)                            │   │
│ │   │   ├── CPU: 65% ⚠️                                    │   │
│ │   │   ├── MEM: 55% ✅                                    │   │
│ │   │   ├── DISK: 40% ✅                                   │   │
│ │   │   └── connected_to → 核心交换机-01 ✅                 │   │
│ │   ├── depends_on → payment-db (MySQL)                    │   │
│ │   │   └── runs_on → db-master (Host)                     │   │
│ │   │       ├── CPU: 90% 🔴 ← 根因！                       │   │
│ │   │       ├── MEM: 70% ⚠️                                │   │
│ │   │       └── connected_to → 核心交换机-01 ✅             │   │
│ │   ├── depends_on → user-cache (Redis)                    │   │
│ │   │   └── runs_on → redis-01 (Host)                      │   │
│ │   │       ├── CPU: 20% ✅                                │   │
│ │   │       └── MEM: 85% ⚠️                                │   │
│ │   └── has_endpoint → POST /pay/process                   │   │
│ │       └── error_rate: 15% 🔴                             │   │
│ │                                                          │   │
│ └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 全局拓扑的布局策略

```
布局算法：分层 + 力导向混合

第一层（顶层）：按业务分组
  Business: 在线支付, 用户注册

第二层（业务内部）：横向调用链
  按 Trace 调用链排列（从左到右）
  gateway → order-svc → payment-svc → DB

第三层（点击下钻）：纵向归属树
  Service → Host → NetworkDevice
  Service → Database → Host
```

### 4.4 侧边详情面板（四 Tab 设计）

| Tab | 内容 | 数据来源 |
|-----|------|---------|
| **📊 指标** | 关键指标趋势图（延迟/错误率/CPU/内存） | ClickHouse traces.spans + logs |
| **🔔 告警** | 该实体的活跃告警和历史事件 | 告警表（Phase 4）|
| **🌲 下钻拓扑** | 该实体的纵向归属树（runs_on → Host → Network） | CMDB relationship |
| **🔗 Trace** | 相关 Trace 列表（最近的调用链） | ClickHouse traces.spans |

---

## 5. 下钻逻辑设计

### 5.1 下钻触发

```
用户点击全局拓扑中的任意实体节点
  │
  ▼
右侧面板弹出
  │
  ├── Tab 1: 指标 → 自动查询 ClickHouse
  │   ├── 延迟趋势（15min / 1h / 24h）
  │   ├── 错误率趋势
  │   ├── 主机 CPU/内存（如果是服务）
  │   └── 数据库连接数/慢查询（如果是 DB）
  │
  ├── Tab 2: 告警 → 查询告警表
  │   ├── 活跃告警（status=firing）
  │   └── 历史告警（最近 24h）
  │
  ├── Tab 3: 下钻拓扑 → 递归查询 CMDB
  │   ├── 从当前实体出发，沿 runs_on / depends_on / includes 向下展开
  │   ├── 每个节点显示健康度和关键指标
  │   └── 最多展开 3 层，避免图过大
  │
  └── Tab 4: Trace → 查询 ClickHouse
      ├── 最近 10 条经过该服务的 Trace
      └── 点击可展开完整调用链
```

### 5.2 纵向下钻拓扑的查询逻辑

```python
# 从当前实体出发，递归查询纵向关系
def get_drill_down_topology(entity_guid: str, max_depth: int = 3):
    """
    纵向下钻：沿 runs_on / depends_on / includes 向下展开。
    
    示例：从 payment-service 出发
    → payment-service
       ├── runs_on → app-02 (Host) [指标: cpu=65%, mem=55%]
       │   └── connected_to → 核心交换机-01 [状态: ok]
       ├── depends_on → payment-db (MySQL) [健康度: 55]
       │   └── runs_on → db-master (Host) [指标: cpu=90%, mem=70%] ← 根因
       └── depends_on → user-cache (Redis) [健康度: 80]
           └── runs_on → redis-01 (Host) [指标: cpu=20%, mem=85%]
    """
    visited = set()
    tree = []
    
    def _expand(guid, depth):
        if depth > max_depth or guid in visited:
            return None
        visited.add(guid)
        
        entity = cmdb_get_entity(guid)
        # 查询该实体的实时指标
        metrics = fetch_entity_metrics(entity)
        
        node = {
            "entity": entity,
            "metrics": metrics,
            "children": [],
        }
        
        # 查询纵向关系（runs_on, depends_on, includes）
        relations = cmdb_get_relations(guid, dimension="vertical")
        for rel in relations:
            child = _expand(rel.to_guid, depth + 1)
            if child:
                node["children"].append({
                    "relation_type": rel.type_name,
                    "node": child,
                })
        
        # 同时查询横向关系（calls）— 只展示，不展开
        horiz_rels = cmdb_get_relations(guid, dimension="horizontal")
        if horiz_rels:
            node["calls_to"] = [r.to_name for r in horiz_rels]
        
        return node
    
    return _expand(entity_guid, 0)
```

### 5.3 关联分析面板

**点击下钻后，右侧面板不仅展示拓扑，还做关联分析：**

```
┌─────────────────────────────────────────────────────┐
│ payment-service 下钻分析                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│ 🔴 根因定位:                                        │
│   db-master CPU 90% → payment-db 慢查询             │
│   → payment-service 超时 → order-service 重试失败   │
│                                                     │
│ 📊 关键指标（最近 15 分钟）:                          │
│   P99 延迟: 450ms (↑ 8x from 55ms)                 │
│   错误率: 29.3% (↑ from 0.1%)                       │
│   QPS: 24.8/s (正常)                                │
│                                                     │
│ 🌲 影响链:                                          │
│   gateway → order-service → payment-service         │
│   → payment-db → db-master (根因)                   │
│                                                     │
│ 💡 建议:                                            │
│   1. 检查 db-master 磁盘 IO                         │
│   2. kill 慢查询                                     │
│   3. 考虑读写分离                                    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 6. API 设计

### 6.1 拓扑数据 API

```
GET /api/v1/cmdb/topology/call?window_minutes=15
  → 调用拓扑（从 Trace 数据）
  
GET /api/v1/cmdb/topology/infra
  → 基础设施拓扑（从 CMDB）
  
GET /api/v1/cmdb/topology/global?biz_service=在线支付
  → 全局拓扑（混合）
  
GET /api/v1/cmdb/entities/{guid}/drill-down?max_depth=3
  → 实体下钻拓扑（纵向归属树 + 指标）
```

### 6.2 下钻 API 响应示例

```json
{
  "entity": {
    "guid": "xxx",
    "name": "payment-service",
    "type_name": "Service",
    "health_score": 55,
    "health_level": "critical",
    "risk_score": 85
  },
  "metrics": {
    "p99_latency": 450.5,
    "error_rate": 29.3,
    "qps": 24.8
  },
  "drill_tree": [
    {
      "relation_type": "runs_on",
      "node": {
        "entity": {"name": "app-02", "type_name": "Host", "health_score": 75},
        "metrics": {"cpu": 65, "memory": 55, "disk": 40},
        "children": [
          {
            "relation_type": "connected_to",
            "node": {
              "entity": {"name": "核心交换机-01", "type_name": "NetworkDevice", "health_score": 95},
              "metrics": {"packet_loss": 0.01},
              "children": []
            }
          }
        ]
      }
    },
    {
      "relation_type": "depends_on",
      "node": {
        "entity": {"name": "payment-db", "type_name": "MySQL", "health_score": 55},
        "metrics": {"connections": 120, "slow_queries": 45},
        "children": [
          {
            "relation_type": "runs_on",
            "node": {
              "entity": {"name": "db-master", "type_name": "Host", "health_score": 30},
              "metrics": {"cpu": 90, "memory": 70, "disk": 45},
              "children": []
            }
          }
        ]
      }
    }
  ],
  "calls_to": ["order-service", "user-cache"],
  "root_cause_hint": "db-master CPU 90% 可能是根因"
}
```

---

## 7. 前端实现方案

### 7.1 技术选型

| 需求 | 方案 | 理由 |
|------|------|------|
| 拓扑图渲染 | **Dagre-D3** 或 **@antv/x6** | 分层布局 + 力导向，成熟稳定 |
| 交互 | SVG + React | 与现有技术栈一致 |
| 动画 | CSS + SVG | 异常脉冲、hover 效果 |
| 下钻面板 | Ant Design Drawer + Tabs | 复用现有组件 |

### 7.2 组件结构

```
TopologyPage
├── TopologyTabs (三种视图切换)
│   ├── CallTopology (调用拓扑)
│   ├── InfraTopology (基础设施拓扑)
│   └── GlobalTopology (全局拓扑) ← 默认
├── TopologyCanvas (拓扑画布)
│   ├── NodeRenderer (节点渲染)
│   └── EdgeRenderer (连线渲染)
└── DrillDownDrawer (下钻详情面板)
    ├── MetricsTab (指标)
    ├── AlertsTab (告警)
    ├── DrillTreeTab (下钻拓扑)
    └── TraceTab (Trace 列表)
```

### 7.3 实现分阶段

**Phase 1（当前可做）：**
- 重构 Topology.tsx 为三 Tab 结构
- 实现全局拓扑（现有 SVG 布局优化）
- 实现下钻 API + 侧边面板
- 纵向下钻拓扑展示

**Phase 2（后续）：**
- 接入 Dagre / x6 做更好的布局
- 调用拓扑边的粗细/颜色按 QPS/错误率渲染
- 实时指标图表接入

**Phase 3（后续）：**
- 基础设施拓扑（物理连接图）
- 根因高亮 + 建议
- 关联分析面板

---

## 8. 与现有架构的关系

| 现有组件 | 拓扑重构如何使用 |
|---------|----------------|
| CMDB relationship 表 | dimension 字段区分横向/纵向，查询时按维度过滤 |
| Trace discovery | 调用拓扑的数据来源 |
| health-engine | 节点颜色和根因高亮 |
| Chat API | 可在下钻面板中集成问答 |

---

_设计完成，待主人确认后进入实现阶段_
