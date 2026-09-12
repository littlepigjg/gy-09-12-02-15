# 社交网络分析服务镜像
# 基于 python:3.12-slim 构建，一键启动 Flask + Vue 前端
FROM python:3.12-slim

WORKDIR /app

# 安装依赖（利用缓存层：先复制 requirements 再安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码（后端 + 前端，前端依赖已本地化无需外网）
COPY backend ./backend
COPY frontend ./frontend

# 数据目录（SQLite 数据库持久化挂载点）
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8000

# 健康检查：探测统计接口
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/stats', timeout=3)" || exit 1

# 启动服务
CMD ["python3", "-m", "backend.app", "--host", "0.0.0.0", "--port", "8000"]
