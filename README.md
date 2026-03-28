# Monitoring ETL Platform

> 数据接入零人工 · AI 贯穿全层 · 业务风险驱动 · AI 自主进化

智能监控数据 ETL 平台，支持数百至数千台云主机规模。

## Deploy (Cloud Server)

```bash
# 一行命令部署
curl -fsSL https://raw.githubusercontent.com/hackwoman/monitoring-etl/main/scripts/setup.sh | bash

# 或手动
git clone https://github.com/hackwoman/monitoring-etl.git
cd monitoring-etl
bash scripts/setup.sh
```

## Local Development

```bash
docker compose up -d
docker compose ps

# 访问
# 前端: http://localhost:3000
# API:  http://localhost:8000/docs
# CMDB: http://localhost:8001/docs
# Logs: http://localhost:8002/docs
```

## Architecture

```
数据源 → OTel Collector → Vector ETL → ClickHouse(日志) + PostgreSQL(CMDB)
                                    ↓
                              API Gateway → React 前端
```

## Modules

| Service | Port | Description |
|---------|------|-------------|
| frontend | 3000 | React + Ant Design UI |
| api-gateway | 8000 | 统一 API 入口 |
| cmdb-api | 8001 | CMDB 实体/关系管理 |
| log-api | 8002 | 日志查询 (ClickHouse) |
| vector | 8686 | ETL 管道 |
| postgres | 5432 | CMDB 存储 |
| clickhouse | 8123 | 日志存储 |

## Phase 1 Scope

- ✅ 日志采集 (OTel Collector)
- ✅ ETL 管道 (Vector)
- ✅ CMDB 实体管理 (PostgreSQL)
- ✅ 日志搜索 API
- ✅ 基础前端

See [Architecture Design](../.plans/etl-architecture-design.md) for full design.
