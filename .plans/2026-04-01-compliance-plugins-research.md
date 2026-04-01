# 航空业合规检查插件库 - 调研规划

_需求日期：2026-04-01_
_来源：航空业 Part-IS.I.OR.243.3(d) 合规要求_
_定位：后续需求，当前只做调研和规划_

---

## 1. 业务场景

**用户故事：** 作为航空公司的信息安全负责人，我需要确保所有处理航空重要数据的信息系统都符合行业合规要求。当日志数据进入平台后，我希望能够选择特定的合规规范（如 Part-IS.I.OR.243.3(d)），让系统自动检查日志是否满足合规要求，并在不合规时及时预警。

**核心价值：**
- 合规检查自动化（替代人工审计）
- 实时预警（不等问题暴露）
- 证据收集（应对监管检查）
- 灵活装载（不同行业/规范可插拔）

---

## 2. 航空业合规要求分析

### 2.1 Part-IS.I.OR.243.3(d) 核心要求

| 条款 | 要求 | 检查点 | 日志数据关联 |
|------|------|--------|-------------|
| **3.3.1** | 记录重大事件 | 事件完整性 | 所有系统必须有日志输出 |
| **3.3.2** | 身份认证日志 | 认证事件 | 登录/登出/失败尝试 |
| **3.3.2** | 访问日志 | 访问控制 | 数据访问/API调用 |
| **3.3.2** | 配置变更日志 | 变更管理 | 系统配置修改 |
| **3.3.2** | 安全事件日志 | 安全监控 | 异常/攻击/入侵 |
| **3.3.2** | 系统故障日志 | 可用性 | 错误/崩溃/重启 |
| **3.3.3** | 日志防篡改 | 完整性保护 | 日志文件权限/加密 |
| **3.3.3** | 防止未授权访问 | 访问控制 | 日志读取权限 |
| **3.3.3** | 防止日志删除 | 持久化 | 日志保留策略 |
| **3.3.3** | 防止存储覆盖 | 存储管理 | 磁盘空间监控 |
| **3.3.4** | 时钟同步 | 时间一致性 | NTP 配置检查 |
| **4** | 定期审查访问日志 | 审计频率 | 审计报告生成 |

### 2.2 ISO 27001 关联控制

| ISO 27001 控制 | 对应要求 | 检查方式 |
|---------------|---------|---------|
| A.12.4.1 | 事件日志 | 日志覆盖率 |
| A.12.4.2 | 日志信息保护 | 访问控制检查 |
| A.12.4.3 | 管理员和操作员日志 | 特权操作记录 |
| A.18.1.1 | 适用法律和法规识别 | 合规映射 |
| A.18.2.3 | 技术合规性 | 技术检查 |

---

## 3. 合规检查插件架构设计

### 3.1 插件结构

```
compliance-plugins/
├── aviation/                          # 航空业
│   ├── part-is-ior-243-3d/           # Part-IS.I.OR.243.3(d)
│   │   ├── plugin.yaml               # 插件元数据
│   │   ├── rules/                    # 检查规则
│   │   │   ├── 3.3.1-event-logging.yaml
│   │   │   ├── 3.3.2-auth-logging.yaml
│   │   │   ├── 3.3.2-access-logging.yaml
│   │   │   ├── 3.3.2-config-change.yaml
│   │   │   ├── 3.3.2-security-events.yaml
│   │   │   ├── 3.3.2-system-faults.yaml
│   │   │   ├── 3.3.3-log-protection.yaml
│   │   │   ├── 3.3.4-clock-sync.yaml
│   │   │   └── 4-access-review.yaml
│   │   └── reports/                  # 报告模板
│   │       └── compliance-report.md
│   └── iso27001-aviation/            # ISO 27001 航空扩展
│       └── ...
├── finance/                          # 金融业（预留）
│   └── ...
└── healthcare/                       # 医疗业（预留）
    └── ...
```

### 3.2 插件定义格式（plugin.yaml）

```yaml
plugin_id: "part-is-ior-243-3d"
name: "航空信息系统安全 - Part-IS.I.OR.243.3(d)"
version: "1.0.0"
industry: "aviation"
standard: "EASA Part-IS"
description: "航空信息系统日志记录与监控合规检查"
author: "监控ETL平台"
rules_count: 9
data_requirements:
  - type: "logs"
    sources: ["all_systems"]
    min_retention_days: 365
  - type: "metrics"
    sources: ["ntp_sync", "disk_usage", "log_access"]
  - type: "config"
    sources: ["system_config", "log_config"]
check_schedule: "0 2 * * *"  # 每天凌晨2点
severity_levels:
  critical: "立即上报影响航空运营的警报"
  high: "24小时内处理"
  medium: "7天内处理"
  low: "下次维护窗口处理"
```

### 3.3 检查规则格式（YAML）

```yaml
rule_id: "3.3.2-auth-logging"
name: "身份认证日志记录"
clause: "3.3.2"
description: "系统必须就身份认证生成日志，包含时间戳、用户标识符和事件详情"
severity: "critical"

# 检查逻辑
check_type: "log_coverage"  # log_coverage / log_content / metric_threshold / config_check
check_logic:
  # 检查是否存在认证相关日志
  type: "exists"
  query: |
    SELECT count() as auth_events
    FROM logs.log_entries
    WHERE timestamp > now() - INTERVAL 24 HOUR
      AND (
        message ILIKE '%login%' OR
        message ILIKE '%authentication%' OR
        message ILIKE '%auth%' OR
        level = 'security'
      )
  threshold:
    min: 1  # 至少要有1条认证日志
  time_window: "24h"

# 合规条件
compliance:
  pass_condition: "auth_events >= 1"
  fail_message: "过去24小时未检测到身份认证日志，违反 Part-IS.I.OR.243.3(d) 3.3.2"
  remediation: "确保所有处理航空重要数据的系统启用了身份认证日志记录"

# 证据收集
evidence:
  query: |
    SELECT timestamp, service_name, host_name, message
    FROM logs.log_entries
    WHERE timestamp > now() - INTERVAL 24 HOUR
      AND (message ILIKE '%login%' OR message ILIKE '%auth%')
    ORDER BY timestamp DESC
    LIMIT 100
  retention_days: 365
```

### 3.4 检查引擎设计

```python
# services/compliance-engine/app/main.py

class ComplianceEngine:
    """合规检查引擎 - 可插拔规则执行器。"""
    
    def __init__(self):
        self.plugins = {}  # plugin_id → Plugin
        self.results = []  # 检查结果
    
    def load_plugin(self, plugin_dir: str):
        """加载合规插件。"""
        plugin_yaml = load_yaml(f"{plugin_dir}/plugin.yaml")
        rules = load_rules(f"{plugin_dir}/rules/")
        self.plugins[plugin_yaml["plugin_id"]] = Plugin(plugin_yaml, rules)
    
    def run_check(self, plugin_id: str, rule_id: str = None):
        """执行合规检查。"""
        plugin = self.plugins[plugin_id]
        
        if rule_id:
            rules = [r for r in plugin.rules if r.id == rule_id]
        else:
            rules = plugin.rules
        
        for rule in rules:
            result = self._execute_rule(rule)
            self.results.append(result)
            
            if result.status == "fail" and rule.severity == "critical":
                self._raise_alert(result)
    
    def _execute_rule(self, rule: ComplianceRule) -> CheckResult:
        """执行单条规则。"""
        # 执行查询
        data = self._run_query(rule.check_logic.query)
        
        # 评估结果
        if self._evaluate(data, rule.check_logic.threshold):
            return CheckResult(
                rule_id=rule.id,
                status="pass",
                message=f"{rule.name} - 合规",
                evidence=data
            )
        else:
            return CheckResult(
                rule_id=rule.id,
                status="fail",
                message=rule.compliance.fail_message,
                remediation=rule.compliance.remediation,
                evidence=data
            )
    
    def generate_report(self, plugin_id: str) -> str:
        """生成合规报告。"""
        plugin = self.plugins[plugin_id]
        results = [r for r in self.results if r.rule_id in [r.id for r in plugin.rules]]
        
        return render_template(
            plugin.report_template,
            plugin=plugin,
            results=results,
            pass_rate=sum(1 for r in results if r.status == "pass") / len(results)
        )
```

---

## 4. 航空业合规检查规则清单

### 4.1 规则矩阵

| 规则ID | 条款 | 检查项 | 检查方式 | 数据来源 | 频率 |
|--------|------|--------|---------|---------|------|
| R001 | 3.3.1 | 事件完整性 | 所有系统是否有日志输出 | logs.log_entries | 每日 |
| R002 | 3.3.2 | 身份认证日志 | 登录/登出/失败尝试 | logs.log_entries | 每日 |
| R003 | 3.3.2 | 访问日志 | 数据访问/API调用 | logs.log_entries | 每日 |
| R004 | 3.3.2 | 配置变更日志 | 系统配置修改 | logs.log_entries | 每日 |
| R005 | 3.3.2 | 安全事件日志 | 异常/攻击/入侵 | logs.log_entries | 每日 |
| R006 | 3.3.2 | 系统故障日志 | 错误/崩溃/重启 | logs.log_entries | 每日 |
| R007 | 3.3.3 | 日志完整性 | 日志文件权限/加密 | config | 每周 |
| R008 | 3.3.3 | 访问控制 | 日志读取权限 | config | 每周 |
| R009 | 3.3.3 | 持久化保护 | 日志保留策略 | config | 每周 |
| R010 | 3.3.3 | 存储监控 | 磁盘空间监控 | metrics | 每日 |
| R011 | 3.3.4 | 时钟同步 | NTP 配置检查 | config | 每日 |
| R012 | 4 | 审计频率 | 审计报告生成 | logs | 每周 |

### 4.2 关键规则详细设计

#### R002: 身份认证日志检查

```yaml
rule_id: "R002"
name: "身份认证日志记录"
clause: "3.3.2"
severity: "critical"

check_logic:
  type: "log_pattern"
  patterns:
    - "login"
    - "logout"
    - "authentication"
    - "auth_success"
    - "auth_failure"
    - "password_change"
    - "session_start"
    - "session_end"
  threshold:
    min_events_per_hour: 1  # 至少每小时1条（覆盖所有系统）
  time_window: "24h"

compliance:
  pass_condition: "所有系统都有认证日志输出"
  fail_message: "系统 {system} 过去24小时未检测到身份认证日志"
  remediation: "确保系统 {system} 启用了认证日志记录"

evidence_query: |
  SELECT 
    service_name,
    host_name,
    count() as auth_events,
    min(timestamp) as first_event,
    max(timestamp) as last_event
  FROM logs.log_entries
  WHERE timestamp > now() - INTERVAL 24 HOUR
    AND (
      message ILIKE '%login%' OR
      message ILIKE '%logout%' OR
      message ILIKE '%authentication%' OR
      message ILIKE '%auth_success%' OR
      message ILIKE '%auth_failure%'
    )
  GROUP BY service_name, host_name
  ORDER BY auth_events DESC
```

#### R011: 时钟同步检查

```yaml
rule_id: "R011"
name: "时钟同步检查"
clause: "3.3.4"
severity: "high"

check_logic:
  type: "metric_threshold"
  query: |
    SELECT 
      host_name,
      max(timestamp) as last_log_time,
      now() as current_time,
      dateDiff('second', max(timestamp), now()) as time_drift_seconds
    FROM logs.log_entries
    WHERE timestamp > now() - INTERVAL 1 HOUR
    GROUP BY host_name
  threshold:
    max_drift_seconds: 30  # 最大允许漂移30秒

compliance:
  pass_condition: "所有主机时间漂移 < 30秒"
  fail_message: "主机 {host_name} 时间漂移 {time_drift_seconds}秒，超过30秒阈值"
  remediation: "检查NTP配置，确保所有系统与可信时间源同步"

evidence_query: |
  SELECT 
    host_name,
    max(timestamp) as last_log_time,
    now() as current_time,
    dateDiff('second', max(timestamp), now()) as time_drift_seconds
  FROM logs.log_entries
  WHERE timestamp > now() - INTERVAL 1 HOUR
  GROUP BY host_name
  HAVING time_drift_seconds > 30
  ORDER BY time_drift_seconds DESC
```

#### R010: 存储空间监控

```yaml
rule_id: "R010"
name: "日志存储空间监控"
clause: "3.3.3"
severity: "high"

check_logic:
  type: "metric_threshold"
  query: |
    SELECT 
      host_name,
      disk_usage_percent,
      free_space_gb
    FROM system_metrics
    WHERE metric_name = 'disk_usage'
      AND mount_point LIKE '%log%'
      AND timestamp > now() - INTERVAL 1 HOUR
  threshold:
    max_usage_percent: 85  # 磁盘使用率不超过85%
    min_free_gb: 10        # 至少保留10GB

compliance:
  pass_condition: "所有日志存储磁盘使用率 < 85% 且可用空间 > 10GB"
  fail_message: "主机 {host_name} 日志存储磁盘使用率 {disk_usage_percent}%，可能因存储空间不足导致日志被覆盖"
  remediation: "扩容日志存储或调整日志保留策略"
```

---

## 5. 平台集成设计

### 5.1 在现有架构中的位置

```
                    用户
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    前端层                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │  合规管理页面                                     │   │
│  │  • 插件市场（选择合规规范）                        │   │
│  │  • 检查结果仪表盘                                 │   │
│  │  • 合规报告下载                                   │   │
│  │  • 不合规项处置                                   │   │
│  └─────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                    API 层 (FastAPI)                       │
│  /compliance/                                            │
│  ├── /plugins           插件管理                         │
│  ├── /checks            检查执行                         │
│  ├── /results           结果查询                         │
│  └── /reports           报告生成                         │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                合规检查引擎 (Compliance Engine)            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 插件加载器   │  │ 规则执行器   │  │ 报告生成器   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└───────────────────────────┬─────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         ClickHouse    PostgreSQL     Config
         (日志数据)    (CMDB/实体)    (配置检查)
```

### 5.2 数据流

```
1. 用户选择合规插件 → 加载规则集
2. 定时任务触发 → 执行所有规则
3. 每条规则 → 查询 ClickHouse/PostgreSQL
4. 评估结果 → 写入 compliance_check_result 表
5. 不合规项 → 触发告警（critical 级别）
6. 生成报告 → 存储 + 通知用户
```

### 5.3 新增数据库表

```sql
-- 合规插件表
CREATE TABLE compliance_plugin (
    plugin_id       VARCHAR(128) PRIMARY KEY,
    name            VARCHAR(256) NOT NULL,
    version         VARCHAR(32),
    industry        VARCHAR(64),
    standard        VARCHAR(128),
    description     TEXT,
    plugin_dir      VARCHAR(512),
    is_enabled      BOOLEAN DEFAULT false,
    installed_at    TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 合规检查规则表
CREATE TABLE compliance_rule (
    rule_id         VARCHAR(128) PRIMARY KEY,
    plugin_id       VARCHAR(128) REFERENCES compliance_plugin(plugin_id),
    clause          VARCHAR(64),           -- 条款号：3.3.2
    name            VARCHAR(256),
    description     TEXT,
    severity        VARCHAR(16),           -- critical/high/medium/low
    check_type      VARCHAR(32),           -- log_coverage/log_content/metric_threshold/config_check
    check_logic     JSONB,                 -- 检查逻辑
    compliance      JSONB,                 -- 合规条件
    evidence_query  TEXT,                  -- 证据收集查询
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 合规检查结果表
CREATE TABLE compliance_check_result (
    result_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id       VARCHAR(128) REFERENCES compliance_plugin(plugin_id),
    rule_id         VARCHAR(128) REFERENCES compliance_rule(rule_id),
    check_time      TIMESTAMPTZ DEFAULT now(),
    status          VARCHAR(16),           -- pass/fail/error
    message         TEXT,
    evidence        JSONB,                 -- 证据数据
    remediation     TEXT,                  -- 修复建议
    resolved_at     TIMESTAMPTZ,
    resolved_by     VARCHAR(128)
);

-- 合规报告表
CREATE TABLE compliance_report (
    report_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_id       VARCHAR(128) REFERENCES compliance_plugin(plugin_id),
    report_time     TIMESTAMPTZ DEFAULT now(),
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    total_rules     INT,
    passed_rules    INT,
    failed_rules    INT,
    pass_rate       FLOAT,
    report_data     JSONB,                 -- 完整报告数据
    report_file     VARCHAR(512)           -- 报告文件路径
);

-- 索引
CREATE INDEX idx_check_result_plugin ON compliance_check_result(plugin_id);
CREATE INDEX idx_check_result_status ON compliance_check_result(status) WHERE status = 'fail';
CREATE INDEX idx_check_result_time ON compliance_check_result(check_time DESC);
```

---

## 6. 技术实现路径

### Phase 1: 插件框架（3-4周）
- [ ] 合规检查引擎核心
- [ ] 插件加载器（YAML 规则解析）
- [ ] 规则执行器（查询 + 评估）
- [ ] 基础 API（插件管理 + 检查执行）

### Phase 2: 航空业插件（2-3周）
- [ ] Part-IS.I.OR.243.3(d) 全套规则
- [ ] ISO 27001 航空扩展规则
- [ ] 合规报告模板
- [ ] 告警集成

### Phase 3: 前端 + 集成（2周）
- [ ] 合规管理页面
- [ ] 插件市场 UI
- [ ] 检查结果仪表盘
- [ ] 报告下载

### Phase 4: 扩展（按需）
- [ ] 金融业合规插件
- [ ] 医疗业合规插件
- [ ] 自定义规则编辑器

---

## 7. 关键设计决策

### 7.1 规则执行方式

| 方式 | 优点 | 缺点 | 适用 |
|------|------|------|------|
| **SQL 查询** | 灵活，性能好 | 需要 SQL 知识 | 日志/指标检查 |
| **配置检查** | 简单直接 | 覆盖面有限 | 系统配置检查 |
| **模式匹配** | 易于理解 | 性能较差 | 日志内容检查 |
| **LLM 分析** | 智能，能发现未知模式 | 成本高，延迟大 | 复杂场景 |

**推荐：** SQL 查询为主，配置检查为辅，LLM 作为可选增强。

### 7.2 检查频率

| 规则类型 | 频率 | 理由 |
|---------|------|------|
| 日志覆盖率 | 每日 | 需要24小时窗口 |
| 日志内容 | 每日 | 与覆盖率同步 |
| 指标阈值 | 每日 | 与日志检查同步 |
| 配置检查 | 每周 | 配置变更频率低 |
| 审计频率 | 每周 | 审计周期长 |

### 7.3 证据保留

- 所有检查结果保留 **365天**（航空业审计要求）
- 证据数据（查询结果）保留 **90天**
- 合规报告永久保留

---

## 8. 风险与挑战

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 日志格式多样 | 规则难以通用化 | 使用模式匹配 + 可配置字段映射 |
| 性能影响 | 大量日志查询慢 | 索引优化 + 预聚合 + 增量检查 |
| 误报率高 | 用户不信任 | 人工确认 + 反馈学习 |
| 合规标准更新 | 规则过时 | 版本管理 + 定期审查 |

---

## 9. 竞品参考

| 产品 | 合规能力 | 我们的优势 |
|------|---------|-----------|
| Splunk Enterprise | 内置合规框架 | 更轻量，更聚焦 |
| IBM QRadar | 合规报告自动化 | 更灵活的插件架构 |
| Azure Sentinel | 云原生合规 | 更好的本地化支持 |
| 国产安全厂商 | 特定行业合规 | 更开放的插件生态 |

---

_调研规划完成，待后续进入详细设计和实现阶段_
