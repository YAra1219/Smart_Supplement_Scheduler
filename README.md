# Smart Supplement Scheduler

一款 AI 驱动的膳食补充剂管理工具。用户通过拍照上传补剂瓶标签，系统自动识别成分，结合权威医学数据库进行安全性校验，并基于个人作息时间生成科学的每日服用排期计划。

## 功能特点

- **拍照识别** - 上传补剂瓶标签照片，AI 自动提取成分信息
- **安全校验** - 集成 NIH、RxNorm、OpenFDA 等权威数据库，检测成分风险与药物相互作用
- **智能排期** - 基于营养学规则（脂溶性/水溶性、吸收竞争、协同作用）优化服用时间
- **异步处理** - 复杂分析任务通过 Celery + Redis 异步执行，支持进度实时推送

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + Vite + Tailwind CSS |
| 后端 | FastAPI + Uvicorn |
| 任务队列 | Celery + Redis |
| 向量数据库 | ChromaDB |
| LLM | 通义千问 (DashScope) |
| 数据解析 | NIH / RxNorm / OpenFDA |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Redis

### 安装与运行

```bash
# 1. 克隆仓库
git clone https://github.com/YAra1219/Smart_Supplement_Scheduler.git
cd Smart_Supplement_Scheduler

# 2. 创建 Python 虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 安装前端依赖
cd UI && npm install && cd ..

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 DASHSCOPE_API_KEY

# 6. 一键启动所有服务
./run_all.sh
```

启动后访问：
- 前端：`http://localhost:5173`
- 后端 API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

## 项目结构

```
.
├── app/                      # FastAPI 后端
│   ├── main.py               # 应用入口
│   ├── vision.py             # 图像识别（OCR + LLM）
│   ├── safety_checker.py     # 安全校验
│   ├── schedule_generator.py # 排期生成
│   ├── rag.py                # RAG 知识检索
│   ├── tasks.py              # Celery 异步任务
│   └── celery_config.py      # Celery 配置
├── UI/                       # React 前端
│   ├── src/                  # 页面与组件
│   └── dist/                 # 构建产物
├── knowledge_base/           # 营养学与医学知识库
├── nih_data_processed/       # NIH 数据处理结果
├── requirements.txt          # Python 依赖
└── run_all.sh                # 一键启动脚本
```

## 核心 API

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/parse-image` | 解析补剂标签图片 |
| POST | `/api/generate-schedule` | 生成服用排期 |
| POST | `/api/generate-schedule/stream` | 流式生成排期（SSE） |
| POST | `/api/async/full-process` | 提交异步完整分析任务 |
| GET | `/api/task/{task_id}` | 查询异步任务状态 |
| GET | `/health` | 服务健康检查 |

## 许可证

MIT
