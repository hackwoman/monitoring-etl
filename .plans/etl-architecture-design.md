# 监控数据 ETL 智能平台 - 架构设计

_设计日期：2026-03-28_
_规模目标：数百至数千台云主机_

---

## 0. 平台设计哲学

### 核心价值一：数据接入零人工（Universal Ingestion）

传统运维平台的最大痛点：**每接入一个新数据源，就要写 parser、配 pipeline、调 schema**。

本平台的设计目标是：**接入即用，自动适配**。

```
传统方式：
  新数据源 → 人工分析格式 → 写解析规则 → 配 ETL 管道 → 调试 → 上线
  (耗时：天级)

本平台：
  新数据源 → 接入 OTel Collector → 自动识别协议 → 自动解析 → 自动入库存储
  (耗时：分钟级)
```

**实现机制：**

| 环节 | 自动化手段 | 人工介入 |
|------|-----------|---------|
| 协议识别 | Receiver 插件自动适配 (OTLP/syslog/filelog/prometheus/zipkin/...) | 选择插件即可 |
| 日志解析 | 基于 Grok/JSON/日志模式的**自动模式推断** | 复杂格式才需手写规则 |
| 实体提取 | LLM 从日志中识别服务名/主机名/错误类型 | 无需人工配置 |
| 关系发现 | Trace Span 自动提取调用关系 → 融合 CMDB | 仅确认，不创建 |
| Schema 演进 | 宽表存储 (ClickHouse/JSONB) + 动态字段发现 | 无需预定义全量字段 |
| 存储路由 | 规则引擎自动分发 (日志→ClickHouse, 指标→Doris, 关系→PG) | 仅特殊场景需配置 |

**关键原则：**
- **Convention over Configuration** — 有合理默认值，特殊需求才需配置
- **宽进严出** — 入库宽容（接受任何格式），查询严格（标准化后的结构化数据）
- **自动发现，人工确认** — 系统自动发现新实体/新关系，人只需点确认

---

### 核心价值二：AI 贯穿全层（AI-Native）

AI 不是独立模块，而是**嵌入每一层的能力**：

```
┌─────────────────────────────────────────────────┐
│                   前端层                          │
│  自然语言搜索 │ AI 问答界面 │ 智能 Dashboard 推荐  │
├─────────────────────────────────────────────────┤
│                   API 层                          │
│  Text-to-SQL │ Text-to-PromQL │ 意图识别路由       │
├─────────────────────────────────────────────────┤
│                   智能层                          │
│  异常检测 │ 根因分析 │ 告警聚合 │ 故障预测          │
├─────────────────────────────────────────────────┤
│                   ETL 层                          │
│  LLM 日志解析 │ 自动模式推断 │ 实体智能识别        │
├─────────────────────────────────────────────────┤
│                   采集层                          │
│  智能采样 │ 异常日志自动提升采样率                   │
└─────────────────────────────────────────────────┘
```

**AI 在各层的具体作用：**

| 层 | AI 能力 | 场景 |
|----|--------|------|
| 采集层 | 智能采样 | 正常日志降采样，异常日志全量采集 |
| ETL 层 | LLM 日志解析 | 未知格式日志自动提取结构化字段 |
| ETL 层 | 实体识别 | 从自由文本日志中识别服务名、IP、错误码 |
| 存储层 | 向量化 | 日志自动 Embedding，支持语义搜索 |
| 智能层 | 异常检测 | 指标异常、日志模式突变 |
| 智能层 | 根因分析 | 图遍历 + LLM 推理故障传播链 |
| 智能层 | 告警聚合 | 相似告警自动合并，抑制告警风暴 |
| API 层 | Text-to-SQL | 自然语言转 SQL 查询 |
| API 层 | 结果解释 | 查询结果自动生成自然语言摘要 |
| 前端层 | 智能问答 | Chat 界面，"最近一小时 error 最多的服务是？" |

---

### 核心价值三：业务风险驱动（Business-Risk-First）

**传统运维的致命缺陷：用 IT 视角排序告警，而不是用户视角。**

```
传统告警思维                    本平台告警思维
                              
"磁盘 95% → P1!"             "磁盘 95% → 用户无感 → P4, 计划扩容"
"CPU 90% → P2!"              "CDN 节点挂了 → 50万用户白屏 → P0, 立即处理"
"MySQL 慢查询 → P1!"         "MySQL 慢查询 → 有缓存用户无感 → P4, 明天修"
                              
排序依据：技术严重度             排序依据：业务风险度
关注：IT 觉得什么重要            关注：用户会不会受影响
结果：告警疲劳，真正重要的淹没    结果：精准聚焦，处理真正影响用户的故障
```

**业务风险度 = 技术严重度 × 传播距离 × 影响面**

| 因子 | 计算方式 | 说明 |
|------|---------|------|
| 技术严重度 | 传统指标（CPU/内存/错误率阈值） | 0-100 |
| 传播距离 | CMDB 拓扑：该实体到用户的最短路径 | 前端 1.0 → 中间件 0.4 → 基础设施 0.2 |
| 影响面 | CMDB 拓扑：该实体挂了会影响多少下游 | 全站 3.0 → 单服务 1.0 → 单机 0.3 |

**作为核心价值，风险驱动不是独立模块，而是贯穿平台的思维：**

```
┌─────────────────────────────────────────────────────────┐
│                    每一层都内置风险度                      │
│                                                         │
│  采集层:  每条数据打上实体标签 → 用于后续拓扑关联          │
│  ETL层:  实时关联 CMDB 拓扑 → 计算每条异常的传播距离       │
│  存储层:  告警表内置 risk_score 字段                      │
│  AI层:   根因分析结合风险度 → 按业务影响排序              │
│  API层:  告警列表默认按风险度降序返回                      │
│  前端:   告警中心第一排序维度 = 业务风险度                 │
│                                                         │
│  → 运维人员看到的永远是"对用户影响最大的问题排在最前面"     │
└─────────────────────────────────────────────────────────┘
```

---

## 1. 架构约束原则

| # | 原则 | 要求 | 实现方式 |
|---|------|------|---------|
| **1** | **层间解耦** | 每层独立部署、独立扩缩容，层与层通过标准接口通信 | 每层用独立容器/服务，层间走 OTLP/HTTP/Kafka 标准协议，不走函数调用 |
| **2** | **模块可替换** | 任何组件可独立升级/替换，不影响其他层 | 统一接口契约（OTel 数据模型），替换实现不改协议 |
| **3** | **时间线统一** | 全链路统一时间戳标准，支持跨时区对齐 | 采集端强制 UTC + 毫秒时间戳，存储端统一带时区的 TIMESTAMPTZ，查询端按用户时区展示 |
| **4** | **CMDB 模型统一** | 所有数据类型的实体/关系/属性走同一套 TypeDef 系统 | 单一 `entity` + `relationship` 表，不为不同数据类型建独立表 |
| **5** | **自定义标签上下文** | 用户可定义任意标签（如业务线、环境、租户），标签贯穿全链路 | `labels` JSONB 字段在采集→ETL→存储→查询全链路透传，支持基于标签的过滤/聚合/权限 |
| **6** | **数据零丢失** | 任何环节故障不丢数据，支持断点续传和历史回补 | 边缘持久化缓冲 + ACK 机制 + 间隙检测 + 回补能力 |

### 1.1 数据可靠性设计（Data Reliability）

运维保障场景，数据丢失 = 故障盲区。全链路必须保证 At-Least-Once 语义。

#### 全链路可靠性架构

```
数据源                采集层              管道层             存储层
 │                    │                   │                  │
 │  ① 源端持久化      │  ② 边缘缓冲       │  ③ 管道背压       │  ④ 事务写入
 │  (文件/本地DB)     │  (磁盘 WAL)       │  (队列)          │  (ACK确认)
 │                    │                   │                  │
 ├─ App 写本地日志    ├─ OTel filelog     ├─ Vector 内置     ├─ ClickHouse
 │  (天然持久)        │  持久化 cursor     │  buffer + disk   │  异步批量写
 │                    │                   │  ACK 模式        │  (最终一致)
 │                    │                   │                  │
 ├─ 网络设备 Syslog   ├─ OTel syslog      ├─ Redis Streams   ├─ PostgreSQL
 │  (UDP 无状态!)    │  写 WAL 后才 ACK   │  消费者确认后    │  事务提交后
 │                    │                   │  才移除消息       │  才算成功
 │                    │                   │                  │
 └─ SNMP (轮询)      └─ 轮询数据本地     └─ 失败重试队列    └─ Dead Letter
     可回溯查询           暂存                    指数退避          Queue 兜底
```

#### ① 采集层可靠性（Agent 侧）

**文件日志：天然可靠**
- App 写入本地文件 → Agent 读取 → 记录 cursor（已读位置）
- Agent 重启后从 cursor 继续读，不丢不重

**Syslog/网络数据：需要额外保障**
```
问题：Syslog/UDP 是无连接协议，Agent 挂了数据就丢了

解决方案：
┌──────────────────────────────────────────────┐
│          OTel Collector Syslog Receiver       │
│                                               │
│  UDP:514 ──→ 写 WAL 文件 (fsync) ──→ 处理 ──→ 推送
│                  │                             │
│                  └── Agent 重启后从 WAL 恢复    │
│                                               │
│  TCP:514 ──→ 直接处理 (TCP 有重传机制)         │
│              但 Agent 不可用时发送端会重试      │
└──────────────────────────────────────────────┘
```

**OTel Collector 关键配置：**
```yaml
# otlphttp exporter - 开启 ACK 和重试
exporters:
  otlphttp:
    endpoint: http://vector:4318
    sending_queue:
      enabled: true
      queue_size: 5000          # 内存队列大小
      num_consumers: 10
    retry_on_failure:
      enabled: true
      initial_interval: 1s
      max_interval: 30s
      max_elapsed_time: 300s    # 最多重试 5 分钟

# filelog receiver - 持久化 cursor
receivers:
  filelog:
    include: [/var/log/app/*.log]
    storage: file_storage       # cursor 持久化到磁盘

extensions:
  file_storage:
    directory: /var/lib/otelcol
    fsync: true                 # 每次写 cursor 都 fsync
```

#### ② 管道层可靠性（Vector）

**Vector 内置 Buffer（磁盘持久化）：**
```toml
# Vector sink 配置 - 磁盘 buffer + ACK
[sinks.clickhouse]
type = "clickhouse"
inputs = ["enriched_logs"]
endpoint = "http://clickhouse:8123"

# 关键：磁盘持久化 buffer
[sinks.clickhouse.buffer]
type = "disk"
max_size = 107374182400    # 100GB 最大磁盘占用
when_full = "block"        # 满了阻塞，不丢数据
```

**管道背压机制：**
```
采集 Agent → [Vector Buffer] → 存储

存储慢/不可用：
├── Vector buffer 填满 → 背压到 Agent
├── Agent 队列填满 → Agent 写 WAL 暂停读取
├── 数据在源端持续累积（文件/设备缓冲）
└── 存储恢复 → 全链路自动疏通 → 数据不丢
```

#### ③ 存储层可靠性

**ClickHouse：**
- 异步批量写入，性能好但不保证即时持久
- 方案：写入后记录 `ingest_watermark`（已成功写入的最大时间戳）
- 查询时用 `ingest_watermark` 判断数据完整性

**PostgreSQL（CMDB）：**
- 事务提交即持久化，ACID 保证
- 关系融合操作用事务：先查→判断→写入，原子执行

#### ④ 间隙检测与回补

```sql
-- 数据完整性追踪表
CREATE TABLE data_completeness (
    source_id       VARCHAR(256),       -- 数据源标识
    time_bucket     TIMESTAMPTZ,        -- 时间桶（按小时/分钟）
    expected_count  BIGINT,             -- 预期数据量
    actual_count    BIGINT,             -- 实际写入量
    first_event     TIMESTAMPTZ,        -- 该桶内最早事件
    last_event      TIMESTAMPTZ,        -- 该桶内最晚事件
    gap_seconds     INT,                -- 桶内最大时间间隔（秒）
    status          VARCHAR(32),        -- complete/gap_detected/partial
    updated_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (source_id, time_bucket)
);
```

**自动间隙检测：**
```python
# Vector Transform: 检测时间间隔异常
[transforms.detect_gap]
type = "remap"
source = '''
  .time_since_last = now() - .last_seen_time
  # 日志源连续超过 5 分钟无数据 → 标记为可能间隙
  if .time_since_last > 300 {
    .gap_alert = true
    .gap_seconds = .time_since_last
  }
'''
```

**回补策略：**

| 场景 | 回补方式 |
|------|---------|
| Agent 短暂中断（< 1 小时） | Agent 重启后从 cursor 自动补读，无需人工 |
| Agent 长时间中断 | 文件日志：从 cursor 补读完整文件；Syslog：无法回补（UDP 无持久化） |
| 管道阻塞 | Vector buffer 磁盘持久化，恢复后自动消费 |
| 存储写入失败 | Dead Letter Queue → 定时重试 → 人工介入兜底 |
| 网络设备数据丢失 | **不可回补**（SNMP/Syslog 无持久化）→ 在完整性表中标记 gap，查询时提示 |

#### 数据一致性级别总结

| 数据类型 | 一致性级别 | 理由 |
|---------|-----------|------|
| 应用日志 | **强一致**（At-Least-Once） | 文件持久化 + cursor + 补读 |
| 系统日志 | **强一致** | 同应用日志 |
| Trace | **强一致** | App SDK 本地 buffer + 重试 |
| Prometheus 指标 | **最终一致** | Pull 模式，间隔采样，可回溯 |
| 网络设备 Syslog (TCP) | **最终一致** | TCP 重传 + Agent WAL |
| 网络设备 Syslog (UDP) | **尽力而为** | ⚠️ UDP 无状态，Agent 挂了可能丢数据，需标 gap |
| SNMP/NetFlow | **尽力而为** | ⚠️ 轮询间隔内数据不可回补 |
| 告警事件 | **强一致** | 走队列 + ACK |

**关键设计原则：**
- **能回补的走自动回补**（文件日志、Trace）
- **不能回补的标 gap + 通知**（UDP syslog、SNMP）
- **查询层感知完整性**：查询结果中展示"该时间段数据可能不完整"的提示

**时间线统一细节：**

```
数据源侧                          平台内部                         展示侧
                                  
各数据源时区不一                  统一 UTC 毫秒                    按用户时区
├─ 日志: CST/无时区    ──→  OTel Collector:         ──→  前端: +08:00
├─ SNMP: 设备时间        resource.attributes 中       ├─ ClickHouse: DateTime64(3, 'UTC')
├─ Trace: UTC            标准化 timestamp              ├─ PostgreSQL: TIMESTAMPTZ
└─ NetFlow: UTC          + 采集时间 ingest_time       └─ Doris: DATETIMEV2(3)
                            (区分事件时间 vs 采集时间)
```

**自定义标签上下文支持：**

```sql
-- 标签定义表（用户可自定义）
CREATE TABLE label_definition (
    label_key       VARCHAR(128) PRIMARY KEY,
    label_name      VARCHAR(256),        -- 显示名
    value_type      VARCHAR(32),         -- string/number/enum
    enum_values     JSONB,               -- enum 类型的可选值
    description     TEXT,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 标签使用场景：
-- 1. 采集时附加: OTel resource.attributes → labels.business_line = "支付"
-- 2. ETL 时关联: 从 CMDB 查实体属性 → labels.env = "prod"
-- 3. 查询时过滤: SELECT * FROM logs WHERE labels @> '{"business_line":"支付"}'
-- 4. 权限控制: 用户只能看 labels.tenant = "用户所属租户" 的数据
-- 5. AI 时上下文: "查询支付链路最近 1 小时的日志" → labels.business_line = "支付"
```

### 1.2 数据时效分层（Data Timeliness）

1 小时前的数据不是"没用"，是**用途不同**。需要根据数据到达的延迟，自动分流到不同的处理通道。

#### 核心概念：事件时间 vs 到达时间

```
事件时间 (Event Time)：数据实际发生的时间
到达时间 (Arrival Time)：数据进入平台的时间
延迟 = 到达时间 - 事件时间
```

#### 时效分层模型

```
延迟 < 30秒    →   🔴 HOT   →   实时告警、实时大盘、秒级异常检测
30秒 ~ 5分钟   →   🟡 WARM  →   近实时分析、分钟级聚合、延迟告警
5分钟 ~ 1小时  →   🔵 COOL  →   批量分析、趋势补全、根因回溯
> 1小时       →   ⚪ COLD  →   仅入库存储、历史分析、ML 训练、合规审计
```

#### ETL 管道中的时效路由

```
OTel Collector → Vector ETL
                    │
                    ▼
              ┌─────────────┐
              │ 计算延迟     │
              │ delay =      │
              │ arrival_time │
              │ - event_time │
              └──────┬──────┘
                     │
        ┌────────────┼────────────┬────────────┐
        ▼            ▼            ▼            ▼
   delay<30s    30s~5min     5min~1h        >1h
   ┌────────┐  ┌────────┐  ┌────────┐  ┌─────────────┐
   │ HOT    │  │ WARM   │  │ COOL   │  │ COLD        │
   │ 路由   │  │ 路由   │  │ 路由   │  │ 路由         │
   └───┬────┘  └───┬────┘  └───┬────┘  └──────┬──────┘
       │           │           │               │
       ▼           ▼           ▼               ▼
   实时告警     近实时聚合   批量分析       仅存储
   实时大盘     延迟告警     趋势补全       ML训练
   秒级检测     分钟级窗口   根因回溯       合规审计
```

```toml
# Vector 时效路由配置
[transforms.timeliness_classify]
type = "remap"
source = '''
  event_ts = to_timestamp(.timestamp)
  arrival_ts = now()
  delay_secs = to_int(arrival_ts - event_ts)

  if delay_secs < 30 {
    .timeliness = "hot"
  } else if delay_secs < 300 {
    .timeliness = "warm"
  } else if delay_secs < 3600 {
    .timeliness = "cool"
  } else {
    .timeliness = "cold"
  }
  .delay_seconds = delay_secs
'''

[transforms.route_by_timeliness]
type = "route"
inputs = ["timeliness_classify"]
route.hot = '.timeliness == "hot"'
route.warm = '.timeliness == "warm"'
route.cool_cold = '.timeliness == "cool" || .timeliness == "cold"'

# HOT → 实时处理链路
[sinks.realtime_alert]
type = "elasticsearch"  # 或直接推到告警引擎
inputs = ["route_by_timeliness.hot"]

# WARM/COOL/COLD → 统一存储，但处理策略不同
[sinks.clickhouse]
type = "clickhouse"
inputs = ["route_by_timeliness.warm", "route_by_timeliness.cool_cold"]
```

#### 超时数据的处理策略

| 延迟范围 | 实时告警 | 实时大盘 | 近实时分析 | 历史分析 | ML 训练 |
|---------|---------|---------|-----------|---------|---------|
| < 30s | ✅ 参与 | ✅ 参与 | ✅ 参与 | ✅ | ✅ |
| 30s ~ 5min | ⚠️ 标记延迟 | ⚠️ 补充展示 | ✅ 参与 | ✅ | ✅ |
| 5min ~ 1h | ❌ 不参与 | ❌ 不参与 | ⚠️ 标记补全 | ✅ | ✅ |
| > 1h | ❌ | ❌ | ❌ | ✅（标 gap） | ✅ |

**关键原则：**
- **永远入库**：不管多晚到的数据都存储，不丢弃
- **处理策略分层**：不同延迟的数据走不同的处理通道
- **可视化感知延迟**：大盘展示时区分"实时数据"和"补录数据"
- **告警只看热数据**：超时数据不触发实时告警（避免已过时的告警噪音）

#### 数据完整性感知查询

```sql
-- 查询时自动检测数据完整性
-- 例：查询最近 1 小时的错误日志，同时返回数据完整性信息

SELECT 
    time_bucket,
    error_count,
    -- 标注哪些时间段的数据可能是补录的
    CASE 
        WHEN last_event < now() - interval '5 minutes' THEN 'delayed_data'
        ELSE 'realtime'
    END as data_freshness,
    -- 标注是否有时间间隙
    CASE 
        WHEN gap_seconds > 300 THEN 'has_gap'
        ELSE 'complete'
    END as completeness
FROM log_aggregation
WHERE timestamp > now() - interval '1 hour'
  AND level = 'error'
ORDER BY time_bucket;
```

**查询结果展示：**
```
时间              错误数   数据状态
09:00 - 09:05     12      ✅ 实时
09:05 - 09:10     8       ✅ 实时
09:10 - 09:15     3       ⚠️ 数据延迟到达 (延迟 25 分钟)
09:15 - 09:20     ?       ❌ 数据缺失 (可能原因: Agent 故障)
09:20 - 09:25     15      ✅ 实时
```

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          数据源层 (Data Sources)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ 应用日志  │  │ 系统日志  │  │  Trace   │  │Prometheus│  ...       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                             │
│  │ 网络设备  │  │安全设备   │  │流量数据   │                             │
│  │ Syslog/  │  │ IDS/IPS  │  │NetFlow/  │                             │
│  │ SNMP     │  │ WAF/防火墙│  │ sFlow    │                             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                             │
└───────┼──────────────┼──────────────┼────────────────────────────────┘
        │              │              │
┌───────▼──────────────▼──────────────▼─────────────────────────────────┐
│                      采集层 (Collection)  [可独立扩容]                  │
└───────┼──────────────┼──────────────┼──────────────┼─────────────────┘
        │              │              │              │
┌───────▼──────────────▼──────────────▼──────────────▼─────────────────┐
│                      采集层 (Collection)                              │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │           OpenTelemetry Collector (Host Agent)            │       │
│  │   Receivers: filelog | otlp | prometheus | ...           │       │
│  │   Processors: parse | filter | batch | resource          │       │
│  │   Exporters: OTLP → ETL Pipeline                         │       │
│  └──────────────────────────────────────────────────────────┘       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                    ETL 管道层 (Pipeline)                              │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │              Vector (Rust, 高性能数据管道)                 │       │
│  │                                                           │       │
│  │  Source ──→ Transform Chain ──→ Sink                      │       │
│  │  (otlp)     parse                                         │       │
│  │              enrich (CMDB 关联)                            │       │
│  │              extract (实体提取)                            │       │
│  │              route (按类型分发)                             │       │
│  │                         ↓                                 │       │
│  │            ┌────────┬────────┬────────┐                   │       │
│  │         ClickHouse  CMDB    Doris   Queue               │       │
│  │         (日志存储)  (关系)  (聚合)  (事件流)              │       │
│  └──────────────────────────────────────────────────────────┘       │
└───────┬──────────────┬──────────────┬──────────────┬────────────────┘
        │              │              │              │
┌───────▼─────┐ ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
│  ClickHouse │ │ PostgreSQL  │ │  Doris   │ │ Event Queue │
│  (日志存储)  │ │ + AGE       │ │ (OLAP)   │ │  (Kafka/    │
│  海量日志    │ │ + pgvector  │ │ 多维分析  │ │   Redis)    │
│  压缩查询    │ │ (CMDB核心)  │ │          │ │             │
└──────┬──────┘ └──────┬──────┘ └────┬─────┘ └──────┬──────┘
       │               │             │               │
┌──────▼───────────────▼─────────────▼───────────────▼────────────────┐
│                      智能运维层 (AIOps)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  向量检索     │  │  LLM 引擎    │  │  根因分析 / 异常检测      │  │
│  │  (pgvector)   │  │  (Text-to-   │  │  (图推理 + 规则引擎)      │  │
│  │  日志相似搜索 │  │   SQL/PromQL) │  │                          │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
└─────────┼─────────────────┼───────────────────────┼─────────────────┘
          │                 │                       │
          │    ┌────────────▼───────────────┐       │
          │    │  ⭐ 业务风险度引擎 (Risk)   │       │
          │    │  传播距离 × 影响面 × 业务权重│       │
          │    │  实时查 CMDB 拓扑            │◄──────┤ 所有告警/异常
          │    │  输出: risk_score + user_impact│     │ 都经过风险度计算
          │    └────────────┬───────────────┘       │
          │                 │                       │
┌─────────▼─────────────────▼───────────────────────▼─────────────────┐
│                       API 层 (FastAPI)                               │
│  /cmdb/*   /logs/*   /metrics/*   /traces/*   /ai/*   /alerts/*    │
│  /risk/*   权限 │ 多租户 │ 缓存 │ 限流                               │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      前端层 (React + Ant Design)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ CMDB     │  │ 日志查询  │  │ 告警中心  │  │ 智能问答  │            │
│  │ 拓扑图   │  │ (SQL)    │  │ 按风险度  │  │ (LLM)   │            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块详细设计

### 3.1 数据采集层

**选型：OpenTelemetry Collector (Agent 模式)**

每台主机部署一个 OTel Collector Agent，以 DaemonSet（K8s）或 systemd 服务（裸机）运行。

```
Host
├── App (stdout/file logs)
├── OTel Collector
│   ├── Receivers:
│   │   ├── filelog    → 采集应用日志文件
│   │   ├── syslog     → 采集系统日志
│   │   └── otlp       → 接收应用直接推送的 OTLP 数据
│   ├── Processors:
│   │   ├── resource   → 添加 host.name, service.name 等资源属性
│   │   ├── batch      → 批量发送，减少网络开销
│   │   └── filter     → 过滤噪声日志
│   └── Exporters:
│       └── otlphttp   → 推送到 ETL Pipeline (Vector)
```

**日志标准化策略：**
- 统一为 OTel LogData 模型：Timestamp + Severity + Body + Resource + Attributes
- 应用日志通过 filelog receiver 的 operators 做多行合并 + JSON/Regex 解析
- 系统日志通过 syslog receiver 直接采集

### 3.1.1 网络/安全设备接入

**支持矩阵：**

| 数据类型 | 协议/格式 | OTel Receiver | 典型设备 |
|---------|----------|---------------|---------|
| 系统日志 | Syslog RFC 3164/5424 | `syslog` | 所有网络/安全设备 |
| 设备指标 | SNMP v1/v2c/v3 | `snmp` | 交换机、路由器 |
| 流量数据 | NetFlow v5/v9/IPFIX | `netflow` | Cisco、华为路由器 |
| 流量采样 | sFlow | `sflow` | 交换机、负载均衡 |
| 告警推送 | SNMP Traps | `snmp` trap 模式 | 防火墙、IDS |
| 安全日志 | JSON/自定义 | `filelog` | Suricata、Snort |

**部署架构（解耦设计）：**

```
网络/安全设备集群
├── 防火墙群 (Palo Alto/Fortinet/ASA)
│   ├── Syslog:514 → OTel Agent (专用网络采集节点)
│   └── NetFlow:2055 → OTel Agent
├── 交换机/路由器 (Cisco/Huawei/H3C)
│   ├── Syslog:514 → OTel Agent
│   └── SNMP polling → OTel Agent
├── IDS/IPS (Suricata/Snort)
│   └── JSON 日志 → OTel Agent
└── WAF/DDoS 设备
    └── Syslog:514 → OTel Agent
         │
         ▼
    专用采集节点 (独立于应用主机 Agent)
    ├── syslog receiver (监听多个端口/VLAN)
    ├── netflow receiver
    ├── snmp receiver
    └── otlphttp exporter → Vector ETL
```

**厂商日志自动解析（零人工原则）：**

```python
# Vector Transform 伪代码
[transforms.parse_network_log]
type = "remap"
source = '''
  # Step 1: 已知厂商规则库匹配
  parsed = null
  if starts_with(.message, "1,20") {
    # Palo Alto 格式
    parsed = parse_palo_alto(.message)
    .vendor = "palo_alto"
  } else if starts_with(.message, "date=") {
    # Fortinet 格式
    parsed = parse_fortinet_kv(.message)
    .vendor = "fortinet"
  } else if match(.message, r"%ASA-") {
    # Cisco ASA
    parsed = parse_cisco_asa(.message)
    .vendor = "cisco_asa"
  }

  # Step 2: 规则库未覆盖 → LLM fallback
  if !parsed {
    parsed = call_llm_parse(.message, prompt="提取: vendor, timestamp, src_ip, dst_ip, action, protocol, port")
    .vendor = parsed.vendor ?? "unknown"
    .parse_method = "llm"
  } else {
    .parse_method = "rule"
  }

  # Step 3: 标准化字段
  .src_ip = parsed.src_ip
  .dst_ip = parsed.dst_ip
  .action = parsed.action    # allow/deny/drop
  .protocol = parsed.protocol
  .device_ip = .resource.host.ip
'''
```

### 3.1.2 端到端可观测：客户端 → 后端 → 基础设施

**核心理念：** 不只是监控服务器，而是追踪**每一次用户操作的完整旅程**。

```
用户操作                          端到端 Trace ID 贯穿全链路
  │
  ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 浏览器    │  │ CDN/网关  │  │ API 服务  │  │ 数据库    │  │ 基础设施  │
│          │  │          │  │          │  │          │  │          │
│ 用户点击  │→│ TLS握手   │→│ 业务处理  │→│ SQL执行   │→│ 磁盘IO   │
│ 2.3s     │  │ 50ms     │  │ 120ms    │  │ 35ms     │  │ 8ms      │
│          │  │          │  │          │  │          │  │          │
│ LCP:1.8s │  │ TTFB:200ms│ │ gRPC     │  │ 慢查询    │  │ CPU 85%  │
│ FID:45ms │  │ 首字节    │  │ 调用链    │  │ 锁等待    │  │ IO wait  │
│ CLS:0.05 │  │          │  │          │  │          │  │          │
│ JS错误:1  │  │          │  │          │  │          │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
     │              │             │             │             │
     └──────────────┴─────────────┴─────────────┴─────────────┘
                         同一个 trace_id 贯穿
                    用户能感知的延迟 = 所有环节之和
```

#### 客户端数据维度矩阵

| 维度 | 浏览器 (Web RUM) | 移动 App | 小程序 | 数据用途 |
|------|-----------------|---------|--------|---------|
| **性能指标** | LCP, FID, CLS, TTFB, FCP, INP | App 启动时间, 页面渲染, FPS | 渲染耗时 | 前端性能优化 |
| **网络状况** | 连接类型(4G/WiFi), RTT, 下行带宽 | 网络类型, 弱网检测 | 同移动 | 排查客户端网络问题 |
| **请求追踪** | XHR/Fetch 的 trace_id, 耗时, 状态码 | HTTP 请求 trace_id | 同移动 | 端到端链路串联 |
| **JS/崩溃** | JS 异常, 资源加载失败, 白屏检测 | Crash, ANR, 原生异常 | 同移动 | 错误监控 |
| **用户行为** | 页面浏览, 点击, 滚动, 表单交互 | 页面切换, 按钮点击 | 同移动 | 行为分析 + 转化漏斗 |
| **用户上下文** | userId, sessionId, 设备/浏览器 | userId, deviceId, OS版本 | 同移动 | 多租户 + 用户画像 |
| **业务事件** | 下单, 支付, 搜索, 注册 | 同 Web | 同 Web | 业务指标监控 |
| **自定义指标** | 页面级自定义埋点 | App 级自定义 | 同移动 | 业务定制需求 |
| **用户标签** | VIP/普通, 地域, 来源渠道 | 同 Web | 同 Web | 分群分析 |

#### 采集架构

```
┌─────────────────────────────────────────────────────────────┐
│                     客户端 SDK 层                            │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Web RUM SDK  │  │ Mobile SDK   │  │ 小程序 SDK   │      │
│  │ (OTel JS)    │  │ (OTel Swift/ │  │ (OTel 微信   │      │
│  │              │  │  Kotlin)     │  │  小程序扩展)  │      │
│  │ • 页面性能   │  │ • App 性能   │  │ • 页面性能   │      │
│  │ • XHR 追踪   │  │ • 网络请求   │  │ • 请求追踪   │      │
│  │ • 用户交互   │  │ • Crash 检测 │  │ • 用户行为   │      │
│  │ • JS 错误    │  │ • 用户行为   │  │ • 业务事件   │      │
│  │ • 业务事件   │  │ • 设备信息   │  │ • 设备信息   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
          │  Beacon/OTLP    │  OTLP/HTTP      │  OTLP/HTTP
          │  (页面关闭时     │  (实时推送)      │  (实时推送)
          │   也能发送)      │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│               边缘接入层 (Edge Collector)                     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  OTel Collector (边缘节点 / CDN 回源)                  │   │
│  │                                                       │   │
│  │  Receivers:                                           │   │
│  │    • otlp (gRPC + HTTP) → 接收客户端 SDK 数据         │   │
│  │    • zipkin              → 兼容 Zipkin 格式           │   │
│  │                                                       │   │
│  │  Processors:                                          │   │
│  │    • resource    → 补充边缘节点信息                    │   │
│  │    • transform   → 会话关联（session_id → trace_id）  │   │
│  │    • filter      → 过滤无意义的健康检查请求            │   │
│  │    • batch       → 批量，减少回源带宽                  │   │
│  │                                                       │   │
│  │  Exporters:                                           │   │
│  │    • otlphttp    → 推送到中心 ETL 管道                │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                  ETL 管道 (Vector)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          ClickHouse   Doris/OLAP    CMDB/Grafana
         (端到端明细)  (业务聚合)    (链路追踪+拓扑)
```

#### 端到端 Trace 关联模型

**核心：一个 trace_id 从浏览器贯穿到数据库。**

```
用户点击"提交订单"
       │
       ▼
[浏览器] trace_id=abc123
  ├─ span: 页面渲染 (beforeunload)
  ├─ span: XHR POST /api/order (携带 traceparent header)
  │    ├─ 总耗时: 2300ms
  │    ├─ TTFB: 200ms (等待后端首字节)
  │    └─ 下载: 2100ms (传输+渲染)
  │
  │    ─────────── 网络边界 ───────────
  │
  ├─ [API Gateway] trace_id=abc123 (从 traceparent header 继承)
  │    └─ span: 路由转发 15ms
  │
  ├─ [order-service] trace_id=abc123
  │    ├─ span: 参数校验 5ms
  │    ├─ span: 库存检查 (gRPC → inventory-service) 80ms
  │    │    └─ span: Redis GET 3ms
  │    ├─ span: 创建订单 (SQL INSERT) 35ms
  │    │    └─ 慢查询! disk IO wait 28ms
  │    └─ span: 发消息到 MQ 12ms
  │
  └─ [infrastructure]
       └─ span: MySQL disk IO 28ms ← 根因在这里!
           └─ host: db-node-03, disk_util: 95%
```

**Trace 关联的数据表：**

```sql
-- 端到端 Trace 明细（ClickHouse）
CREATE TABLE e2e_traces (
    trace_id          String,
    span_id           String,
    parent_span_id    String,
    
    -- 来源标记
    source            Enum8('browser' = 1, 'mobile' = 2, 'gateway' = 3, 
                            'service' = 4, 'database' = 5, 'infra' = 6),
    
    -- 时间
    start_time_us     UInt64,        -- 微秒
    duration_us       UInt64,
    
    -- 实体关联
    service_name      String,
    endpoint          String,        -- /api/order, SQL: INSERT INTO ...
    host_name         String,
    
    -- 客户端特有字段
    user_id           Nullable(String),
    session_id        Nullable(String),
    page_url          Nullable(String),
    device_type       Nullable(String),    -- desktop/mobile/tablet
    browser           Nullable(String),
    os                Nullable(String),
    network_type      Nullable(String),    -- wifi/4g/5g
    geo_country       Nullable(String),
    geo_city          Nullable(String),
    
    -- 性能指标
    client_ttfb_ms    Nullable(UInt32),    -- 客户端感知的 TTFB
    client_lcp_ms     Nullable(UInt32),    -- LCP (仅浏览器)
    client_fcp_ms     Nullable(UInt32),
    client_cls        Nullable(Float32),
    client_fid_ms     Nullable(UInt32),
    
    -- 业务标签
    labels            Map(String, String), -- 自定义标签全透传
    
    -- 状态
    status_code       UInt16,
    is_error          UInt8,
    error_message     Nullable(String)
) ENGINE = MergeTree()
ORDER BY (trace_id, start_time_us)
PARTITION BY toYYYYMMDD(fromUnixTimestamp64Micro(start_time_us));
```

#### 客户端 SDK 核心能力

```javascript
// Web RUM SDK 示例 (OTel JS)
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { UserInteractionInstrumentation } from '@opentelemetry/instrumentation-user-interaction';

const provider = new WebTracerProvider({
  resource: new Resource({
    // 自动注入上下文
    'service.name': 'web-app',
    'user.id': getUserId(),          // 用户 ID
    'user.session': getSessionId(),  // 会话 ID
    'user.tags': JSON.stringify({    // 用户标签
      'vip_level': 'gold',
      'region': 'east_china',
      'channel': 'wechat'
    }),
    'device.type': getDeviceType(),
    'browser.name': getBrowserName(),
    'network.type': getConnectionType(),  // 4g/wifi/slow-2g
  })
});

// 自动采集：
// 1. 页面导航性能 (LCP, FCP, CLS, FID, INP)
// 2. XHR/Fetch 请求 (自动关联 trace_id)
// 3. 用户交互 (click, input 事件)
// 4. JS 异常
// 5. 资源加载错误

// 手动埋点：业务事件
tracer.startActiveSpan('business.order.submit', (span) => {
  span.setAttributes({
    'business.event': 'order_submit',
    'business.order_id': orderId,
    'business.amount': amount,
    'business.product_count': items.length,
  });
  // 业务逻辑...
  span.end();
});
```

#### 端到端分析场景

| 场景 | 查询方式 | 价值 |
|------|---------|------|
| **用户投诉"页面很卡"** | 按 user_id + session_id 查端到端 trace → 看每段耗时 | 精确定位瓶颈在哪 |
| **转化率下降** | 关联业务事件(下单) + 前端性能(LCP) + 后端延迟 | 发现"支付页面 LCP>3s 导致用户流失" |
| **某地区用户访问慢** | 按 geo_city 分组看 TTFB 分布 | 发现"华东用户延迟高→CDN 节点问题" |
| **移动端兼容性问题** | 按 device_type + os_version 看 JS 错误率 | 发现"iOS 15 上某个 API 不兼容" |
| **弱网用户体验差** | 按 network_type 分组看错误率和延迟 | 发现"3G 网络下图片加载超时" |
| **全链路延迟 TopN** | trace_id 排序取最大 duration → 逐段分析 | 快速找到最慢的链路 |

#### 双维度图模型（完整版）

```
                    纵向（抽象层级）
                    
    业务层  ┌─ 业务流程 ──── 转化漏斗 ──── GMV/UV
            │    │                            │
    应用层  │  Service ──calls──→ Service      │ 业务↔服务
            │    │                │           │ 关联
    运行时  │  K8sPod ──runs_on─→ Node        │
            │    │                │           │
    基础层  └─ Host ──connected→ Switch       │
                  │                           │
            ┌─────┴───────────────────────────┘
            │
            │  横向（跨领域关联）
            │
    客户端  Browser ──sends_trace──→ Gateway ──→ Service
      │         │                       │           │
   user_id   session_id            trace_id      span_id
   geo_loc   device_type
   LCP/FID   network_type
```

```cypher
-- 端到端影响分析：用户投诉 → 直达基础设施
MATCH path = (user:User {id: 'user_12345'})
      -[:has_session]->(session:Session)
      -[:made_request]->(client_span:BrowserSpan {trace_id: 'abc123'})
      -[:traces_to]->(gateway_span:ServiceSpan)
      -[:calls]->(service_span:ServiceSpan)
      -[:queries]->(db_span:DBSpan)
      -[:runs_on]->(infra:Host)
RETURN path

-- 业务指标关联基础设施：支付成功率下降 → 根因
MATCH (biz:BusinessMetric {name: 'payment_success_rate', drop: true})
      -[:occurred_at]->(time_window:TimeBucket)
      -[:related_to]->(traces:E2ETrace)
      -[:slow_at]->(slow_span:Span)
      -[:runs_on]->(host:Host)
RETURN host.name, host.metrics, slow_span.endpoint, slow_span.duration_ms
ORDER BY slow_span.duration_ms DESC
```

### 3.2 ETL 管道层

**选型：Vector (Rust, 高性能)**

Vector 作为中心化数据管道，接收所有 Agent 推送的数据。

```yaml
# vector.toml 概念配置
[sources.otlp_logs]
type = "opentelemetry"
grpc = { address = "0.0.0.0:4317" }
http = { address = "0.0.0.0:4318" }

# ---- Transform Chain ----

# 1. 日志解析：提取结构化字段
[transforms.parse_log]
type = "remap"
inputs = ["otlp_logs.logs"]
source = '''
  . = parse_json!(string!(.message)) ?? { "raw": .message }
  .timestamp = to_timestamp(.timestamp) ?? now()
  .level = downcase(.level ?? "info")
'''

# 2. 实体提取：识别日志中的服务、主机、应用
[transforms.extract_entity]
type = "remap"
inputs = ["parse_log"]
source = '''
  # 从日志中提取实体标识
  .entity.service = .service.name ?? .k8s.pod.labels["app"] ?? "unknown"
  .entity.host = .resource.host.name ?? .host
  .entity.trace_id = .trace_id  # 如果有 trace id
'''

# 3. CMDB 关联：从 CMDB 查询实体信息，丰富日志
[transforms.enrich_cmdb]
type = "http"
inputs = ["extract_entity"]
uri = "http://cmdb-api:8000/api/v1/enrich"
method = "POST"

# 4. 路由分发
[transforms.route]
type = "route"
inputs = ["enrich_cmdb"]
route.debug = '.level == "debug"'
route.error = '.level == "error" || .level == "fatal"'

# ---- Sinks ----
[sinks.clickhouse]
type = "clickhouse"
inputs = ["enrich_cmdb", "!route.error"]
endpoint = "http://clickhouse:8123"
database = "logs"
table = "log_entries"

[sinks.cmdb_entity]
type = "http"
inputs = ["extract_entity"]
uri = "http://cmdb-api:8000/api/v1/entities/heartbeat"
method = "POST"

[sinks.doris]
type = "http"
inputs = ["route.error"]
uri = "http://doris:8030/api/logs/errors"
```

**核心 Transform 能力：**
| 阶段 | 功能 | 说明 |
|------|------|------|
| parse | 日志解析 | JSON/Regex/多行合并 |
| extract | 实体提取 | 从日志识别服务、主机、TraceID |
| enrich | CMDB 关联 | 查询 CMDB 丰富实体信息 |
| route | 路由分发 | 按类型/级别分发到不同存储 |

### 3.3 CMDB 对象模型 ⭐ (核心)

#### 3.3.1 实体类型系统

参考 Apache Atlas TypeDef，设计可扩展的实体类型系统：

```sql
-- 实体类型定义表
CREATE TABLE entity_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    super_types     JSONB,           -- 继承的父类型
    attribute_defs  JSONB,           -- 属性定义
    description     TEXT,
    version         INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 实体实例表
CREATE TABLE entity (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL REFERENCES entity_type_def(type_name),
    name            VARCHAR(512) NOT NULL,
    qualified_name  VARCHAR(1024) UNIQUE NOT NULL,  -- 全局唯一标识
    attributes      JSONB,           -- 类型特定属性
    status          VARCHAR(32) DEFAULT 'active',
    source          VARCHAR(64),     -- 数据来源: manual/cmdb_import/trace_discovery
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 关系定义表
CREATE TABLE relationship_type_def (
    type_name       VARCHAR(128) PRIMARY KEY,
    end1_type       VARCHAR(128),    -- 一端实体类型
    end1_name       VARCHAR(128),    -- 一端角色名
    end2_type       VARCHAR(128),    -- 另一端实体类型
    end2_name       VARCHAR(128),    -- 另一端角色名
    description     TEXT
);

-- 关系实例表
CREATE TABLE relationship (
    guid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name       VARCHAR(128) NOT NULL REFERENCES relationship_type_def(type_name),
    end1_guid       UUID NOT NULL REFERENCES entity(guid),
    end2_guid       UUID NOT NULL REFERENCES entity(guid),
    attributes      JSONB,           -- 关系属性（如调用次数、延迟等）
    source          VARCHAR(64),     -- 来源: manual/imported/trace_discovered
    confidence      FLOAT DEFAULT 1.0,  -- 置信度（Trace 发现的关系 < 1.0）
    first_seen      TIMESTAMPTZ,
    last_seen       TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_entity_type ON entity(type_name);
CREATE INDEX idx_rel_type ON relationship(type_name);
CREATE INDEX idx_rel_end1 ON relationship(end1_guid);
CREATE INDEX idx_rel_end2 ON relationship(end2_guid);
CREATE INDEX idx_rel_active ON relationship(is_active) WHERE is_active = true;
```

#### 3.3.2 预定义实体类型

```
基础类型：
├── Host          (主机/虚拟机/容器宿主)
├── IP            (IP 地址)
├── Service       (微服务)
├── Application   (应用实例)
├── Database      (数据库实例)
├── Middleware    (中间件: Redis/MQ/ES 等)
├── Endpoint      (API 端点: /api/v1/users)
├── K8sCluster    (Kubernetes 集群)
├── K8sNamespace  (K8s 命名空间)
├── K8sPod        (K8s Pod)
├── K8sService    (K8s Service)
├── NetworkDevice (网络设备)
└── AlertRule     (告警规则)

关系类型：
├── Host_runs         → Host ─→ Application
├── Service_calls     → Service ─→ Service        (静态配置 or 动态 Trace)
├── Service_depends   → Service ─→ Database/Middleware
├── Service_has       → Service ─→ Endpoint
├── K8sDeployed       → Service ─→ K8sPod
├── K8sInNamespace    → K8sPod ─→ K8sNamespace
├── Contains          → Host ─→ IP
└── Triggers          → AlertRule ─→ Service/Host
```

#### 3.3.3 ⭐ Trace 调用链融合 CMDB 设计 (核心创新)

**核心思路：** Trace 数据是"运行时自动发现的动态关系"，CMDB 是"人工维护的静态关系"，两者融合形成完整的实体关系图。

**关键决策：图计算独立为服务，不嵌入 ETL 管道。**

```
原因：
├── ETL 管道要保证高吞吐、低延迟（日志/指标处理）
├── 图计算是 CPU/IO 密集型操作（聚合、去重、融合）
├── 两者资源需求和扩展策略不同
├── 独立后可以单独扩缩容
└── 图服务故障不影响主数据管道
```

#### 整体架构：三层分离

```
              Trace 数据来源
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  Layer 1: ETL 管道 (Vector)                               │
│  职责：Trace 接收 → 解析 → 关系候选提取 → 推到队列         │
│  特点：高吞吐、无状态、不访问数据库                         │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Redis Streams  │  解耦队列
              │  (trace.rels)   │  消费者组 + ACK
              └────────┬────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
┌──────────────────────┐   ┌──────────────────────┐
│  Layer 2: 实时融合    │   │  Layer 3: 批量计算    │
│  (Real-time Merge)    │   │  (Batch Recompute)    │
│                      │   │                      │
│  频率：每条关系到达时  │   │  频率：每小时/每天     │
│  做法：增量更新        │   │  做法：全量重算        │
│                      │   │                      │
│  - 新关系→直接插入     │   │  - 重算 P99 延迟       │
│  - 已有关系→更新属性   │   │  - 清理过期关系        │
│  - 更新 last_seen     │   │  - 重新计算置信度       │
│  - 更新实时统计        │   │  - 生成拓扑快照        │
│                      │   │  - 检测拓扑变更         │
└──────────┬───────────┘   └──────────┬───────────┘
           │                          │
           ▼                          ▼
    ┌──────────────────────────────────────────┐
    │          PostgreSQL + AGE                 │
    │  实体节点 + 关系边 + 图计算                 │
    └──────────────────────────────────────────┘
```

#### Layer 1: ETL 管道中的 Trace 处理

Vector 管道只做**轻量级关系提取**，不做任何数据库操作：

```toml
# Vector 配置 - Trace 关系提取（无状态，不碰数据库）
[transforms.trace_extract_rels]
type = "remap"
inputs = ["otlp_traces"]
source = '''
  # 只提取调用方 span 的关系
  if .kind == "CLIENT" || .kind == "PRODUCER" {
    .rel_from = .resource["service.name"]
    .rel_to = .peer_service
    .rel_type = "calls"
    .span_name = .name
    .latency_ms = .duration_nanos / 1000000
    .protocol = .attributes["rpc.system"]
    .trace_id = .trace_id
  } else {
    abort  # 不是调用方 span，跳过
  }
'''

# 推到 Redis Streams，不做数据库写入
[sinks.redis_trace_rels]
type = "redis"
inputs = ["trace_extract_rels"]
url = "redis://localhost:6379"
key = "trace.relations"
data_type = "list"
```

#### Layer 2: 实时融合服务（独立进程）

```python
# graph_merge_service.py - 独立运行的服务

class GraphMergeService:
    """
    从 Redis Streams 消费 Trace 关系，增量更新图数据库。
    独立于 ETL 管道，可单独扩缩容。
    """
    
    def __init__(self):
        self.pg = PostgreSQLConnection()      # AGE 图存储
        self.redis = RedisStreams("trace.relations", "graph-merge-group")
        # 内存缓存：已知关系的指纹，减少数据库查询
        self.relation_cache = TTLCache(maxsize=100000, ttl=300)
    
    def run(self):
        while True:
            messages = self.redis.read(count=100, block=5000)
            # 批量处理，减少数据库事务次数
            batch = [self._parse(m) for m in messages]
            self._batch_merge(batch)
            self.redis.ack(messages)
    
    def _batch_merge(self, relations: List[RelationCandidate]):
        """
        批量融合，一次事务处理 N 条关系。
        比逐条写入性能提升 10x+。
        """
        with self.pg.transaction() as tx:
            for rel in relations:
                # 检查缓存
                cache_key = f"{rel.from_}:{rel.to_}:{rel.type}"
                if cache_key in self.relation_cache:
                    # 已知关系，只更新 last_seen + 实时统计
                    self._update_relation_stats(tx, rel)
                else:
                    # 未知关系，查库确认后创建
                    exists = self._check_relation_exists(tx, rel)
                    if exists:
                        self.relation_cache[cache_key] = True
                        self._update_relation_stats(tx, rel)
                    else:
                        self._create_relation(tx, rel)
                        self.relation_cache[cache_key] = True
                
                # 同时更新实体的 last_seen
                self._touch_entity(tx, rel.from_)
                self._touch_entity(tx, rel.to_)
    
    def _update_relation_stats(self, tx, rel):
        """
        实时更新关系属性（不做复杂聚合）
        复杂聚合交给批量计算层
        """
        tx.execute("""
            UPDATE relationship
            SET last_seen = now(),
                attributes = jsonb_set(attributes, '{last_latency_ms}', %s),
                attributes = jsonb_set(attributes, '{call_count}', 
                    (COALESCE(attributes->>'call_count', '0')::int + 1)::text::jsonb)
            WHERE end1_guid = (SELECT guid FROM entity WHERE name = %s)
              AND end2_guid = (SELECT guid FROM entity WHERE name = %s)
              AND type_name = %s
        """, [rel.latency_ms, rel.from_, rel.to_, rel.type])
```

#### Layer 3: 批量计算服务（定时任务）

```python
# graph_batch_recompute.py - 定时执行（cron 或独立调度）

class GraphBatchRecompute:
    """
    定期重算图数据，补充实时层算不出来的复杂指标。
    资源密集型，不影响实时管道。
    """
    
    def recompute(self):
        """
        每小时执行：
        1. 重算每个关系的 P50/P95/P99 延迟
        2. 重算调用频率 (calls/min)
        3. 检测过期关系（>N小时未见到）
        4. 生成拓扑快照
        5. 检测拓扑变更（与上次快照对比）
        """
        with self.pg.transaction() as tx:
            # 1. 重算延迟分布
            tx.execute("""
                WITH recent_traces AS (
                    SELECT * FROM trace_spans
                    WHERE timestamp > now() - interval '1 hour'
                )
                UPDATE relationship r SET attributes = jsonb_set(
                    attributes,
                    '{latency}',
                    jsonb_build_object(
                        'p50', percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms),
                        'p95', percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms),
                        'p99', percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms)
                    )
                )
                FROM recent_traces t
                WHERE r.end1_guid = t.source_entity
                  AND r.end2_guid = t.target_entity
            """)
            
            # 2. 检测过期关系
            tx.execute("""
                UPDATE relationship
                SET is_active = false
                WHERE is_active = true
                  AND last_seen < now() - interval '24 hours'
                  AND source = 'trace_discovered'
            """)
            
            # 3. 生成拓扑快照（存到独立表，用于变更检测）
            self._save_topology_snapshot(tx)
            
            # 4. 检测拓扑变更
            changes = self._diff_topology(tx)
            if changes:
                self._notify_topology_change(changes)
    
    def _diff_topology(self, tx) -> List[TopologyChange]:
        """
        对比当前拓扑与上次快照，发现：
        - 新增关系（新依赖）
        - 消失关系（停用的依赖）
        - 延迟突变（某条边延迟飙升）
        """
        tx.execute("""
            WITH current AS (
                SELECT e1.name as from_svc, e2.name as to_svc, 
                       r.attributes->>'latency'->>'p99' as p99
                FROM relationship r
                JOIN entity e1 ON r.end1_guid = e1.guid
                JOIN entity e2 ON r.end2_guid = e2.guid
                WHERE r.is_active = true
            ),
            previous AS (
                SELECT * FROM topology_snapshot
                WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM topology_snapshot)
            )
            SELECT * FROM (
                -- 新增
                SELECT c.*, 'added' as change_type
                FROM current c LEFT JOIN previous p
                  ON c.from_svc = p.from_svc AND c.to_svc = p.to_svc
                WHERE p.from_svc IS NULL
                UNION ALL
                -- 消失
                SELECT p.*, 'removed' as change_type
                FROM previous p LEFT JOIN current c
                  ON p.from_svc = c.from_svc AND p.to_svc = c.to_svc
                WHERE c.from_svc IS NULL
                UNION ALL
                -- 延迟突变 (>50% 增长)
                SELECT c.*, 'latency_spike' as change_type
                FROM current c JOIN previous p
                  ON c.from_svc = p.from_svc AND c.to_svc = p.to_svc
                WHERE c.p99::float > p.p99::float * 1.5
            ) changes
        """)
        return tx.fetchall()
```

#### 实时 vs 批量的职责划分

| 能力 | 实时层 (Layer 2) | 批量层 (Layer 3) |
|------|-----------------|-----------------|
| 新关系发现 | ✅ 立即插入 | ❌ 不负责 |
| 已有关系更新 last_seen | ✅ 实时更新 | ❌ 不负责 |
| 实时调用计数 (累加) | ✅ +1 | ❌ 不负责 |
| P50/P95/P99 延迟计算 | ❌ 太重 | ✅ 每小时重算 |
| 调用频率 (calls/min) | ❌ 需要窗口聚合 | ✅ 每小时重算 |
| 过期关系检测 | ❌ 不负责 | ✅ 每小时扫描 |
| 拓扑快照 | ❌ 不负责 | ✅ 每小时生成 |
| 拓扑变更检测 | ❌ 不负责 | ✅ 与上次快照对比 |
| 新实体自动创建 | ✅ 即时创建 | ❌ 不负责 |

#### 图查询（读路径独立）

```cypher
-- 实时查询：当前拓扑（从关系表直接查，不实时算图）
MATCH p=(a:Service {name: 'order-service'})-[:calls*1..3]->(b:Service)
WHERE ALL(r IN relationships(p) WHERE r.is_active = true)
RETURN p

-- 影响分析：某个服务挂了会影响哪些下游
MATCH (failed:Service {name: 'payment-service'})-[:calls*1..5]->(downstream:Service)
WHERE ALL(r IN relationships(failure_path) WHERE r.is_active = true)
RETURN DISTINCT downstream.name, downstream.attributes->>'team' as owner

-- 延迟热力图：找出拓扑中延迟最高的边
MATCH (a:Service)-[r:calls]->(b:Service)
WHERE r.is_active = true
RETURN a.name, b.name, r.attributes->'latency'->>'p99' as p99_ms
ORDER BY p99_ms DESC
LIMIT 20
```

#### 服务扩容策略

```
百台规模：
├── 实时融合服务: 1 实例 (单进程消费)
├── 批量计算服务: 1 实例 (定时任务)
└── PostgreSQL: 单主

千台规模：
├── 实时融合服务: 2-3 实例 (Redis Streams 消费者组负载均衡)
├── 批量计算服务: 1 实例 (计算密集，可按租户/业务线分片)
└── PostgreSQL: 一主多从 (读写分离)
```

#### 融合策略总结：

| 场景 | 动作 | 置信度 | 人工确认 |
|------|------|--------|----------|
| CMDB 有 + Trace 确认 | 更新属性，刷新 last_seen | 1.0 | 不需要 |
| CMDB 无 + Trace 发现 | 创建新关系，标记 source=trace | 0.9 | 需要 |
| CMDB 有 + Trace 未见(超时) | 标记 is_active=false | — | 需要 |
| Trace 发现新服务 | 自动创建实体 | 0.7 | 需要 |

**图存储方案：**

使用 PostgreSQL AGE (Apache Graph Extension)，在 PostgreSQL 上直接加图查询能力：

```cypher
-- 查询 serviceA 的完整调用链（3层深度）
MATCH p=(a:Service {name: 'serviceA'})-[:calls*1..3]->(b:Service)
RETURN p

-- 查询某个告警的影响范围
MATCH (alert:AlertRule)-[:triggers]->(svc:Service)-[:calls*1..5]->(downstream:Service)
RETURN svc.name, downstream.name

-- 找出调用关系中延迟最高的路径
MATCH p=(a:Service)-[:calls*1..3]->(b:Service)
WHERE ALL(r IN relationships(p) WHERE r.latency_p99 > 100)
RETURN p
```

### 3.4 数据存储层

| 存储 | 用途 | 选型 | 说明 |
|------|------|------|------|
| 日志存储 | 海量日志压缩+搜索 | **ClickHouse** | 列式压缩，日志场景最优 |
| OLAP 分析 | 多维聚合+报表 | **Apache Doris** | MySQL 兼容，实时导入 |
| CMDB 核心 | 实体+关系+图查询 | **PostgreSQL + AGE** | ACID + 图扩展，统一管理 |
| 向量存储 | 日志 Embedding | **pgvector** | PostgreSQL 扩展，无需额外组件 |
| 事件队列 | 异步解耦 | **Redis Streams** | 轻量，Python 生态好 |
| 缓存 | 热数据+查询缓存 | **Redis** | 实体查询缓存 |

**为什么 PostgreSQL 为核心？**
- AGE 图扩展 = PostgreSQL + 图数据库，不需要单独的 Neo4j
- pgvector = PostgreSQL + 向量数据库，不需要单独的 Milvus
- 一个 PostgreSQL 实例承担 CMDB + 图查询 + 向量检索，运维简单
- 千台规模用单主 + 读副本足够

### 3.5 AI 诊断引擎（智能运维层）

**目标：用户对任意对象提出问题，AI 自动关联多维数据，推导根因并按概率排序呈现。**

#### 3.5.1 整体架构

```
用户自然语言提问
"payment-service 最近响应变慢了，什么原因？"
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI 诊断引擎 (Orchestrator)                     │
│                                                                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │ 1. 意图   │→│ 2. 数据   │→│ 3. 关联   │→│ 4. 根因   │   │
│  │   理解    │   │   采集    │   │   分析    │   │   推理    │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘   │
│       │               │               │               │        │
│       ▼               ▼               ▼               ▼        │
│  识别对象         并行拉取          时序对齐         多因排序     │
│  时间范围         多源数据          异常关联         概率计算     │
│  分析维度         指标/日志/        拓扑穿透         证据链       │
│                  Trace/告警        维度交叉         可信度       │
│                                                                 │
│                              ▼                                   │
│                    ┌─────────────────┐                          │
│                    │  5. 智能呈现     │                          │
│                    │  自然语言总结    │                          │
│                    │  + 关联图表      │                          │
│                    │  + 建议操作      │                          │
│                    └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.5.x 可插拔大脑架构（Swappable Brain）

**设计原则：AI 推理层与业务逻辑层完全解耦。用户可以随时切换"大脑"，不改代码。**

```
┌───────────────────────────────────────────────────────────────┐
│                    AI 诊断引擎 (Orchestrator)                   │
│                                                               │
│  业务逻辑层（不变）                                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │
│  │ 意图理解   │  │ 数据采集   │  │ 关联分析   │  │ 根因推理   │ │
│  │ (模板)    │  │ (工具)    │  │ (算法)    │  │ (算法)    │ │
│  └─────┬─────┘  └───────────┘  └───────────┘  └───────────┘ │
│        │                                                      │
│        │ 调用 LLM                                              │
│        ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Brain Adapter (大脑适配层)                   │  │
│  │                                                         │  │
│  │  统一接口: chat(system, messages, tools) → response     │  │
│  │                                                         │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  │  │
│  │  │ OpenAI  │  │ Claude  │  │ 通义千问 │  │ 本地模型  │  │  │
│  │  │ GPT-4o  │  │ Opus/S  │  │ Qwen-Max │  │ Llama3   │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └──────────┘  │  │
│  │                                                         │  │
│  │  用户可在界面上切换:  "大脑: GPT-4o → Claude Opus"       │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

**统一 Brain Adapter 接口：**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BrainAdapter(ABC):
    """
    所有 LLM 提供商实现此接口。
    AI 诊断引擎只调用 BrainAdapter，不关心具体是哪个模型。
    """
    
    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,    # Function Calling
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> ChatResponse:
        """统一聊天接口"""
        ...
    
    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """统一向量化接口（用于日志 Embedding）"""
        ...


# ---- 各厂商实现 ----

class OpenAIBrain(BrainAdapter):
    provider = "openai"
    models = ["gpt-4o", "gpt-4o-mini", "o1", "o3"]
    
    async def chat(self, system_prompt, messages, tools=None, **kwargs):
        response = await openai_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=tools,
            temperature=kwargs.get("temperature", 0.1),
        )
        return self._to_response(response)

class ClaudeBrain(BrainAdapter):
    provider = "anthropic"
    models = ["claude-opus-4-20250514", "claude-sonnet-4-20250514"]
    
    async def chat(self, system_prompt, messages, tools=None, **kwargs):
        response = await anthropic_client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=messages,
            tools=tools,
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return self._to_response(response)

class QwenBrain(BrainAdapter):
    provider = "alibaba"
    models = ["qwen-max", "qwen-plus", "qwen-turbo"]
    
    async def chat(self, system_prompt, messages, tools=None, **kwargs):
        # 兼容 OpenAI 接口的阿里云 DashScope
        response = await dashscope_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=tools,
        )
        return self._to_response(response)

class LocalBrain(BrainAdapter):
    provider = "local"
    models = ["llama3-70b", "qwen2.5-72b", "deepseek-v3"]
    
    async def chat(self, system_prompt, messages, tools=None, **kwargs):
        # vLLM / Ollama / TGI 本地推理
        response = await local_client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
        )
        return self._to_response(response)
```

**大脑注册与切换：**

```sql
-- 大脑配置表（租户级）
CREATE TABLE brain_config (
    config_id       UUID PRIMARY KEY,
    tenant_id       VARCHAR(128),
    
    -- 大脑选择
    provider        VARCHAR(64),        -- openai / anthropic / alibaba / local
    model           VARCHAR(128),       -- gpt-4o / claude-opus / qwen-max / llama3
    
    -- 场景级配置（不同任务可以用不同大脑）
    use_for         VARCHAR(64),        -- diagnosis / chat / embedding / parsing
    fallback_provider VARCHAR(64),      -- 主模型不可用时的降级
    
    -- API 配置
    api_key_encrypted TEXT,             -- 加密存储的 API Key
    api_base_url    VARCHAR(512),       -- 自定义端点（私有部署用）
    
    -- 参数
    temperature     FLOAT DEFAULT 0.1,
    max_tokens      INT DEFAULT 4096,
    rate_limit_rpm  INT,                -- 每分钟请求限制
    
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 示例配置：
-- tenant=支付团队, 场景=diagnosis, 大脑=GPT-4o (主力), 降级=Claude Sonnet
-- tenant=支付团队, 场景=embedding, 大脑=text-embedding-3-small
-- tenant=数据团队, 场景=chat, 大脑=qwen-max (成本低)
```

**大脑路由决策：**

```python
class BrainRouter:
    """
    根据场景、租户配置、模型可用性，智能路由到最合适的大脑。
    """
    
    async def route(self, tenant: str, use_for: str) -> BrainAdapter:
        # 1. 查租户配置
        config = await db.get_brain_config(tenant, use_for)
        
        # 2. 尝试主模型
        brain = self._get_brain(config.provider, config.model)
        if await brain.health_check():
            return brain
        
        # 3. 主模型不可用 → 降级到 fallback
        logger.warning(f"Brain {config.model} unavailable, falling back to {config.fallback_provider}")
        fallback = self._get_brain(config.fallback_provider, config.fallback_model)
        if await fallback.health_check():
            return fallback
        
        # 4. 全部不可用 → 使用平台默认模型
        return self._get_default_brain()
```

**场景级大脑配置：**

| 场景 | 推荐模型 | 原因 |
|------|---------|------|
| 意图理解 | GPT-4o-mini / Qwen-Turbo | 轻量任务，速度快成本低 |
| 根因推理 | GPT-4o / Claude Opus | 需要强推理能力 |
| 日志解析 | Qwen-Max / GPT-4o-mini | 结构化提取，不需要最强模型 |
| 向量 Embedding | text-embedding-3-small / bge-m3 | 专用嵌入模型 |
| 诊断报告生成 | Claude Sonnet / GPT-4o | 长文本生成质量好 |
| 实时问答 | GPT-4o-mini / Qwen-Turbo | 低延迟优先 |

**用户界面（大脑切换）：**

```
⚙️ AI 设置
┌──────────────────────────────────────────────┐
│ 🧠 当前大脑: GPT-4o                          │
│                                              │
│ 场景              模型              操作      │
│ ──────────────── ──────────────── ──────    │
│ 智能诊断          GPT-4o           [切换]    │
│ 智能问答          Qwen-Max         [切换]    │
│ 日志解析          GPT-4o-mini      [切换]    │
│ 向量嵌入          bge-m3           [切换]    │
│                                              │
│ 💰 本月 Token 消耗: 12.5M tokens / ¥380     │
│ 📊 各场景调用统计:                            │
│   诊断: 156次 | 问答: 892次 | 解析: 12.3K次   │
└──────────────────────────────────────────────┘
```

**平台自建 vs 第三方的取舍：**

| 方案 | 优点 | 缺点 | 适用 |
|------|------|------|------|
| 全用第三方 | 零运维，随时用最新模型 | 成本高，数据出境 | 初期/中小规模 |
| 全自建 | 数据不出域，成本可控 | 需 GPU，模型更新慢 | 金融/政府等合规场景 |
| **混合（推荐）** | 敏感场景自建，其他第三方 | 配置复杂 | 大多数场景 |

#### 3.5.2 五步诊断流水线

**Step 1: 意图理解（NLU）**

```python
# LLM 解析用户问题，提取结构化诊断意图
class DiagnosticIntent:
    target_entity: str          # "payment-service"
    entity_type: str            # "Service"
    time_range: TimeRange       # "最近 1 小时"
    question_type: str          # "performance" / "error" / "availability"
    dimensions: List[str]       # ["metrics", "logs", "traces", "topology"]
    comparison: Optional[str]   # "vs 昨天同期" / "vs 上周"

# 用户: "payment-service 最近响应变慢了"
# → Intent(target="payment-service", type="performance", 
#           time_range="1h", dimensions=["metrics","traces","logs"])
```

**Step 2: 多源数据并行采集**

```
诊断意图
    │
    ├──→ [Metrics Agent]    查该服务 CPU/内存/延迟/错误率趋势
    │    Text-to-PromQL
    │
    ├──→ [Logs Agent]       查该服务最近错误日志、异常堆栈
    │    Text-to-SQL
    │
    ├──→ [Trace Agent]      查该服务调用链，找最慢的 Span
    │    Trace Query API
    │
    ├──→ [CMDB Agent]       查该服务的上下游依赖、部署拓扑
    │    Graph Query API
    │
    ├──→ [Alert Agent]      查相关告警历史
    │    Alert Query API
    │
    └──→ [Vector Agent]     查历史上类似的故障案例
         Similarity Search
```

**Step 3: 关联分析引擎**

```python
class CorrelationEngine:
    """
    将多源数据按时间线对齐，发现异常关联模式。
    """
    
    def analyze(self, data: MultiSourceData) -> List[Correlation]:
        correlations = []
        
        # 1. 时序对齐：所有指标按同一时间窗口对齐
        aligned = self.time_align(data.metrics, data.logs, data.traces, 
                                   data.alerts, bucket='1min')
        
        # 2. 异常检测：每条时间线找异常点
        anomalies = self.detect_anomalies(aligned)
        
        # 3. 关联分析：找同时发生的异常
        #    "服务延迟飙升" + "数据库慢查询增多" + "磁盘 IO 打满"
        #    → 三者在同一时刻发生 → 高度相关
        for t in anomalies.time_windows:
            concurrent_anomalies = anomalies.at(t)
            if len(concurrent_anomalies) >= 2:
                correlation = self.compute_correlation(concurrent_anomalies)
                correlations.append(correlation)
        
        # 4. 拓扑关联：沿依赖图传播异常
        #    "数据库慢" → "依赖该数据库的所有服务都受影响"
        topology_impact = self.propagate_along_topology(
            source=data.target_entity,
            cmdb_graph=data.topology,
            anomalies=anomalies
        )
        correlations.extend(topology_impact)
        
        # 5. 历史相似：向量搜索历史上类似的异常模式
        similar_cases = self.vector_search_similar(anomalies)
        correlations.extend(similar_cases)
        
        return correlations
```

**Step 4: 根因推理（概率排序）**

```python
class RootCauseAnalyzer:
    """
    基于关联分析结果，用因果推理算法排序根因。
    输出：候选根因列表，按概率降序排列。
    """
    
    def infer(self, correlations: List[Correlation]) -> List[RootCause]:
        candidates = []
        
        # 算法 1：拓扑因果链推理
        # 沿 CMDB 拓扑图向上游追溯，找到最底层的异常
        # 原则：下游异常通常是结果，上游异常更可能是原因
        topology_causes = self.topology_causal_chain(correlations)
        
        # 算法 2：时间优先性
        # 先发生的异常更可能是原因
        temporal_causes = self.temporal_precedence(correlations)
        
        # 算法 3：贝叶斯概率
        # 基于历史故障数据，计算 P(根因 | 观察到的异常)
        bayesian_causes = self.bayesian_inference(correlations)
        
        # 算法 4：历史相似案例匹配
        # "历史上类似症状 80% 是磁盘问题"
        historical_causes = self.historical_pattern_match(correlations)
        
        # 综合打分
        for cause in set(topology_causes + temporal_causes + 
                         bayesian_causes + historical_causes):
            score = self.composite_score(
                cause,
                topology_score=topology_causes.get(cause, 0),
                temporal_score=temporal_causes.get(cause, 0),
                bayesian_score=bayesian_causes.get(cause, 0),
                historical_score=historical_causes.get(cause, 0),
            )
            candidates.append(RootCause(
                entity=cause.entity,
                description=cause.description,
                probability=score,          # 0-100%
                evidence=cause.evidence,     # 支撑证据链
                similar_cases=cause.history, # 历史相似案例
                suggested_actions=cause.fixes,# 建议操作
            ))
        
        # 按概率降序返回
        return sorted(candidates, key=lambda x: x.probability, reverse=True)
```

**Step 5: 智能呈现**

```python
# LLM 生成诊断报告，包含自然语言总结 + 图表引用 + 操作建议

DIAGNOSTIC_REPORT_PROMPT = """
你是一个资深运维专家。基于以下分析结果，生成诊断报告。

目标对象: {entity}
分析时间: {time_range}

关联分析结果:
{correlations}

根因排序（按概率）:
{root_causes}

请输出：
1. 一句话总结问题
2. 最可能的根因（含概率和支撑证据）
3. 其他可能原因（降序排列）
4. 建议的排查步骤
5. 建议引用哪些图表（指定 metrics/logs/traces 查询）
"""
```

#### 3.5.3 根因概率计算模型

```python
# 综合评分公式
def composite_score(cause, weights):
    """
    综合 4 种算法的置信度，加权计算最终概率。
    """
    return (
        weights.topology    * cause.topology_score    # 拓扑位置 (上游优先)
      + weights.temporal    * cause.temporal_score    # 时间优先性 (先发生优先)
      + weights.bayesian    * cause.bayesian_score    # 贝叶斯推断 (历史统计)
      + weights.historical  * cause.historical_score  # 历史相似 (向量匹配)
    )

# 默认权重（可通过反馈学习优化）
DEFAULT_WEIGHTS = {
    'topology':   0.35,   # 拓扑因果链是最强信号
    'temporal':   0.20,   # 时间先后是重要参考
    'bayesian':   0.25,   # 历史统计规律
    'historical': 0.20,   # 相似案例
}
```

#### 3.5.4 诊断结果展示

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 诊断报告：payment-service 响应变慢
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 概述
最近 1 小时 payment-service P99 延迟从 80ms 上升到 450ms，
错误率从 0.1% 上升到 2.3%。影响下游 order-service 和 user-service。

🎯 根因排序

  🥇 [78%] MySQL 主库磁盘 IO 饱和
     证据：
     • MySQL 慢查询从 2/min → 45/min (同时发生 ↑)
     • 磁盘 IO util 从 35% → 92% (时间优先 ↑)
     • 拓扑：payment-service → MySQL 主库 (上游依赖 ↑)
     • 历史：3 月 15 日相同症状，最终确认是磁盘问题 (相似案例 ↑)
     图表：[查看磁盘IO趋势] [查看慢查询分布]

  🥈 [15%] order-service 调用量突增导致排队
     证据：
     • order-service → payment-service QPS 从 200/s → 850/s
     • 线程池 active 从 8 → 64 (满)
     图表：[查看调用QPS趋势] [查看线程池状态]

  🥉 [5%] 网络抖动
     证据：
     • payment-service ↔ MySQL RTT 有 3 次 >50ms
     图表：[查看网络延迟趋势]

📎 相关图表
  • [服务延迟趋势图]  P99: 80ms → 450ms
  • [错误率趋势图]    0.1% → 2.3%
  • [调用拓扑图]      payment → MySQL (延迟标红)
  • [关联时间线]      指标 + 日志 + 告警对齐展示
  • [相似历史案例]    2026-03-15 相同故障 → 根因：磁盘 IO

🔧 建议操作
  1. 立即：检查 MySQL 磁盘 IO (iotop / iostat)
  2. 短期：kill 慢查询，扩容磁盘 IOPS
  3. 长期：考虑读写分离，或迁移到高性能存储
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### 3.5.5 持续学习机制

```
每次诊断完成
     │
     ▼
┌──────────────────┐
│ 用户反馈          │
│ • 根因是否正确？  │
│ • 实际根因是什么？│
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│ 反馈写入 learning_feedback 表 │
│ → 调整算法权重                │
│ → 丰富历史案例库              │
│ → 更新向量索引                │
└──────────────────────────────┘
```

```sql
-- 诊断学习反馈表
CREATE TABLE diagnostic_feedback (
    id              UUID PRIMARY KEY,
    diagnosis_id    UUID,              -- 诊断报告 ID
    target_entity   VARCHAR(256),
    predicted_cause TEXT,              -- AI 预测的根因
    predicted_prob  FLOAT,             -- 预测概率
    actual_cause    TEXT,              -- 实际根因（用户反馈）
    is_correct      BOOLEAN,
    feedback_notes  TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

#### 3.5.6 向量检索场景（基础能力）

| 场景 | 输入 | 输出 |
|------|------|------|
| 日志相似搜索 | 一条错误日志文本 | 历史相似日志 + 当时的解决方案 |
| 告警聚合 | 一批告警事件 | 自动合并相似告警，输出聚合后数量 |
| 故障案例匹配 | 当前异常模式的向量表示 | 最相似的历史故障 + 根因 + 处理过程 |
| Runbook 推荐 | 告警描述 | 匹配最相关的运维手册 |

#### 3.5.7 告警体系重构：从业务风险度出发

**传统告警的问题：**

```
传统思维：IT 严重度驱动
├─ 磁盘使用率 95% → P1 告警！
├─ MySQL 慢查询 >1s → P2 告警！
├─ CPU 90% 持续 5min → P2 告警！
└─ 结果：运维疲于奔命，大部分告警对用户无感

问题本质：
├─ 技术严重 ≠ 业务影响
├─ 磁盘 95% 但用户完全无感 → 为什么要半夜叫人？
├─ 前端 CDN 故障 → 用户白屏，投诉涌入 → 但传统监控不告警！
└─ 告警应该回答："用户会受影响吗？影响多大？"
```

**新思维：业务风险度 = 技术严重度 × 传播距离 × 影响面**

```
                 用户
                  │
              ┌───▼───┐
              │  前端   │  ← 最近用户，风险度最高
              │ CDN/WAF │    一挂用户全无感
              └───┬────┘
                  │
              ┌───▼────┐
              │  网关   │  ← 用户请求入口
              │ Gateway │    一挂全站不可用
              └───┬────┘
                  │
          ┌───────┼───────┐
          ▼       ▼       ▼
       Service  Service  Service  ← 核心业务层
       (支付)   (订单)   (用户)     单个挂→部分功能不可用
          │       │       │
          ▼       ▼       ▼
       MySQL   Redis    MQ       ← 中间件层
                  │                用户不直连
                  ▼               有缓存兜底，用户可能无感
              物理机/磁盘          ← 最底层
                                用户最远，风险度最低
```

#### 风险度计算模型

```python
class AlertRiskCalculator:
    """
    计算告警的业务风险度，而非仅看技术严重度。
    """
    
    def calculate_risk(self, alert: Alert) -> AlertRisk:
        # 1. 技术严重度 (0-100) - 传统告警的等级
        tech_severity = self._calc_severity(alert)
        
        # 2. 传播距离 (衰减系数) - 离用户越远，衰减越大
        propagation_distance = self._calc_distance_to_user(alert.entity)
        # 前端/网关: 1.0
        # 核心服务:  0.7
        # 中间件:    0.4
        # 基础设施:  0.2
        
        # 3. 影响面 (放大系数) - 影响多少用户/多少业务
        blast_radius = self._calc_blast_radius(alert.entity)
        # 核心链路全挂: 3.0
        # 单服务降级:   1.0
        # 单实例异常:   0.3
        
        # 4. 综合风险度
        risk_score = tech_severity * propagation_distance * blast_radius
        
        return AlertRisk(
            score=risk_score,
            level=self._risk_level(risk_score),  # P0-P4
            tech_severity=tech_severity,
            business_impact=self._describe_impact(alert, blast_radius),
            user_impact=self._describe_user_impact(alert),
        )
    
    def _calc_distance_to_user(self, entity: Entity) -> float:
        """
        通过 CMDB 拓扑计算该实体到用户的最短路径。
        路径越短，风险度越高。
        """
        # 查询 CMDB 图
        path_to_user = self.cmdb.shortest_path_to(
            entity, 
            target_type="UserEndpoint"  # 用户接入点
        )
        
        if path_to_user is None:
            return 0.1  # 拓扑找不到，默认低风险
        
        hops = len(path_to_user)
        # 1跳(前端)→1.0, 2跳(网关)→0.9, 3跳(服务)→0.7, 
        # 4跳(中间件)→0.4, 5跳+→0.2
        return max(0.2, 1.0 - (hops - 1) * 0.2)
    
    def _calc_blast_radius(self, entity: Entity) -> float:
        """
        通过 CMDB 拓扑计算影响面。
        向下遍历：这个实体挂了会影响多少下游。
        """
        downstream = self.cmdb.downstream_count(entity, depth=5)
        
        if downstream > 20:
            return 3.0    # 影响大量服务
        elif downstream > 5:
            return 2.0
        elif downstream > 0:
            return 1.0
        else:
            return 0.3    # 叶子节点
```

#### 告警风险度 vs 严重度 对比

| 告警事件 | 技术严重度 | 传播距离 | 影响面 | **业务风险度** | 处理策略 |
|---------|-----------|---------|--------|--------------|---------|
| CDN 节点故障 | 中 | **最近 (1.0)** | **全站 (3.0)** | **🔴 极高** | 立即处理 |
| 网关 502 错误率 5% | 高 | 近 (0.9) | 全站 (3.0) | **🔴 极高** | 立即处理 |
| 支付服务 P99>500ms | 高 | 中 (0.7) | 支付链路 (2.0) | **🟠 高** | 15min 内 |
| 订单服务 CPU 80% | 中 | 中 (0.7) | 订单链路 (1.5) | **🟡 中** | 工作时间 |
| MySQL 慢查询 >1s | 高 | **远 (0.4)** | 有缓存 (0.5) | **🟢 低** | 工作时间 |
| 磁盘使用率 95% | 高 | **最远 (0.2)** | 单机 (0.3) | **⚪ 极低** | 计划扩容 |
| 物理机温度高 | 中 | 最远 (0.2) | 单机 (0.3) | **⚪ 极低** | 计划巡检 |

**关键洞察：MySQL 慢查询技术严重度"高"，但业务风险度"低"（用户有缓存无感）；
CDN 故障技术严重度"中"，但业务风险度"极高"（用户直接白屏）。**

#### 告警展示：业务视角排序

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 告警中心 — 按业务风险度排序
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 P0 - 极高风险 (用户直接感知)
  #1 CDN 华东节点不可用                    14:23 触发
     风险度: 95 | 影响: 华东用户白屏, 预估影响 50万用户
     技术: CDN健康检查失败 | 业务: 全站不可用
     
  #2 网关 502 率 5%                       14:25 触发
     风险度: 87 | 影响: 5% 用户请求失败
     技术: upstream timeout | 业务: 部分功能不可用

🟠 P1 - 高风险 (用户体验下降)
  #3 支付服务 P99=800ms                    14:28 触发
     风险度: 72 | 影响: 支付超时率上升, 预估损失 ¥XX/分钟
     技术: DB 慢查询 | 业务: 支付转化率可能下降

🟡 P2 - 中风险 (后台异常)
  #4 订单服务 CPU 85%                       14:20 触发
     风险度: 45 | 影响: 暂无用户感知, 扩容后可能缓解
     技术: 流量突增 | 业务: 目前无感

⚪ P4 - 低风险 (IT 维护类, 不需要即时处理)
  #5 MySQL 慢查询 15条/min                  14:15 触发
     风险度: 12 | 影响: 用户无感 (有Redis缓存)
     建议: 工作时间优化索引即可
     
  #6 主机 i-0xabc 磁盘 95%                 14:00 触发
     风险度: 8 | 影响: 用户无感
     建议: 计划扩容, 下周维护窗口处理

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 今日概览: P0×2 | P1×1 | P2×3 | P3×5 | P4×12
   用户可感知告警: 3 条 | 纯 IT 维护: 20 条
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### 告警通知分级

| 风险等级 | 通知方式 | 时间要求 | 通知对象 |
|---------|---------|---------|---------|
| P0 极高 | 电话 + 短信 + 飞书 | 立即 | On-Call + 管理层 |
| P1 高 | 飞书 + 短信 | 5 分钟内 | On-Call |
| P2 中 | 飞书 | 30 分钟内 | 相关负责人 |
| P3 低 | 邮件 + 飞书汇总 | 当天 | 相关负责人 |
| P4 极低 | 周报汇总 | 不通知 | 计划排期 |

#### 告警收敛与抑制

```
传统问题：10 台机器磁盘告警 → 10 条告警 → 告警风暴

新思维：
├─ 相同根因合并：10 台机器磁盘告警 → "磁盘空间不足影响 10 台主机"
├─ 因果链抑制：MySQL 慢查询 → 上游服务超时 → 不要重复告警
│   (只告警根因，不告警下游连锁反应)
├─ 风险度抑制：P4 告警不触发夜间通知
└─ 降噪：已知问题(维护中) → 自动静默
```

```sql
-- 告警表设计（含风险度）
CREATE TABLE alert (
    alert_id        UUID PRIMARY KEY,
    
    -- 来源
    source          VARCHAR(64),         -- rule_engine / anomaly_detection / user_report
    rule_id         UUID,
    
    -- 实体
    entity_guid     UUID REFERENCES entity(guid),
    entity_name     VARCHAR(512),
    
    -- 技术维度
    tech_severity   INT,                 -- 0-100, 技术严重度
    metric_name     VARCHAR(256),
    metric_value    DOUBLE PRECISION,
    threshold       DOUBLE PRECISION,
    
    -- 业务维度 (新增)
    risk_score      INT,                 -- 0-100, 业务风险度
    risk_level      VARCHAR(8),          -- P0/P1/P2/P3/P4
    propagation_dist FLOAT,              -- 到用户的传播距离
    blast_radius    FLOAT,               -- 影响面
    user_impact_desc TEXT,               -- "华东用户白屏, 影响50万用户"
    business_impact_desc TEXT,           -- "支付转化率预计下降20%"
    
    -- 关联
    trace_id        VARCHAR(64),         -- 关联的 trace
    correlated_alerts UUID[],            -- 同因合并的告警 ID 列表
    root_cause_alert UUID,               -- 因果链抑制：指向根因告警
    
    -- 状态
    status          VARCHAR(16),         -- firing / resolved / suppressed / merged
    fired_at        TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    
    -- 通知
    notified_channels TEXT[],            -- 已通知的渠道
    acknowledged_by  VARCHAR(128),       -- 确认人
    acknowledged_at  TIMESTAMPTZ
);

-- 索引：按风险度排序查询活跃告警
CREATE INDEX idx_alert_active_risk ON alert(status, risk_level, risk_score DESC)
    WHERE status = 'firing';
```

### 3.6 API 层

**选型：FastAPI (Python)**

```
/api/v1/
├── /cmdb/
│   ├── /entities          CRUD + 批量导入
│   ├── /entities/:id/relations  实体关系查询
│   ├── /types             类型定义管理
│   ├── /topology          拓扑图数据
│   └── /enrich            日志实体关联接口
├── /logs/
│   ├── /search            日志搜索
│   ├── /query             SQL 查询
│   └── /aggregation       聚合统计
├── /metrics/
│   ├── /query             指标查询(代理 PromQL)
│   └── /range             范围查询
├── /traces/
│   ├── /search            Trace 搜索
│   └── /:traceId          Trace 详情
├── /ai/
│   ├── /chat              自然语言查询
│   ├── /similar-logs      日志相似搜索
│   └── /root-cause        根因分析
└── /alerts/
    ├── /rules              告警规则管理
    ├── /active             活跃告警
    └── /history            告警历史
```

### 3.7 前端

**选型：React + Ant Design Pro + AntV G6 (图可视化)**

核心页面：
1. **CMDB 拓扑图** — AntV G6 力导向图，展示服务依赖 + 关系类型
2. **日志查询** — SQL 编辑器 + 表格 + 图表展示
3. **监控大盘** — 可配置 Dashboard（图表、表格、告警列表）
4. **智能问答** — Chat UI，自然语言查询
5. **Trace 查看** — 火焰图 + 时序图

---

### 3.8 多租户与权限控制

**核心问题：** 平台服务多个团队/业务线，如何隔离数据、控制访问？

#### 租户模型

```
租户 (Tenant)
├── 团队 (Team)
│   ├── 角色 (Role)
│   │   └── 用户 (User)
│   └── 管理的实体范围
│       ├── 标签选择器: labels.business_line IN ('支付', '交易')
│       └── 标签选择器: labels.env = 'production'
└── 数据隔离边界
    ├── CMDB 实体：按标签过滤
    ├── 日志：按 labels.tenant 过滤
    └── 指标：按标签过滤
```

#### 两种隔离策略对比

| 策略 | 实现方式 | 优点 | 缺点 | 适用场景 |
|------|---------|------|------|---------|
| **标签隔离** | 所有数据加 `labels.tenant`，查询时 WHERE 过滤 | 实现简单，共享存储 | 隔离不彻底，有越界风险 | 内部平台，信任度高 |
| **Schema 隔离** | 每租户独立 DB schema | 隔离彻底 | 运维复杂，扩租户要加 schema | 对外 SaaS |

**推荐：标签隔离 + RBAC**（运维平台通常内部使用，信任度高）。

#### RBAC 权限模型

```sql
-- 角色定义
CREATE TABLE role (
    role_id     UUID PRIMARY KEY,
    role_name   VARCHAR(64) UNIQUE,    -- admin / operator / viewer / developer
    description TEXT,
    permissions JSONB                   -- 细粒度权限
);

-- 权限结构示例
-- {
--   "cmdb": {"read": true, "write": true, "delete": false},
--   "logs": {"read": true, "query": true, "export": false},
--   "metrics": {"read": true, "query": true},
--   "traces": {"read": true},
--   "ai": {"chat": true, "diagnose": true},
--   "alerts": {"read": true, "manage": false},
--   "admin": {"users": false, "tenants": false, "system": false}
-- }

-- 用户-角色-数据范围
CREATE TABLE user_role_binding (
    user_id         UUID REFERENCES users(id),
    role_id         UUID REFERENCES role(role_id),
    tenant_id       VARCHAR(128),           -- 所属租户
    data_scope      JSONB,                  -- 数据访问范围
    -- data_scope 示例:
    -- {"labels": {"business_line": ["支付","交易"], "env": ["prod"]}}
    -- 含义: 该用户只能访问 business_line 为支付或交易，且 env 为 prod 的数据
    PRIMARY KEY (user_id, role_id, tenant_id)
);
```

#### 查询层租户过滤（中间件）

```python
# FastAPI 中间件：自动注入租户过滤条件
class TenantFilterMiddleware:
    """
    所有查询自动附加租户标签过滤，用户无感知。
    """
    async def __call__(self, request, call_next):
        user = get_current_user(request)
        scope = user.data_scope  # {"labels": {"tenant": "支付团队"}}
        
        # 注入过滤条件到请求上下文
        request.state.tenant_filter = scope
        response = await call_next(request)
        return response

# 日志查询自动附加过滤
@app.get("/api/v1/logs/search")
async def search_logs(request: Request, query: LogQuery):
    tenant_filter = request.state.tenant_filter
    # 自动拼接: WHERE labels @> '{"tenant":"支付团队"}'
    query.filters.update(tenant_filter.get("labels", {}))
    return await log_service.search(query)
```

---

### 3.9 数据生命周期管理

**核心问题：** 千台规模日志每天 TB 级增长，如何控制存储成本？

#### 数据分层存储策略

```
数据产生
   │
   ▼
┌──────────────────────────────────────────────────────┐
│  HOT (0-7天)     全量存储，SSD，毫秒级查询            │
│  ClickHouse SSD  │  PostgreSQL SSD  │  Doris SSD     │
├──────────────────────────────────────────────────────┤
│  WARM (7-30天)   全量存储，HDD，秒级查询              │
│  ClickHouse HDD  │  降精度聚合 (1min → 5min)          │
├──────────────────────────────────────────────────────┤
│  COLD (30-365天) 采样存储 / 对象存储，十秒级查询       │
│  S3/OSS 归档     │  保留 1% 采样 + 全量错误日志       │
├──────────────────────────────────────────────────────┤
│  ARCHIVE (>1年)  仅合规审计需要的，压缩归档            │
│  冷存储          │  可查询但分钟级响应                 │
└──────────────────────────────────────────────────────┘
```

#### 生命周期管理表

```sql
CREATE TABLE data_lifecycle_policy (
    policy_id       UUID PRIMARY KEY,
    data_type       VARCHAR(64),        -- logs / metrics / traces / alerts
    tenant_id       VARCHAR(128),       -- 租户（可覆盖全局策略）
    
    -- 各阶段策略
    hot_retention_days    INT DEFAULT 7,
    warm_retention_days   INT DEFAULT 30,
    cold_retention_days   INT DEFAULT 365,
    archive_retention_days INT DEFAULT 1095,  -- 3年
    
    -- 降精度规则
    warm_aggregation      VARCHAR(32),   -- '5min_avg' / '1min_sample'
    cold_sample_rate      FLOAT,         -- 0.01 = 保留 1%
    
    -- 冷存储配置
    cold_storage_type     VARCHAR(32),   -- 's3' / 'oss' / 'minio'
    cold_storage_bucket   VARCHAR(256),
    
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

#### ClickHouse TTL 自动管理

```sql
-- 日志表：自动按策略过期
CREATE TABLE log_entries (
    timestamp       DateTime64(3, 'UTC'),
    -- ...
) ENGINE = MergeTree()
ORDER BY (service_name, timestamp)
TTL timestamp + INTERVAL 7 DAY TO VOLUME 'warm',    -- 7天后转 HDD
    timestamp + INTERVAL 30 DAY TO VOLUME 'cold',   -- 30天后转对象存储
    timestamp + INTERVAL 365 DAY DELETE;             -- 1年后删除
```

#### 存储成本估算

| 数据类型 | 日增量 (1000台) | HOT 7天 | WARM 30天 | COLD 365天 | 年成本估算 |
|---------|----------------|---------|-----------|-----------|-----------|
| 日志 | ~500GB | 3.5TB | 15TB | 182TB (1%采样=1.8TB) | ~$5K |
| 指标 | ~50GB | 350GB | 1.5TB | 18TB (降精度=500GB) | ~$1.5K |
| Trace | ~200GB | 1.4TB | 6TB | 73TB (1%采样=730GB) | ~$3K |
| **合计** | **~750GB/天** | **~5TB** | **~22TB** | **~2.9TB** | **~$10K/年** |

---

### 3.10 平台自我监控（元监控）

**"谁来监控监控平台？"**

```
平台组件                    自监控指标
├── OTel Collector Agent    │ 存活状态、采集延迟、队列积压、CPU/内存
├── Vector ETL              │ 吞吐量、处理延迟、buffer 占用率、错误率
├── PostgreSQL (CMDB)       │ 连接数、慢查询、复制延迟、磁盘占用
├── ClickHouse              │ 查询延迟、Merge 状态、磁盘占用、副本同步
├── Redis                   │ 内存使用、连接数、Streams 积压
├── API Gateway             │ QPS、P99 延迟、错误率
├── AI 诊断引擎             │ LLM 调用延迟、token 消耗、诊断耗时
└── Graph Merge Service     │ 消费延迟、关系更新速率
```

#### 元监控架构

```
┌────────────────────────────────────────────────┐
│          平台组件 (每个组件内置 exporter)         │
│                                                │
│  Vector → /metrics (Prometheus 格式)           │
│  API → /health + /metrics                      │
│  Agent → 向中心上报心跳                          │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ 元监控 Agent  │  (独立的 OTel Collector)
              │ 采集平台指标   │  (与业务 Agent 分离)
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ 元监控存储    │  (独立 ClickHouse 实例
              │              │   或 PostgreSQL 表)
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ 元监控大盘    │  (独立 Dashboard)
              │ 告警→飞书/短信 │
              └──────────────┘
```

**关键原则：元监控与业务监控物理隔离**（元监控挂了不能影响业务监控）。

---

### 3.11 安全架构

| 层面 | 措施 | 实现 |
|------|------|------|
| **认证** | SSO / OAuth2 / LDAP | FastAPI + authlib，对接企业 SSO |
| **授权** | RBAC + 标签数据范围 | 角色绑定 + 查询中间件自动过滤 |
| **传输加密** | mTLS (Agent ↔ Collector ↔ Pipeline) | OTel Collector 内置 TLS 配置 |
| **存储加密** | PostgreSQL TDE + ClickHouse 加密列 | 数据库原生加密 |
| **审计日志** | 所有写操作 + 敏感查询记录 | 独立审计表，不可删除 |
| **密钥管理** | API Key / Token 定期轮转 | Vault 或 KMS 集成 |

---

### 3.12 插件扩展架构

**目标：新增数据源/分析能力不改核心代码。**

```
┌────────────────────────────────────────────────────┐
│                   插件注册中心                       │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ Receiver 插件 │  │ Parser 插件   │               │
│  │ (OTel 原生)  │  │ (厂商日志)    │               │
│  │              │  │              │               │
│  │ 无需改代码   │  │ Grok/JSON    │               │
│  │ 装插件即用   │  │ 模板注册      │               │
│  └──────────────┘  └──────────────┘               │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ Entity 插件  │  │ AI 插件       │               │
│  │ (新实体类型)  │  │ (新分析算法)  │               │
│  │              │  │              │               │
│  │ TypeDef 注册 │  │ Python 模块   │               │
│  │ 无需改表结构  │  │ 热加载        │               │
│  └──────────────┘  └──────────────┘               │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ Dashboard 插件│  │ Exporter 插件 │               │
│  │ (新可视化)    │  │ (新数据导出)  │               │
│  │ Panel 模板   │  │ Webhook/DB   │               │
│  └──────────────┘  └──────────────┘               │
└────────────────────────────────────────────────────┘
```

**各层扩展点：**

| 扩展点 | 方式 | 示例 |
|--------|------|------|
| 数据接入 | OTel Receiver 插件 | 新厂商 syslog、新协议 |
| 日志解析 | Parser 模板注册 (JSON/Grok) | 新设备日志格式 |
| 实体类型 | CMDB TypeDef 注册 | 新增 "LoadBalancer" 类型 |
| 关系类型 | CMDB RelationshipDef 注册 | 新增 "routes_to" 关系 |
| AI 分析 | Python 模块注册 | 新增异常检测算法 |
| 可视化 | Panel 模板 (React 组件) | 新增拓扑热力图 |
| 数据导出 | Sink 插件 | 导出到 Kafka / Elasticsearch |

### 3.13 业务风险度引擎 ⭐ (核心服务)

**地位：与 CMDB、ETL 管道并列的核心平台服务。**

风险度引擎不是 AI 诊断的附属功能，而是**独立的、实时的、贯穿全平台的核心服务**。所有告警、所有异常展示、所有根因分析，都必须经过风险度引擎排序后再呈现。

#### 架构定位

```
                    ┌──────────────────────────┐
                    │     告警/异常事件流入       │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │     风险度计算引擎         │
                    │     (Risk Engine)         │
                    │                          │
                    │  输入: 异常事件 + 实体ID    │
                    │  输出: risk_score + level │
                    │         + user_impact     │
                    │         + business_impact │
                    └────┬────────────┬────────┘
                         │            │
               ┌─────────▼──┐  ┌──────▼────────┐
               │ CMDB 拓扑   │  │ 影响面计算器   │
               │ 传播距离    │  │ 下游数量统计   │
               │ (实时查询)  │  │ (缓存 + 增量)  │
               └────────────┘  └───────────────┘
```

#### 独立服务设计

```python
# risk_engine.py — 独立微服务，对外提供 REST API

from fastapi import FastAPI
app = FastAPI(title="Risk Engine")

@app.post("/api/v1/risk/calculate")
async def calculate_risk(request: RiskRequest) -> RiskResult:
    """
    接收异常事件，返回业务风险度。
    所有上游（告警引擎、AI诊断、前端展示）都调用此接口。
    """
    entity = await cmdb_client.get_entity(request.entity_id)
    
    # 1. 传播距离（实时查 CMDB 拓扑）
    distance = await cmdb_client.shortest_path_to_user(entity)
    propagation_score = 1.0 - (distance.hops - 1) * 0.2  # 衰减
    
    # 2. 影响面（缓存 + 增量更新）
    blast = await get_blast_radius(entity)  # 缓存的下游计数
    blast_score = min(3.0, blast.downstream_count / 10)
    
    # 3. 业务权重（按实体类型预配置）
    biz_weight = BIZ_WEIGHTS.get(entity.type_name, 0.5)
    # Service: 0.8, Database: 0.4, Host: 0.2, CDN: 1.0
    
    # 4. 综合风险度
    risk_score = request.tech_severity * propagation_score * blast_score * biz_weight
    
    return RiskResult(
        risk_score=round(risk_score),
        risk_level=risk_level(risk_score),
        propagation_distance=distance.hops,
        blast_radius=blast.downstream_count,
        user_impact=describe_user_impact(entity, blast),
        business_impact=describe_business_impact(entity, blast),
    )

@app.get("/api/v1/risk/batch")
async def batch_risk(alerts: List[Alert]) -> List[RiskResult]:
    """批量计算，用于告警列表排序"""
    results = await asyncio.gather(*[
        calculate_risk(a) for a in alerts
    ])
    return sorted(results, key=lambda r: r.risk_score, reverse=True)
```

#### 传播距离的实时计算

```
CMDB 图查询（PostgreSQL AGE）：
从异常实体出发，找最短路径到"用户接入点"

示例：
  支付服务 → 网关 → CDN → 用户    (3 hops) → 传播距离 0.7
  MySQL   → 支付服务 → 网关 → CDN → 用户  (4 hops) → 传播距离 0.4
  物理机   → K8s Node → Pod → 服务 → 网关 → CDN → 用户  (6 hops) → 传播距离 0.2
```

```cypher
-- 传播距离计算（预计算 + 实时查询）
-- 预计算：定期为每个实体算出到用户的最短距离，缓存
MATCH (entity:Entity)-[:calls|runs_on|deployed_as|hosted_on|connected_to*1..8]->(endpoint:UserEndpoint)
RETURN entity.name, min(length(path)) as min_hops
ORDER BY min_hops

-- 实时查询：异常发生时查缓存，miss 时实时算
```

#### 影响面的缓存策略

```python
# 影响面计算很重（要遍历下游子图），必须缓存

class BlastRadiusCache:
    """
    缓存每个实体的影响面。
    定时批量重算（每小时），CMDB 拓扑变更时增量更新。
    """
    
    async def get(self, entity_id: str) -> BlastRadius:
        # 1. 查缓存
        cached = await redis.get(f"blast:{entity_id}")
        if cached:
            return cached
        
        # 2. 缓存未命中，实时计算
        downstream = await cmdb.traverse_downstream(entity_id, depth=5)
        blast = BlastRadius(
            entity_id=entity_id,
            downstream_count=len(downstream),
            affected_services=[e.name for e in downstream if e.type == "Service"],
            affected_users=estimate_user_count(downstream),
        )
        
        # 3. 写缓存
        await redis.set(f"blast:{entity_id}", blast, ex=3600)
        return blast
    
    async def on_topology_change(self, changed_entity: str):
        """CMDB 拓扑变更时，失效受影响实体的缓存"""
        upstream = await cmdb.traverse_upstream(changed_entity, depth=5)
        for entity in upstream:
            await redis.delete(f"blast:{entity.id}")
```

#### 与其他模块的集成点

| 模块 | 如何使用风险度引擎 |
|------|-------------------|
| 告警规则引擎 | 每条告警触发时调用 `/risk/calculate`，存储 risk_score |
| AI 诊断引擎 | 根因排序时将 risk_score 作为重要权重 |
| 前端告警中心 | 列表默认按 risk_score DESC 排序 |
| 告警通知 | P0/P1 → 立即通知；P3/P4 → 汇总后通知 |
| 告警收敛 | 同根因多告警 → 取最高 risk_score 作为合并后告警的风险度 |
| 大盘展示 | 异常指标上叠加风险度标识（红/橙/黄/绿） |

---

## 4. 部署架构

### 容器化部署 (Docker Compose / K8s)

```yaml
# docker-compose.yml 概念
services:
  # ---- 核心存储 ----
  postgres:
    image: apache/age:latest  # PostgreSQL + AGE
    volumes: [pgdata:/var/lib/postgresql/data]
    
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    volumes: [chdata:/var/lib/clickhouse]
    
  redis:
    image: redis:7-alpine

  # ---- 数据管道 ----
  vector:
    image: timberio/vector:latest-alpine
    configs: [vector.toml]
    
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    configs: [otel-config.yaml]
    
  # ---- 应用服务 ----
  cmdb-api:
    build: ./services/cmdb-api
    depends_on: [postgres]
    
  etl-service:
    build: ./services/etl
    depends_on: [vector, postgres, clickhouse]
    
  ai-service:
    build: ./services/ai
    depends_on: [postgres, redis]
    
  api-gateway:
    build: ./services/api
    depends_on: [cmdb-api, etl-service, ai-service]
    
  frontend:
    build: ./frontend
    depends_on: [api-gateway]
```

### 资源规划

| 规模 | PostgreSQL | ClickHouse | Vector | API 服务 | 总计 |
|------|-----------|-----------|--------|---------|------|
| 100台 | 4C8G | 4C16G | 2C4G | 4C8G | ~14C36G |
| 500台 | 8C16G | 8C32G | 4C8G | 8C16G | ~28C72G |
| 1000台 | 16C32G (主从) | 16C64G (集群) | 8C16G x2 | 16C32G | ~64C144G |

---

## 5. 分阶段实施路线图

### Phase 1: 日志采集 + 基础 CMDB (4-6 周)

**目标：** 能采集日志、存储、查询，基础 CMDB 管理

- [ ] OTel Collector 配置 + 部署脚本
- [ ] Vector 管道：日志解析 + ClickHouse 写入
- [ ] PostgreSQL CMDB：实体/关系表 + 基础 CRUD API
- [ ] ClickHouse 日志存储 + 搜索 API
- [ ] 前端：日志查询页面 + CMDB 实体列表
- [ ] Docker Compose 一键部署

### Phase 2: Trace 融合 + 指标接入 (4-6 周)

**目标：** Trace 数据自动发现服务关系，CMDB 关系图动态更新

- [ ] Trace 关系提取引擎
- [ ] CMDB 关系融合引擎（创建/更新/过期逻辑）
- [ ] AGE 图存储 + 图查询 API
- [ ] Prometheus 指标接入（Vector → Doris）
- [ ] 前端：拓扑图可视化 + 指标大盘
- [ ] pgvector 向量存储 + 日志 Embedding

### Phase 3: 智能运维 + 告警 (4-6 周)

**目标：** LLM 自然语言查询 + 告警管理 + 根因分析

- [ ] LLM 集成（Text-to-SQL + 结果解释）
- [ ] 向量相似搜索（日志 + 告警）
- [ ] 告警规则引擎 + Alertmanager 集成
- [ ] 根因分析（图遍历 + LLM 推理）
- [ ] 前端：智能问答 + 告警管理

---

## 6. 技术选型总结表

| 层次 | 组件 | 选型 | 理由 |
|------|------|------|------|
| 采集 | Agent | OpenTelemetry Collector | 行业标准，插件丰富 |
| 管道 | ETL | Vector (Rust) | 高性能，声明式配置 |
| 日志存储 | OLAP | ClickHouse | 日志压缩比和查询速度最优 |
| 分析存储 | OLAP | Apache Doris | 多维分析，MySQL 兼容 |
| CMDB 核心 | 关系型+图 | PostgreSQL + AGE | ACID + 图查询，一个数据库搞定 |
| 向量 | Embedding | pgvector | PostgreSQL 扩展，零额外依赖 |
| 队列 | 消息 | Redis Streams | 轻量，Python 友好 |
| API | 后端 | FastAPI (Python) | 异步高性能，自动生成文档 |
| 前端 | UI | React + Ant Design Pro | 组件丰富，企业级 |
| 图可视化 | 拓扑 | AntV G6 | 阿里出品，图布局算法丰富 |
| AI | LLM | 接入外部 API (GPT/Claude) | 按需调用，无需自建 |
| 告警风险 | 风险度引擎 | FastAPI 独立服务 | 实时风险度计算，CMDB 拓扑驱动 |
| 告警通知 | 分级推送 | 飞书 Webhook + 短信网关 | P0 电话+短信, P4 周报汇总 |
| 元监控 | 自监控 | 独立 OTel Collector | 与业务监控物理隔离 |

---

## 平台四大核心价值

| # | 核心价值 | 一句话 |
|---|---------|--------|
| **1** | **数据接入零人工** | 新数据源接入即用，自动协议适配、自动解析、自动入库存储 |
| **2** | **AI 贯穿全层** | 不是独立模块，从采集到展示每一层都有 AI 能力 |
| **3** | **业务风险驱动** | 告警按"用户会不会受影响"排序，而不是 IT 严重度 |
| **4** | **AI 自主进化** | Meta-Agent 大管家 + Sub-Agent 矩阵，平台自我监控、自我优化、自我进化 |

---

### 平台进化层：Meta-Agent（AI 大管家）

**定位：平台的"自动驾驶系统"。不只是被动响应问题，而是主动发现、学习、进化。**

#### 核心理念

```
传统运维平台：人发现问题 → 人分析 → 人处理 → 人优化配置
本平台：    人发现问题 → AI 分析 → AI 处理 → AI 优化自己

更进一步：
            AI 主动发现问题 → AI 分析 → AI 处理 → AI 进化出新能力
            （不需要人触发）
```

#### Meta-Agent 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Meta-Agent (AI 大管家)                      │
│                      始终在线，自治运行                            │
│                                                                 │
│  职责：                                                          │
│  1. 监控平台全貌（所有模块的健康 + 数据质量）                       │
│  2. 按需产生 Sub-Agent 处理专项任务                               │
│  3. 从经验中学习，主动进化平台能力                                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    调度层 (Orchestrator)                  │   │
│  │  "现在需要做什么？谁来做？"                                │   │
│  └──────┬────────────┬────────────┬────────────┬───────────┘   │
│         │            │            │            │                │
│    ┌────▼────┐  ┌────▼────┐  ┌───▼─────┐  ┌───▼─────┐         │
│    │ 监控    │  │ 诊断    │  │ 学习    │  │ 维护    │         │
│    │ Agent   │  │ Agent   │  │ Agent   │  │ Agent   │  ...    │
│    │ (长期)  │  │ (按需)  │  │ (定时)  │  │ (定时)  │         │
│    └─────────┘  └─────────┘  └─────────┘  └─────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

#### Sub-Agent 矩阵

| Agent | 生命周期 | 职责 | 触发条件 |
|-------|---------|------|---------|
| **监控 Agent** | 常驻 | 持续扫描平台全貌：数据流是否通畅、各组件健康度 | 始终在线 |
| **诊断 Agent** | 按需 | 深度分析特定问题，调用 AI 诊断引擎 | 监控 Agent 发现异常时产生 |
| **学习 Agent** | 定时 | 从历史数据和反馈中学习，优化平台配置 | 每天/每周 |
| **维护 Agent** | 定时 | 平台自我优化：清理数据、重建索引、调整参数 | 低峰期 |
| **报告 Agent** | 定时 | 自动生成运营报告、SLA 报告 | 每天/每周 |
| **探索 Agent** | 按需 | 主动发现新数据源模式、新实体、新关系 | 发现未识别数据时产生 |
| **应急 Agent** | 按需 | P0 故障时自动执行预定义的应急操作 | P0 告警触发时产生 |

#### 具体场景

**场景 1：主动发现数据质量问题**

```
Meta-Agent (常驻监控)
    │
    ├─ 检测到: payment-service 的日志量在过去 30 分钟下降 80%
    │  正常: ~500条/min → 当前: ~100条/min
    │
    ├─ 判断: 不是业务下降（QPS 正常），是采集问题
    │
    ├─ 产生 → 诊断 Agent
    │
    └─ 诊断 Agent 执行:
       ├─ 检查 OTel Agent 状态 → 发现: Agent OOM 被 kill
       ├─ 检查日志文件 → 发现: 日志轮转后 inode 变了
       ├─ 结论: filelog cursor 失效，需要重置
       ├─ 操作: 自动重置 cursor，重启 Agent
       └─ 汇报: "已自动修复 payment-service 日志采集问题"
```

**场景 2：主动优化告警规则**

```
学习 Agent (定时执行)
    │
    ├─ 分析过去 30 天告警数据:
    │  • "磁盘 >90%" 告警触发 200 次，0 次用户影响 → P4 合理
    │  • "MySQL 慢查询" 告警触发 50 次，0 次用户影响 → 应该降级到 P4
    │  • "网关延迟 >500ms" 触发 10 次，10 次用户投诉 → 应该升级到 P0
    │
    ├─ 生成建议:
    │  "建议调整以下告警规则的风险度权重: ..."
    │
    └─ (人工确认后) 自动更新风险度计算参数
```

**场景 3：主动发现新模式，进化平台能力**

```
探索 Agent (按需触发)
    │
    ├─ 发现: 最近接入了一批来自 "Kong Gateway" 的日志
    │  格式未知，解析失败率 60%
    │
    ├─ 自动分析:
    │  • 抽取 100 条样本日志
    │  • 用 LLM 分析格式特征
    │  • 生成解析规则模板
    │
    ├─ 生成建议:
    │  "发现新日志格式 'Kong Gateway Access Log'，
    │   已生成解析模板，是否注册到解析规则库？"
    │
    └─ (人工确认后) 注册为新的 Parser 插件
       → 从此 Kong 日志自动解析，不再需要人工
```

**场景 4：P0 故障自动应急**

```
监控 Agent 检测到: P0 网关 502 率 >10%
    │
    ├─ 通知 Meta-Agent
    │
    ├─ Meta-Agent 产生 → 应急 Agent
    │
    └─ 应急 Agent 执行 (Runbook 自动化):
       ├─ Step 1: 自动扩容网关实例 (2 → 6)
       ├─ Step 2: 检查上游服务健康 → 发现 order-service 无响应
       ├─ Step 3: 自动重启 order-service Pod
       ├─ Step 4: 验证恢复 → 502 率回落到 0.1%
       └─ Step 5: 生成事后报告 + 学习案例存入知识库
```

#### Sub-Agent 生命周期管理

```python
class MetaAgent:
    """
    AI 大管家：管理所有 Sub-Agent 的生命周期。
    """
    
    def __init__(self):
        self.active_agents: Dict[str, SubAgent] = {}
        self.agent_pool = AgentPool(max_concurrent=10)
    
    async def main_loop(self):
        """常驻循环：监控全貌 + 调度 Agent"""
        while True:
            # 1. 平台健康巡检
            health = await self.platform_health_check()
            
            # 2. 按需产生 Agent
            for issue in health.issues:
                if issue.severity == "P0":
                    # P0 → 立即产生应急 Agent
                    await self.spawn_agent("emergency", issue)
                elif issue.type == "data_quality":
                    # 数据质量 → 诊断 Agent
                    await self.spawn_agent("diagnosis", issue)
                elif issue.type == "new_pattern":
                    # 新模式 → 探索 Agent
                    await self.spawn_agent("exploration", issue)
            
            # 3. 检查定时任务
            if self.should_run_learning():
                await self.spawn_agent("learning")
            if self.should_run_maintenance():
                await self.spawn_agent("maintenance")
            
            # 4. 清理已完成的 Agent
            await self.cleanup_finished_agents()
            
            await asyncio.sleep(60)  # 每分钟检查一次
    
    async def spawn_agent(self, agent_type: str, context: Any = None):
        """产生一个 Sub-Agent"""
        agent = self.agent_pool.acquire(agent_type)
        agent.context = context
        
        # 记录
        self.active_agents[agent.id] = agent
        logger.info(f"MetaAgent spawned {agent_type} agent: {agent.id}")
        
        # 异步执行
        asyncio.create_task(agent.run())
    
    async def on_agent_finished(self, agent: SubAgent):
        """Sub-Agent 完成后的回调"""
        # 记录结果
        await self.log_agent_result(agent)
        
        # 学习：如果 Agent 产出了有价值的发现，存入知识库
        if agent.result.has_insights:
            await self.knowledge_base.store(agent.result.insights)
        
        # 进化：如果 Agent 发现了新的优化建议，评估后实施
        if agent.result.has_suggestions:
            await self.evaluate_and_apply(agent.result.suggestions)
        
        # 归还 Agent 到池中
        self.agent_pool.release(agent)
```

#### 进化机制

```
Agent 执行 → 产出发现/建议
                    │
                    ▼
            ┌───────────────┐
            │  知识库 (KB)   │  PostgreSQL + pgvector
            │               │
            │ • 故障案例     │  ← 诊断 Agent 产出
            │ • 优化建议     │  ← 学习 Agent 产出
            │ • 解析规则     │  ← 探索 Agent 产出
            │ • 最佳实践     │  ← 从反馈中提炼
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  评估引擎      │
            │               │
            │ • 安全性检查   │  建议不会导致故障？
            │ • 影响评估     │  改动范围可控？
            │ • A/B 验证     │  先在测试环境跑
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  自动实施      │
            │               │
            │ • 更新告警规则  │
            │ • 注册解析模板  │
            │ • 调整风险度权重│
            │ • 优化采集配置  │
            └───────────────┘
                    │
                    ▼
            平台能力 +1
            (比昨天更聪明)
```

#### 与现有模块的关系

| 现有模块 | Meta-Agent 如何使用它 |
|---------|----------------------|
| CMDB | 查询实体拓扑，发现新实体自动创建 |
| AI 诊断引擎 | 诊断 Agent 调用它做深度分析 |
| 告警风险度引擎 | 监控 Agent 用它判断优先级，学习 Agent 优化它的参数 |
| ETL 管道 | 监控 Agent 监控它的健康，维护 Agent 优化它的配置 |
| 插件系统 | 探索 Agent 产出新插件，通过插件系统注册 |

---

_文档完成，待主人 review 后进入 Validate 阶段_
