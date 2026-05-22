#!/bin/bash
# 知识库每月自动更新脚本
# 添加到 crontab: 0 3 1 * * /path/to/update_knowledge_base.sh

set -e

echo "========================================"
echo "知识库月度自动更新"
echo "========================================"
echo "时间：$(date)"

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境（如果有）
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 检查 Redis 是否运行
if ! redis-cli ping &> /dev/null; then
    echo "警告：Redis 未运行，尝试启动..."
    redis-server --daemonize yes || true
fi

# 发送知识库更新任务到 Celery
echo "正在触发知识库更新任务..."
python -c "
from app.tasks import update_knowledge_base_task
from app.celery_config import celery_app

# 异步执行更新任务
result = update_knowledge_base_task.delay(force=False)
print(f'任务已提交，Task ID: {result.id}')

# 等待结果（最多等待 5 分钟）
import time
start = time.time()
while time.time() - start < 300:
    time.sleep(5)
    if result.ready():
        try:
            res = result.get(timeout=10)
            print(f'更新完成：{res}')
            break
        except Exception as e:
            print(f'更新失败：{e}')
            break
"

echo ""
echo "========================================"
echo "更新检查完成"
echo "========================================"
