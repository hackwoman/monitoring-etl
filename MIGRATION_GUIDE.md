# 监控 ETL 平台迁移指南
> 最后更新：2026-04-28 18:30 CST
> 当前环境：实例 B (8.146.232.9) — 今晚 22:00 回收

---

## 1. 数据库现状（已备份）

**备份文件**：`backup/cmdb_full_dump.sql`（GitHub commit dc1ef00）

### 关键数据
- **15 个实体**（6 种类型）：Business(2) / Service(4) / Host(5) / MySQL(2) / Redis(1) / NetworkDevice(1)
- **29 条关系**：runs_on(7) / connected_to(4) / includes(4) / calls(14)
- **16 个实体类型定义**：含 K8s/Docker/Container 等新类型

### Schema 关键点（与 Phase 1 前不同）
```
旧 Schema（Phase 1 前）          新 Schema（Phase 1 后）
─────────────────────────────────────────────────────────
entity_types (表)         →     entity_type_def (表)
entities (表)             →     entity (表)
entity_relations (表)     →     relationship (表)
entity_type_id (UUID)     →     type_name (varchar)
```

### entity 表关键字段
| 字段 | 类型 | 说明 |
|------|------|------|
| guid | uuid | 主键 |
| name | varchar(512) | 实体名称 |
| type_name | varchar(128) | 实体类型（FK 到 entity_type_def） |
| biz_service | varchar(256) | **系统分组字段**（前端必须用这个） |
| health_score | integer | 健康分数 |
| health_level | varchar(16) | healthy/warning/critical |
| attributes | jsonb | 扩展属性 |
| labels | jsonb | 标签 |
| status | varchar(32) | active 等 |

### relationship 表关键字段
| 字段 | 类型 | 说明 |
|------|------|------|
| guid | uuid | 主键 |
| type_name | varchar(128) | 关系类型：runs_on/calls/depends_on/connected_to/includes |
| end1_guid / end2_guid | uuid | 垂直关系端点（双向） |
| from_guid / to_guid | uuid | 水平关系端点（单向，如 calls） |
| dimension | varchar(16) | **horizontal**（水平=跨系统）或 **vertical**（垂直=系统内） |
| call_type | varchar(16) | sync/async |

### entity_type_def 表关键字段
| 字段 | 类型 | 说明 |
|------|------|------|
| type_name | varchar(128) | **主键**，不是 UUID |
| display_name | varchar(256) | 中文显示名 |
| category | varchar(64) | business/application/infrastructure/middleware/runtime |
| icon | varchar(128) | 图标名称 |
| definition | jsonb | 健康度计算方法、metrics、relations 定义 |
| is_custom | boolean | 是否用户自定义 |

---

## 2. 已修复的 Bug（勿重复踩）

### Bug 1：Topology.tsx 系统分组字段名错误 ⚠️ 最重要
- **文件**：`frontend/src/pages/Topology.tsx`
- **问题**：代码用 `e.biz_system` 判断系统分组，但数据库实体实际字段是 `e.biz_service`
- **影响**：所有实体进入 `__no_system__`，系统分组虚线框完全无法显示
- **修复**：commit `c4d7215` — 将 `biz_system` 替换为 `biz_service`（3 处）
  - L295：系统边界计算 `const sys = e.biz_service || '__no_system__'`
  - L792：Drawer 内系统名称显示
  - L794：Drawer 内 systemBounds 查找
- **验证方法**：浏览器访问 `/topology`，应有虚线框圈出"在线支付"(13实体)和"用户注册"(2实体)

### Bug 2：Phase 4-6 脚本未打包进 Docker 镜像
- **问题**：`scripts/` 目录下的脚本（smart_etl_engine.py、conflict_resolver.py 等）在 GitHub 有，但服务器 `services/cmdb-api/app/` 里没有
- **原因**：这些脚本在服务器上手动运行过，但从未 `cp` 到 Docker 构建目录，也未同步 GitHub（后来已同步）
- **影响**：Docker 镜像重建后 cmdb-api 容器启动失败（找不到 smart_etl_engine.py）
- **修复**：手动复制 + GitHub push
  ```bash
  # 正确做法：修改脚本后，必须同时做两件事
  cp /home/lily/monitoring-etl/scripts/smart_etl_engine.py \
     /home/lily/monitoring-etl/services/cmdb-api/app/engines/
  # 然后 git add + commit + push
  ```
- **教训**：Phase 4-6 脚本必须作为应用代码的一部分通过 Docker 构建，不是独立运维脚本

### Bug 3：SSH 连接密码
- **服务器 B (8.146.232.9)**：用户名 `lily`，密码 `Temp2026!`
- **服务器 A (47.93.61.196)**：用户名 `root`，密码 `Temp2026!`
- **连接方式**：必须用 python3 + paramiko，不可用 sshpass/expect

### Bug 4：GitHub Token 前缀
- **正确**：`ghp_` 前缀（GitHub Personal Access Token）
- **错误**：记成 `gph_` 导致 push 失败

---

## 3. 架构设计决策（已确认）

### 全局拓扑设计原则
1. **横向不分层**：所有服务节点平铺，不按 L1-L2-L3-L4 分层展示
2. **系统是可选分组**：客户定义则有，不定义则无（没有系统 = 所有服务平铺）
3. **纵向才分层**：点击服务弹出 Drawer 抽屉，里面才展开承载层级（实例→容器→进程→主机）
4. **服务 = 基本单元**：可能是单实例也可能是集群，对用户呈现"一个服务"
5. **复杂度处理**：过滤（按类型/标签）+ 聚焦（高亮上下游）+ 系统分组（自定义分区）

### 节点视觉编码
- **外环颜色** = 错误率：🟢 ≤1% / 🟡 1-5% / 🔴 >5%
- **图标颜色** = 健康度（Apdex）：🟢 ≥0.94 / 🟡 0.7-0.93 / 🔴 <0.7
- **线条** = 调用关系（只表示"有关系"，不表示先后顺序）

### 双关系体系
- **纵向关系**（CMDB 静态）：runs_on / connected_to / includes 等，存储在 `relationship` 表 `dimension=vertical`
- **横向关系**（APM/Trace 动态）：calls / depends_on，存储在 `relationship` 表 `dimension=horizontal`
- CMDB 不存储高频变化数据（高频数据走 ClickHouse 时序库）

### 关系计算引擎（未实现，缺失）
```
Span 数据（SkyWalking/Jaeger/Zipkin）
    ↓ ETL 采集
ClickHouse（Span 数据湖）
    ↓ 定时消费
关系计算引擎（计算 entity 间的调用关系）
    ↓ 写入
relationship 表（dimension=horizontal）
    ↓ 前端读取
全局拓扑线条
```
**当前状态**：relationship 表中的 horizontal 关系是手动 SQL 写入的，无真实引擎

---

## 4. 新环境部署检查清单

### 代码获取
```bash
git clone -b latest-main https://github.com/hackwoman/monitoring-etl.git
cd monitoring-etl
```

### Docker 环境准备
```bash
# 安装 Docker 和 docker-compose
curl -fsSL https://get.docker.com | sh
pip install docker-compose
```

### 数据库恢复
```bash
# 恢复数据库（如果有备份文件）
docker exec -i monitoring-etl-postgres-1 psql -U postgres -d cmdb < backup/cmdb_full_dump.sql

# 或重新运行 Phase 1 迁移脚本
docker exec monitoring-etl-cmdb-api-1 python /app/scripts/migrate_model_v2.py
```

### 关键环境变量
```yaml
DATABASE_URL: postgresql+asyncpg://postgres:<密码>@<数据库IP>:5432/cmdb
# 当前：postgresql+asyncpg://postgres:M9kX#pL2vQ!zR7w@47.93.61.196:5432/cmdb
```

### 镜像构建（修改代码后）
```bash
# 必须加 --no-cache，否则新代码可能不编译进去
docker compose build frontend --no-cache
docker compose up -d frontend
```

### 服务启动顺序
```bash
docker compose up -d postgres redis clickhouse vector  # 数据层先起
docker compose up -d cmdb-api log-api                 # API 层
docker compose up -d frontend nginx                   # 前端层
```

---

## 5. Phase 4-6 脚本清单（已同步 GitHub）

| 脚本 | 用途 | 位置 |
|------|------|------|
| migrate_model_v2.py | Phase 1 数据库迁移 | scripts/ + services/cmdb-api/app/ |
| smart_etl_engine.py | Phase 5 格式识别引擎 | scripts/ + services/cmdb-api/app/engines/ |
| conflict_resolver.py | Phase 4 冲突检测 | scripts/ + services/cmdb-api/app/routers/ |
| demo_data_factory.py | Phase 6 测试数据生成 | scripts/ |
| import_metrics.py | 指标定义导入 | scripts/ |
| import_mappings.py | 映射规则导入 | scripts/ |
| import_attributes.py | 属性定义导入 | scripts/ |
| import_dictionaries.py | 字典数据导入 | scripts/ |

**重要**：修改 scripts/ 下的文件后，必须同时复制到 `services/cmdb-api/app/` 对应目录，并 git push

---

## 6. 今晚待办（10 PM 回收前）

- [x] GitHub 同步：所有代码推送到 hackwoman/monitoring-etl:latest-main
- [x] 数据库备份：pg_dump 推送到 GitHub backup/cmdb_full_dump.sql
- [x] 本文档：记录所有错误、设计决策、部署流程
- [ ] 确认新云主机 IP 和登录信息
- [ ] 验证前端 /topology 页面（系统分组虚线框 + 跨系统线条）
