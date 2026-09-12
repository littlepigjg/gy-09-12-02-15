#!/bin/bash
# 启动社交网络分析服务
# 用法: bash run.sh [port]
set -e

PORT="${1:-8000}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# 安装依赖（若 flask 尚未安装；已安装则跳过）
if ! python3 -c "import flask" >/dev/null 2>&1; then
    python3 -m pip install -r requirements.txt || \
        python3 -m pip install --break-system-packages -r requirements.txt
fi

# 启动服务
python3 -m backend.app --port "$PORT"
