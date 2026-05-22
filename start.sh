#!/bin/bash

echo "========================================"
echo "  Smart Med-Supplement Scheduler"
echo "  快速启动脚本"
echo "========================================"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "⚠️ 未找到虚拟环境，正在创建..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 安装依赖..."
    pip install -r requirements.txt -q
fi

# 检查 Python
echo "✓ Python 版本：$(python --version)"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️ 未找到 .env 文件"
    if [ -f .env.example ]; then
        echo "📋 正在从 .env.example 创建 .env..."
        cp .env.example .env
        echo "❗ 请编辑 .env 文件并填入你的 DASHSCOPE_API_KEY"
        exit 1
    fi
fi

# 启动后端
echo ""
echo "🚀 启动后端服务..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "✓ 后端服务已启动 (PID: $BACKEND_PID)"

# 等待后端启动
sleep 3

# 检查后端是否运行
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ 后端服务运行正常"
else
    echo "❌ 后端服务启动失败"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "========================================"
echo "  后端服务已启动："
echo "  http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo "========================================"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 捕获退出信号
trap "echo 'Stopping...'; kill $BACKEND_PID 2>/dev/null; exit" INT TERM EXIT

# 等待
wait
