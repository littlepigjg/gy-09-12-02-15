#!/bin/bash
# 一键构建并启动社交网络分析服务（Docker）
# 用法: bash start-docker.sh [port]
set -e

PORT="${1:-8000}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# 前置检查
if ! command -v docker >/dev/null 2>&1; then
    echo "错误: 未检测到 Docker，请先安装 Docker"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "错误: Docker 服务未启动，请先启动 Docker"
    exit 1
fi

echo "构建镜像并启动服务（端口 $PORT）..."
PORT="$PORT" docker compose up -d --build

echo ""
echo "✅ 启动完成，访问 http://localhost:$PORT"
echo "   查看日志: docker compose logs -f"
echo "   停止服务: docker compose down"
