#!/bin/bash
set -e

echo "🚀 开始设置 Demo 环境..."

# 检查 docker-compose 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose 未安装"
    exit 1
fi

# 启动服务
echo "📦 启动 Docker 服务..."
docker compose up -d

# 等待 postgres 启动
echo "⏳ 等待 PostgreSQL 启动..."
until docker compose exec postgres pg_isready -U postgres; do
  sleep 1
done

# 初始化数据库
echo "🔧 初始化数据库..."
python3 scripts/init_db.py

# 加载种子数据
echo "🌱 加载种子数据..."
python3 scripts/seed_phase2.py

# 生成模拟数据
echo "🎭 生成模拟数据..."
python3 scripts/generate_demo_data.py

echo "✅ Demo 环境设置完成！"
echo "前端地址: http://localhost:3000"
