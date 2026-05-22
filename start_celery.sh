#!/bin/bash

echo "========================================"
echo "启动 Celery Worker"
echo "========================================"

# 检查 Redis 是否运行
if ! command -v redis-cli &> /dev/null; then
    echo "错误：redis-cli 未找到，请先安装 Redis"
    echo "macOS: brew install redis"
    echo "Linux: sudo apt-get install redis-server"
    exit 1
fi

# 测试 Redis 连接
if ! redis-cli ping &> /dev/null; then
    echo "错误：无法连接到 Redis，请先启动 Redis 服务"
    echo "macOS: brew services start redis"
    echo "Linux: sudo systemctl start redis-server"
    exit 1
fi

echo "Redis 连接成功"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 启动 Celery Worker
echo "正在启动 Celery Worker..."
python -m celery -A app.celery_config worker --loglevel=info --concurrency=2
