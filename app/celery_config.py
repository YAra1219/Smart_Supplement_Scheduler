"""
Celery 配置

使用方式:
1. 启动 Redis: redis-server
2. 启动 Celery Worker: celery -A app.celery_config worker --loglevel=info
3. 启动 FastAPI: python -m uvicorn app.main:app --reload
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Redis 配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Celery 配置
celery_app = Celery(
    "smart_supplement",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)

# 任务配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 任务最大执行时间 5 分钟
    task_soft_time_limit=240,  # 软时间限制 4 分钟
    worker_prefetch_multiplier=1,  # 每次只取 1 个任务
    broker_connection_retry_on_startup=True,
)

# 导入任务模块以自动注册所有 Celery 任务
import app.tasks  # noqa: E402
