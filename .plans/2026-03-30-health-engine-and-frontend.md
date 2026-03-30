# Feature: Phase 2 Step 3+4 — 健康度计算引擎 + 前端三视图

## 功能描述

实现监控 ETL 平台认知层的两个核心组件：

1. **Step 3: 健康度计算引擎** — 定时服务，从 ClickHouse 拉取最新指标数据，按 entity_type_def 中的 health model 计算每个实体的健康评分，写回 entity 表
2. **Step 4: 前端三视图** — 总览 Dashboard、资源拓扑图、智能问答界面

## 方案描述

### Step 3: 健康度计算引擎

设计为独立的 Python 服务（`services/health-engine`），定时循环：
1. 从 Postgres 读取所有 active entity 及其 type_def 的 health model
2. 从 ClickHouse 查询对应指标的最新值
3. 按 health method（weighted_avg / children_avg）计算健康评分
4. 更新 entity 表的 health_score / health_level / health_detail / risk_score
5. 计算级联影响（blast_radius / propagation_hops）

**健康度算法：**
- `weighted_avg`: 按维度权重加权平均，每个维度从指标值映射到 0-100 分
- `children_avg`: 取下游子实体的健康评分平均值
- 阈值映射：指标值 → 评分（线性插值，基于 definition 中的 thresholds）
- 健康等级：healthy(≥80) / warning(≥60) / critical(≥30) / down(<30)

### Step 4: 前端三视图

在现有 React + Ant Design 前端基础上扩展三个页面：

1. **总览 Dashboard** (`/overview`)
   - 全局健康度仪表盘（大数字 + 颜色）
   - 健康分布饼图（healthy/warning/critical/down）
   - 业务健康度卡片列表
   - 异常实体 Top 10 列表
   - 资源规模统计

2. **资源拓扑图** (`/topology`)
   - 基于实体关系的拓扑可视化（D3.js 或类似方案）
   - 节点颜色 = 健康度，大小 = 连接数
   - 支持按业务/类型筛选
   - 点击节点展示实体详情

3. **智能问答** (`/chat`)
   - 简单的问答界面（先做基础版，后续接入 AI）
   - 支持查询实体状态、健康度、关系
   - 自然语言 → API 调用

## 功能元数据

- **功能类型:** 新功能
- **预估复杂度:** 高
- **主要影响组件:** services/health-engine/, frontend/, services/cmdb-api/
- **外部依赖:** ClickHouse (指标数据), Postgres (CMDB)

---

## 上下文引用

### 相关代码文件

- `services/cmdb-api/app/models/__init__.py` — Entity / EntityTypeDef 模型，含 health_score/health_level/health_detail/risk_score/blast_radius 字段
- `services/cmdb-api/app/routers/overview.py` — 已有 /overview 和 /data-quality API，前端可直接调用
- `services/cmdb-api/app/routers/entities.py` — 实体 CRUD + /cognition + /health 端点
- `demo/topology.py` — 拓扑定义、HEALTH_OVERRIDES、故障场景
- `demo/factory.py` — 数据工厂，已有 trace/log 模拟
- `frontend/src/pages/Cmdb.tsx` — 现有 CMDB 页面，参考其 API 调用 pattern
- `frontend/src/App.tsx` — 路由和布局
- `storage/postgres/schema.sql` — 数据库 schema

### 需要创建的新文件

- `services/health-engine/Dockerfile` — 健康引擎容器
- `services/health-engine/requirements.txt` — 依赖
- `services/health-engine/app/main.py` — 引擎主循环
- `services/health-engine/app/calculator.py` — 健康度计算逻辑
- `services/health-engine/app/impact.py` — 级联影响计算
- `frontend/src/pages/Overview.tsx` — 总览 Dashboard
- `frontend/src/pages/Topology.tsx` — 资源拓扑图
- `frontend/src/pages/Chat.tsx` — 智能问答
- `frontend/package.json` — 更新依赖（添加图表库）

### 需要遵循的 Pattern

**API 调用 pattern (前端):**
```tsx
const API_BASE = '/api/v1/cmdb';
const res = await axios.get(`${API_BASE}/entities`, { params });
```

**ClickHouse 查询 pattern:**
```python
r = requests.post(CLICKHOUSE_URL, data=sql, timeout=10)
data = r.json()
```

**健康度阈值映射 (来自 type_def.definition):**
```json
{
  "health": {
    "method": "weighted_avg",
    "dimensions": [
      {"name": "latency", "metric": "http.server.request.duration.p99", "weight": 0.4},
      {"name": "error_rate", "metric": "http.server.request.error_rate", "weight": 0.3},
      {"name": "saturation", "metric": "system.cpu.usage", "weight": 0.3}
    ]
  }
}
```

---

## 实施计划

### Phase 1: 健康度计算引擎核心

创建 health-engine 服务，实现健康度计算逻辑。

### Phase 2: 健康引擎集成

将 health-engine 集成到 docker-compose，添加 API 端点触发计算。

### Phase 3: 前端总览 Dashboard

实现 Overview 页面，展示全局健康度、分布、异常实体。

### Phase 4: 前端资源拓扑图

实现 Topology 页面，基于实体关系的可视化。

### Phase 5: 前端智能问答

实现 Chat 页面，支持自然语言查询。

### Phase 6: 部署验证

部署到服务器，端到端验证。

---

## 逐步任务清单

### Task 1: CREATE services/health-engine/app/calculator.py

- **实现**: 健康度计算核心逻辑
  - `calculate_entity_health(entity, type_def, metrics_data)` → health_score, health_detail
  - `metric_value_to_score(value, thresholds)` → 0-100 分（线性插值）
  - 支持 weighted_avg 方法
  - 支持 children_avg 方法（从子实体 health_score 聚合）
- **Pattern**: 参考 demo/topology.py 的 HEALTH_OVERRIDES 和 type_def.definition.health
- **坑点**: 指标可能缺失（返回 None），需处理降级逻辑
- **验证**: `python -c "from app.calculator import calculate_entity_health; print('OK')"`

### Task 2: CREATE services/health-engine/app/impact.py

- **实现**: 级联影响计算
  - `calculate_blast_radius(entity_guid, relationships)` → blast_radius (受影响实体数)
  - `calculate_propagation_hops(entity_guid, relationships)` → propagation_hops (最大传播深度)
  - BFS 遍历关系图
- **验证**: `python -c "from app.impact import calculate_blast_radius; print('OK')"`

### Task 3: CREATE services/health-engine/app/main.py

- **实现**: 健康引擎主循环
  - 定时循环（默认 60s）
  - 从 Postgres 加载所有 active entity + type_def
  - 从 ClickHouse 查询指标最新值（批量查询，按 service_name/host_name 分组）
  - 调用 calculator 计算健康度
  - 调用 impact 计算影响范围
  - 批量更新 entity 表
  - 支持 `--once` 模式（单次计算后退出，便于测试）
- **Pattern**: 参考 demo/factory.py 的 ClickHouse 查询方式
- **坑点**: ClickHouse 查询需用最近 5 分钟的数据，避免查全量
- **验证**: `cd services/health-engine && python -m app.main --once`

### Task 4: CREATE services/health-engine/Dockerfile + requirements.txt

- **实现**: 容器化配置
- **Pattern**: 参考 services/cmdb-api/Dockerfile
- **验证**: `docker build services/health-engine/`

### Task 5: UPDATE docker-compose.app.yml

- **实现**: 添加 health-engine 服务
- **验证**: `docker compose -f docker-compose.app.yml config`

### Task 6: CREATE frontend/src/pages/Overview.tsx

- **实现**: 总览 Dashboard
  - 调用 `/api/v1/overview` 获取数据
  - 全局健康度大数字（加权平均）
  - 健康分布 Ant Design Pie/PieChart
  - 业务健康度 Card 列表
  - 异常实体 Table（Top 10 by risk_score）
  - 资源规模统计
- **依赖**: npm install @ant-design/charts（或用 antd Statistic + Progress 简化）
- **Pattern**: 参考 frontend/src/pages/Cmdb.tsx 的结构
- **坑点**: 图表库可能增加打包体积，先用 antd 内置组件简化
- **验证**: 页面渲染无报错

### Task 7: CREATE frontend/src/pages/Topology.tsx

- **实现**: 资源拓扑图
  - 调用 `/api/v1/cmdb/entities?limit=500` + `/api/v1/cmdb/entities/{id}/relations` 获取数据
  - 用 SVG/CSS 手绘简单拓扑（避免引入重量级图表库）
  - 或用 @antv/x6（轻量图库）
  - 节点 = 实体，边 = 关系，颜色 = 健康度
  - 支持按 type_name 筛选
  - 点击节点弹出实体详情 Drawer
- **坑点**: 关系数据需二次查询（N+1），先批量获取再本地组装
- **验证**: 拓扑图正确渲染

### Task 8: CREATE frontend/src/pages/Chat.tsx

- **实现**: 智能问答界面
  - Chat UI（消息列表 + 输入框）
  - 简单的关键词匹配 → API 调用
  - "XX 的健康度" → 查询实体 health
  - "有多少个 XX" → 查询实体列表
  - "异常的实体" → 查询 health_level!=healthy
- **Pattern**: 基础版不需要 AI，直接关键词解析
- **验证**: 基本问答可工作

### Task 9: UPDATE frontend/src/App.tsx

- **实现**: 添加三个新路由和菜单项
  - `/overview` → Overview
  - `/topology` → Topology  
  - `/chat` → Chat
- **验证**: 路由跳转正常

### Task 10: UPDATE frontend/package.json

- **实现**: 添加依赖（如需要图表库）
- **验证**: npm install 成功

### Task 11: 部署 + 端到端验证

- **实现**: 
  - 本地 git commit
  - 推送到服务器
  - docker compose up -d --build
  - 验证 health-engine 运行
  - 验证前端三个页面可访问
- **验证**: 浏览器访问 http://8.146.232.9:3000

---

## 验证命令

```bash
# Level 1: 代码质量
cd services/health-engine && python -m py_compile app/main.py app/calculator.py app/impact.py
cd frontend && npx tsc --noEmit

# Level 2: 健康引擎单次运行
cd services/health-engine && python -m app.main --once

# Level 3: 前端构建
cd frontend && npm run build

# Level 4: 部署验证
docker compose -f docker-compose.app.yml up -d --build
curl http://localhost:8001/api/v1/overview
curl http://localhost:3000
```

---

## 验收标准

- [ ] 健康引擎能从 ClickHouse 拉取指标，计算健康评分，写回 entity 表
- [ ] 前端总览页面展示全局健康度、分布、异常实体
- [ ] 前端拓扑图展示实体关系和健康状态
- [ ] 前端问答页面支持基本查询
- [ ] 所有新代码可正常构建和部署
- [ ] 现有功能无回归

---

## 备注

- 健康引擎优先用 weighted_avg，children_avg 作为后续增强
- 前端图表先用 antd 内置组件，避免引入过重的图表库
- 智能问答先做关键词匹配版，后续可接入 LLM
- ClickHouse 指标查询用最近 5 分钟窗口，避免查询全量数据
