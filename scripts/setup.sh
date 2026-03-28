#!/bin/bash
# ============================================================
# Monitoring ETL Platform - 云服务器一键部署脚本
# 适用于: Ubuntu 22.04 / 24.04
# 用法: curl -fsSL <url>/setup.sh | bash
# 或:   bash setup.sh
# ============================================================

set -e

# ---- 配置 ----
REPO_URL="https://github.com/hackwoman/monitoring-etl.git"
PROJECT_DIR="$HOME/monitoring-etl"
BRANCH="main"

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---- 检查系统 ----
check_system() {
    info "检查系统环境..."
    if [ ! -f /etc/os-release ]; then
        error "无法识别操作系统"
        exit 1
    fi
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        warn "脚本针对 Ubuntu 优化，当前系统: $ID，可能需要手动调整"
    fi
    info "系统: $PRETTY_NAME"
}

# ---- 安装 Docker ----
install_docker() {
    if command -v docker &>/dev/null; then
        info "Docker 已安装: $(docker --version)"
    else
        info "安装 Docker..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq docker.io docker-compose-v2
        sudo systemctl enable docker
        sudo systemctl start docker
        sudo usermod -aG docker $USER
        info "Docker 安装完成"
    fi

    # 验证 docker 能用
    if ! docker ps &>/dev/null; then
        # 当前 shell 可能还没拿到 group 权限，用 sudo
        warn "当前用户无 docker 权限，使用 sudo 运行"
        DOCKER_CMD="sudo docker"
    else
        DOCKER_CMD="docker"
    fi
    info "Docker 版本: $($DOCKER_CMD --version)"
}

# ---- 安装 Git ----
install_git() {
    if command -v git &>/dev/null; then
        info "Git 已安装: $(git --version)"
    else
        info "安装 Git..."
        sudo apt-get install -y -qq git
    fi
}

# ---- 克隆项目 ----
clone_project() {
    if [ -d "$PROJECT_DIR/.git" ]; then
        info "项目已存在，拉取最新代码..."
        cd "$PROJECT_DIR"
        git pull origin $BRANCH
    else
        info "克隆项目..."
        git clone -b $BRANCH "$REPO_URL" "$PROJECT_DIR"
        cd "$PROJECT_DIR"
    fi
    info "项目目录: $PROJECT_DIR"
}

# ---- 配置防火墙 ----
setup_firewall() {
    if command -v ufw &>/dev/null; then
        info "配置防火墙..."
        # SSH
        sudo ufw allow 22/tcp 2>/dev/null || true
        # 前端
        sudo ufw allow 3000/tcp 2>/dev/null || true
        # API (可选，生产环境建议关掉)
        sudo ufw allow 8000/tcp 2>/dev/null || true
        # 启用防火墙（如果未启用）
        echo "y" | sudo ufw enable 2>/dev/null || true
        info "防火墙配置完成"
    else
        warn "ufw 未安装，跳过防火墙配置（请手动确保端口 3000 可访问）"
    fi
}

# ---- 启动服务 ----
start_services() {
    info "拉取镜像..."
    $DOCKER_CMD compose pull 2>/dev/null || true

    info "启动所有服务..."
    if [ "$DOCKER_CMD" = "sudo docker" ]; then
        sudo docker compose up -d
    else
        docker compose up -d
    fi
    info "服务启动命令已执行"
}

# ---- 等待服务就绪 ----
wait_for_services() {
    info "等待服务就绪（最多 60 秒）..."

    local max_wait=60
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        # 检查所有容器是否 running
        local total=$($DOCKER_CMD compose ps --format json 2>/dev/null | wc -l)
        local running=$($DOCKER_CMD compose ps --status running --format json 2>/dev/null | wc -l)

        if [ "$running" -gt 0 ] && [ "$running" -eq "$total" ]; then
            info "所有 $running 个服务已启动"
            break
        fi

        sleep 3
        elapsed=$((elapsed + 3))
        echo -n "."
    done
    echo ""

    if [ $elapsed -ge $max_wait ]; then
        warn "部分服务可能未完全就绪，请检查日志:"
        warn "  $DOCKER_CMD compose logs"
    fi
}

# ---- 健康检查 ----
health_check() {
    info "执行健康检查..."

    local failed=0

    # PostgreSQL
    if $DOCKER_CMD compose exec -T postgres pg_isready -U postgres &>/dev/null; then
        info "  ✅ PostgreSQL OK"
    else
        warn "  ❌ PostgreSQL 未就绪"
        failed=$((failed + 1))
    fi

    # ClickHouse
    if curl -sf http://localhost:8123/ping &>/dev/null; then
        info "  ✅ ClickHouse OK"
    else
        warn "  ❌ ClickHouse 未就绪"
        failed=$((failed + 1))
    fi

    # CMDB API
    if curl -sf http://localhost:8001/health &>/dev/null; then
        info "  ✅ CMDB API OK"
    else
        warn "  ❌ CMDB API 未就绪"
        failed=$((failed + 1))
    fi

    # Log API
    if curl -sf http://localhost:8002/health &>/dev/null; then
        info "  ✅ Log API OK"
    else
        warn "  ❌ Log API 未就绪"
        failed=$((failed + 1))
    fi

    # Frontend
    if curl -sf http://localhost:3000 &>/dev/null; then
        info "  ✅ Frontend OK"
    else
        warn "  ❌ Frontend 未就绪"
        failed=$((failed + 1))
    fi

    if [ $failed -eq 0 ]; then
        info "所有服务健康检查通过！"
    else
        warn "$failed 个服务未就绪，可能需要等待几秒"
    fi
}

# ---- 输出访问信息 ----
print_access_info() {
    local ip=$(curl -sf ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

    echo ""
    echo "============================================"
    echo "  🚀 Monitoring ETL Platform 部署完成！"
    echo "============================================"
    echo ""
    echo "  前端界面:   http://${ip}:3000"
    echo "  CMDB API:   http://${ip}:8001/docs"
    echo "  Log API:    http://${ip}:8002/docs"
    echo "  API 网关:   http://${ip}:8000/docs"
    echo "  Vector:     http://${ip}:8686"
    echo ""
    echo "  常用命令:"
    echo "    查看状态:  docker compose ps"
    echo "    查看日志:  docker compose logs -f"
    echo "    停止服务:  docker compose down"
    echo "    重启服务:  docker compose restart"
    echo "============================================"
}

# ---- 主流程 ----
main() {
    echo ""
    info "=========================================="
    info "  Monitoring ETL Platform 部署脚本"
    info "=========================================="
    echo ""

    check_system
    install_git
    install_docker
    setup_firewall
    clone_project
    start_services
    wait_for_services
    health_check
    print_access_info
}

main "$@"
