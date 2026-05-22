#!/bin/bash

echo "========================================"
echo "  Smart Supplement Scheduler"
echo "  同时启动前后端服务"
echo "========================================"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "未找到虚拟环境，正在创建..."
    python3 -m venv venv
    source venv/bin/activate
    echo "安装依赖..."
    pip install -r requirements.txt -q
fi

echo "Python 版本：$(python --version)"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "未找到 .env 文件"
    if [ -f .env.example ]; then
        echo "正在从 .env.example 创建 .env..."
        cp .env.example .env
        echo "请编辑 .env 文件并填入你的 DASHSCOPE_API_KEY"
        exit 1
    fi
fi

# 启动 Redis（如果未运行）
if ! redis-cli ping &> /dev/null; then
    echo "启动 Redis..."
    redis-server --daemonize yes
    sleep 1
fi

if redis-cli ping &> /dev/null; then
    echo "Redis 运行正常"
else
    echo "Redis 启动失败，请先安装：brew install redis"
    exit 1
fi

# 启动 Celery Worker（后台）
echo ""
echo "启动 Celery Worker..."
python -m celery -A app.celery_config worker --loglevel=info --concurrency=2 &
CELERY_PID=$!
echo "Celery Worker 已启动 (PID: $CELERY_PID)"

# 启动后端（后台）
echo ""
echo "启动后端服务..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "后端服务已启动 (PID: $BACKEND_PID)"

# 等待后端启动
sleep 3

# 检查后端是否运行
if curl -s http://localhost:8000/health > /dev/null; then
    echo "后端服务运行正常"
else
    echo "后端服务启动失败"
    kill $BACKEND_PID 2>/dev/null
    kill $CELERY_PID 2>/dev/null
    exit 1
fi

# 启动前端
echo ""
echo "启动前端服务..."
cd UI
npm run dev &
FRONTEND_PID=$!
cd ..
echo "前端服务已启动 (PID: $FRONTEND_PID)"

echo ""
echo "========================================"
echo "  服务地址："
echo "  前端：http://localhost:5173"
echo "  后端：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo "========================================"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo ""

# 捕获退出信号
trap "echo 'Stopping...'; kill $FRONTEND_PID 2>/dev/null; kill $BACKEND_PID 2>/dev/null; kill $CELERY_PID 2>/dev/null; exit" INT TERM EXIT

# 等待
wait
