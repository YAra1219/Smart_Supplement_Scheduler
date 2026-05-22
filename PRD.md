# Smart Supplement Scheduler (智能补剂排期助手)

## 产品需求文档 (PRD)

> **版本**: 0.1.0  
> **日期**: 2026-05-17  
> **状态**: 开发中  

---

## 1. 产品概述

### 1.1 产品名称

- **中文**: 智能补剂排期助手
- **英文**: Smart Supplement Scheduler

### 1.2 产品定位

一款面向健康-conscious 用户的 AI 驱动型膳食补充剂管理工具。用户通过拍照上传补剂瓶标签，系统自动识别成分，结合权威医学数据库进行安全性校验，并基于用户的个人作息时间生成科学、无冲突的每日服用排期计划。

### 1.3 核心价值主张

- **智能识别**: 拍照即可识别补剂成分，无需手动输入
- **安全优先**: 集成 RxNorm + OpenFDA + NIH 三大权威数据库，层层安全校验
- **科学排期**: 基于营养学规则（脂溶性/水溶性、吸收竞争、协同作用）优化服用时间
- **药物交互**: 自动检测用户当前用药与补剂的相互作用风险

### 1.4 目标用户

- 日常服用 3 种以上膳食补充剂的都市人群
- 正在服用处方药且同时服用补剂的中老年人群
- 健身爱好者（蛋白粉、支链氨基酸、肌酸等运动补剂）

---

## 2. 用户旅程与功能流程

### 2.1 用户旅程地图

```
发现产品 → 设置作息 → 拍照扫描 → AI 分析 → 查看排期 → 每日提醒
```

### 2.2 核心功能流程

#### 流程 1: 完整异步流程（推荐）

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Setup  │───→│  Scan   │───→│ Thinking│───→│Dashboard│───→│  每日提醒 │
│ 设置作息 │    │拍照上传  │    │ AI 分析  │    │查看排期  │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

**步骤详解**:

1. **Setup 设置页** (`/`)：用户设置起床、早餐、午餐、晚餐、睡觉时间，填写当前用药（选填）
2. **Scan 扫描页** (`/scan`)：用户拍摄补剂瓶标签照片，支持多张连拍
3. **Thinking 分析页** (`/thinking`)：展示实时进度（识别成分 → 安全校验 → 排期生成 → 药物交互检查）
4. **Dashboard 排期页** (`/dashboard`)：展示时间轴形式的排期计划，支持点击详情

#### 流程 2: 同步 API 流程

- `POST /api/parse-image`：即时解析图片，返回 MedItem 列表（~3-5 秒）
- `POST /api/generate-schedule`：根据补剂和作息生成排期（~2-3 秒）
- `POST /api/generate-schedule/stream`：流式生成，实时展示思考过程（SSE）

#### 流程 3: 异步任务流程

- `POST /api/async/full-process`：提交完整任务，返回 `task_id`
- `GET /api/task/{task_id}`：轮询任务状态和进度
- 全流程耗时：~8-15 秒

---

## 3. 功能模块详细设计

### 3.1 前端模块 (React + Vite + Tailwind CSS)

#### 3.1.1 页面结构

| 页面 | 路由 | 核心功能 |
|------|------|----------|
| SetupPage | `/` | 作息设置、用药录入 |
| ScanPage | `/scan` | 图片拍摄/上传、提交分析 |
| ThinkingPage | `/thinking` | 进度轮询、动画展示 |
| DashboardPage | `/dashboard` | 排期展示、详情弹窗、安全警告 |

#### 3.1.2 UI 设计规范

- **风格**: Glassmorphism（毛玻璃效果）+ Mesh Gradient 背景
- **配色**: 紫色/粉色/蓝色渐变主色调，灰色 `#F2F2F7` 背景
- **圆角**: 大圆角设计（`rounded-[28px]`）
- **动效**: Pulse 呼吸动画、渐进式进度圆环、卡片悬浮效果
- **移动端优先**: 最大宽度 `383px`，适配手机竖屏

#### 3.1.3 组件清单

- `GlassCard`: 毛玻璃卡片容器
- `MeshGradientBackground`: 动态渐变背景
- 页面级组件: `SetupPage`, `ScanPage`, `ThinkingPage`, `DashboardPage`

### 3.2 后端模块 (FastAPI + Python)

#### 3.2.1 API 端点总览

| 端点 | 方法 | 类型 | 限流 | 描述 |
|------|------|------|------|------|
| `/` | GET | 同步 | 100/min | 服务状态 |
| `/health` | GET | 同步 | 100/min | 健康检查 |
| `/api/parse-image` | POST | 同步 | 10/min | 图片解析 |
| `/api/generate-schedule` | POST | 同步 | 10/min | 生成排期 |
| `/api/generate-schedule/stream` | POST | 流式 | 10/min | SSE 流式生成 |
| `/api/full-process` | POST | 同步 | 10/min | 完整流程 |
| `/api/async/parse-image` | POST | 异步 | 10/min | 异步图片解析 |
| `/api/async/generate-schedule` | POST | 异步 | 10/min | 异步排期生成 |
| `/api/async/full-process` | POST | 异步 | 10/min | 异步完整流程 |
| `/api/task/{task_id}` | GET | 查询 | 60/min | 任务状态查询 |
| `/api/init-knowledge-base` | POST | 同步 | 5/hour | 初始化知识库 |
| `/api/async/init-knowledge-base` | POST | 异步 | 2/hour | 异步初始化知识库 |
| `/api/knowledge-base/status` | GET | 查询 | 30/min | 知识库状态 |
| `/api/knowledge-base/check` | POST | 查询 | 10/min | 检查更新 |
| `/api/knowledge-base/update` | POST | 异步 | 2/hour | 执行更新 |
| `/api/knowledge-base/history` | GET | 查询 | 30/min | 更新历史 |

#### 3.2.2 核心服务层

| 模块 | 文件 | 职责 |
|------|------|------|
| Vision 服务 | `app/vision.py` | 调用 qwen-vl-max 识别补剂图片 |
| 排期生成器 | `app/schedule_generator.py` | 调用 qwen-max 生成每日排期 |
| 安全校验器 | `app/safety_checker.py` | RxNorm + OpenFDA 安全校验 |
| RAG 引擎 | `app/rag.py` | ChromaDB + text-embedding-v3 知识检索 |
| LLM 客户端 | `app/llm_client.py` | 统一 LLM 接口（重试、熔断、降级） |
| 任务队列 | `app/tasks.py` | Celery 异步任务定义 |
| 知识库更新器 | `app/knowledge_base_updater.py` | NIH 数据自动抓取与版本管理 |

### 3.3 数据模型

```python
# 补剂条目
MedItem:
  - name: str                    # 品牌名或通用名
  - type: str                    # 类型（supplement）
  - active_ingredients: List[str] # 活性成分列表
  - recommended_dosage: str      # 推荐剂量
  - is_prescription: bool        # 是否处方药
  - prescription_warning: str    # 处方药警告

# 用户作息
UserRoutine:
  - wake_up_time: str
  - breakfast_time: str
  - lunch_time: str
  - dinner_time: str
  - sleep_time: str
  - current_medications: List[str]  # 当前用药

# 排期条目
ScheduleEntry:
  - time: str      # 24小时制 HH:MM
  - action: str    # 服用动作
  - reasoning: str # 科学依据

# 最终计划
FinalPlan:
  - status: str               # success / rejected_due_to_safety
  - rejection_reason: str     # 拒绝原因
  - schedule: List[ScheduleEntry]
  - warnings: List[str]
  - safety_score: int         # 0-100
  - data_sources: List[str]   # 数据来源 URL
  - drug_interactions: List[str]  # 药物交互警告
```

---

## 4. AI 与安全架构

### 4.1 三层安全架构

```
┌─────────────────────────────────────────────────────────┐
│ Layer 3: 排期生成 (qwen-max LLM)                        │
│ 输入: 安全评分 + RAG 规则 + 用户作息                     │
│ 输出: 带引用来源的排期计划                               │
└─────────────────────────────────────────────────────────┘
                           ▲
┌─────────────────────────────────────────────────────────┐
│ Layer 2: RAG 知识检索 (ChromaDB + text-embedding-v3)   │
│ 功能: 检索 Top-K 营养学规则（协同/冲突/最佳时间）        │
└─────────────────────────────────────────────────────────┘
                           ▲
┌─────────────────────────────────────────────────────────┐
│ Layer 1: 安全校验 (RxNorm + OpenFDA API)               │
│ • RxNorm 名称标准化 + RxCUI 标识                        │
│ • OpenFDA 不良事件 (FAERS) 查询                         │
│ • OpenFDA 召回信息查询                                  │
│ • OpenFDA 标签警告（黑盒警告/禁忌症）                    │
│ • Drug-Supplement 相互作用分析                          │
│ 输出: 安全评分 (0-100)，<50 拒绝                        │
└─────────────────────────────────────────────────────────┘
```

### 4.2 图像识别流程

```
用户上传图片
    │
    ▼
FastAPI 验证（类型/大小/空文件）
    │
    ▼
qwen-vl-max 识别 ──失败──▶ 重试(最多3次)
    │                          │
    │                          ▼
    │                      降级到 qwen-vl-plus
    ▼
返回 MedItem 列表（JSON 格式）
```

**耗时**: ~3-5 秒

### 4.3 异步任务进度追踪

```
 10%  开始解析图片
 40%  图片解析完成
 50%  安全性校验（RxNorm + OpenFDA）
 60%  开始生成排期
 70%  检索知识库 (RAG)
 80%  生成排期计划 (qwen-max)
 85%  检查药物-补剂相互作用
100%  完成
```

---

## 5. 知识库与数据管道

### 5.1 NIH 数据管道

```
NIH 官网 (ods.od.nih.gov)
    │
    ▼
scrape_nih_data.py 抓取原始文本
    │
    ▼
nih_data_raw/*.txt
    │
    ▼
clean_nih_data.py 清洗结构化
    │
    ▼
nih_data_processed/*.json  +  nih_data_markdown/*.md
    │
    ▼
text-embedding-v3 向量化
    │
    ▼
ChromaDB 持久化存储
    │
    ▼
查询时检索 Top-K 规则 → 作为 LLM 上下文
```

### 5.2 知识库自动更新

- **更新源**: NIH ODS (ods.od.nih.gov/factsheets/list-all/)
- **更新频率**: 每 30 天自动检查
- **增量更新**: 只更新有变化的部分
- **版本管理**: 时间戳版本号（如 `v20260517`）
- **变更日志**: 记录新增/更新/删除的补剂

### 5.3 数据结构示例 (Vitamin D)

```json
{
  "name": "Vitamin D",
  "name_en": "Vitamin D",
  "type": "维生素",
  "source_url": "https://ods.od.nih.gov/factsheets/VitaminD-Consumer",
  "best_timing": "随餐服用（脂溶性，需要脂肪帮助吸收）",
  "synergistic_supplements": ["维生素 K2", "钙", "镁"],
  "conflicting_supplements": [],
  "drug_interactions": [],
  "side_effects": ["恶心", "肾结石", "肾衰竭", "心脏问题"],
  "warnings": ["孕妇使用前请咨询医生", "请放置在儿童接触不到的地方"],
  "upper_limit": "25 MCG",
  "raw_content": { "intake": "...", "interactions": "...", "risks": "..." }
}
```

---

## 6. 工程化与稳定性

### 6.1 速率限制 (SlowAPI)

| 端点 | 限流策略 |
|------|----------|
| `/api/parse-image` | 10 次/分钟 |
| `/api/generate-schedule` | 10 次/分钟 |
| `/api/init-knowledge-base` | 5 次/小时 |
| `/api/task/{task_id}` | 60 次/分钟 |

### 6.2 重试与降级策略

```
主模型 (qwen-max / qwen-vl-max)
    │
    ├── 失败 ──▶ 重试（指数退避: 1s → 2s → 4s）
    │              │
    │              └── 仍失败 ──▶ 降级到 qwen-plus / qwen-vl-plus
    │
    └── 连续 5 次失败 ──▶ 熔断器 OPEN（60 秒后尝试恢复）
```

### 6.3 熔断器状态机

```
正常 (CLOSED) ──5 次失败──▶ 熔断 (OPEN) ──60 秒──▶ 半开 (HALF_OPEN) ──成功──▶ 恢复 (CLOSED)
                                                               │
                                                               └── 失败 ──▶ 熔断 (OPEN)
```

### 6.4 输入验证

- **文件类型**: `.jpg`, `.jpeg`, `.png`, `.webp`
- **文件大小**: ≤ 10MB
- **空文件检测**: 拒绝 0 字节文件
- **CORS**: 允许所有来源（开发环境）

### 6.5 异步任务配置

| 配置项 | 值 |
|--------|-----|
| 任务超时 | 300 秒（硬限制）/ 240 秒（软限制） |
| Worker 并发 | 每次只取 1 个任务（`prefetch_multiplier=1`） |
| 重试次数 | 2 次 |
| 时区 | Asia/Shanghai |

---

## 7. 技术栈

### 7.1 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3.1 | UI 框架 |
| Vite | 6.3.5 | 构建工具 |
| Tailwind CSS | 4.1.12 | 样式 |
| React Router | 7.13.0 | 路由 |
| Radix UI | 多个包 | 无障碍组件 |
| Lucide React | 0.487.0 | 图标 |
| Motion | 12.23.24 | 动画 |

### 7.2 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.14 | 运行时 |
| FastAPI | ≥0.109.0 | Web 框架 |
| Uvicorn | ≥0.27.0 | ASGI 服务器 |
| Pydantic | ≥2.6.0 | 数据验证 |
| Celery | ≥5.3.0 | 异步任务队列 |
| Redis | ≥5.0.0 | 消息代理 + 结果后端 |
| SlowAPI | ≥0.1.8 | 速率限制 |

### 7.3 AI / 数据

| 技术 | 版本 | 用途 |
|------|------|------|
| OpenAI SDK | ≥1.12.0 | DashScope API 调用 |
| ChromaDB | ≥0.4.22 | 向量数据库 |
| Pillow | ≥10.0.0 | 图像处理 |
| aiohttp | ≥3.9.0 | 异步 HTTP 客户端 |

### 7.4 外部 API

| API | 提供商 | 用途 | 费用 |
|-----|--------|------|------|
| qwen-vl-max | 阿里云 DashScope | 图像识别 | ¥0.012/次 |
| qwen-max | 阿里云 DashScope | 排期生成 | ¥0.04/次 |
| text-embedding-v3 | 阿里云 DashScope | 文本向量化 | ¥0.002/次 |
| RxNorm API | NLM (NIH) | 药物标准化 | 免费 |
| OpenFDA API | FDA | 药物安全数据 | 免费 |

---

## 8. 部署与运维

### 8.1 开发环境启动

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Celery Worker
./start_celery.sh

# Terminal 3: FastAPI
./start.sh

# Terminal 4: Frontend
cd UI && npm run dev
```

### 8.2 生产环境架构（建议）

```
┌─────────────────────────────────────────┐
│         Load Balancer (Nginx)           │
└─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  FastAPI 1   │ │  FastAPI 2   │ │  FastAPI 3   │
└──────────────┘ └──────────────┘ └──────────────┘
        │           │           │
        └───────────┼───────────┘
                    ▼
        ┌───────────────────────┐
        │    Redis Cluster      │
        └───────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Celery 1     │ │ Celery 2     │ │ Celery 3     │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 8.3 环境变量

```bash
# 必需
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 可选
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
OPENFDA_API_KEY=        # 提高 OpenFDA 限流
```

---

## 9. 成本估算

### 9.1 单次完整流程成本

| 项目 | 单价 | 单次用量 | 小计 |
|------|------|----------|------|
| qwen-vl-max | ¥0.012/次 | 1 次 | ¥0.012 |
| qwen-max | ¥0.04/次 | 1 次 | ¥0.04 |
| text-embedding-v3 | ¥0.002/次 | 1 次 | ¥0.002 |
| **总计** | | | **¥0.054/次** |

### 9.2 按月估算（1000 次/月）

- **AI 调用**: ~¥54
- **RxNorm/OpenFDA**: 免费
- **ChromaDB**: 本地存储，免费
- **Redis**: 本地/云实例按需

---

## 10. 安全与合规

### 10.1 数据安全

- 图片上传后保存为临时文件，处理完成后立即删除
- 不向第三方传输用户图片（仅调用阿里云 DashScope）
- 用户作息数据存储在浏览器 `localStorage`，不上传服务器

### 10.2 医疗免责声明

- 所有建议仅供参考，不构成医疗建议
- 检测到处方药时显示明确警告
- 安全评分 <50 时拒绝生成排期，建议咨询医生
- Dashboard 页面展示数据来源引用

### 10.3 输入安全

- 文件类型白名单验证
- 文件大小上限 10MB
- 速率限制防止滥用
- 空文件拒绝

---

## 11. 项目文件结构

```
Smart_Supplement_Scheduler/
├── app/                          # 后端应用
│   ├── __init__.py
│   ├── main.py                   # FastAPI 主应用
│   ├── models.py                 # Pydantic 数据模型
│   ├── vision.py                 # 图像识别服务
│   ├── schedule_generator.py     # 排期生成服务
│   ├── safety_checker.py         # 安全校验（RxNorm + OpenFDA）
│   ├── rag.py                    # RAG 知识库引擎
│   ├── llm_client.py             # LLM 客户端（重试/熔断/降级）
│   ├── tasks.py                  # Celery 异步任务
│   ├── celery_config.py          # Celery 配置
│   ├── knowledge_base_updater.py # 知识库自动更新
│   └── chroma_db/                # ChromaDB 持久化数据
├── UI/                           # 前端应用
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/
│   │   │   ├── App.tsx
│   │   │   ├── routes.ts
│   │   │   ├── api.ts            # API 客户端
│   │   │   ├── pages/
│   │   │   │   ├── SetupPage.tsx
│   │   │   │   ├── ScanPage.tsx
│   │   │   │   ├── ThinkingPage.tsx
│   │   │   │   └── DashboardPage.tsx
│   │   │   └── components/
│   │   │       ├── GlassCard.tsx
│   │   │       └── MeshGradientBackground.tsx
│   │   └── styles/
│   ├── package.json
│   └── vite.config.ts
├── nih_data_processed/           # 处理后 NIH 数据 (JSON)
├── nih_data_markdown/            # Markdown 格式知识库
├── pics/                         # 测试图片
├── scrape_nih_data.py            # NIH 数据抓取脚本
├── clean_nih_data.py             # 数据清洗脚本
├── requirements.txt              # Python 依赖
├── start.sh                      # 启动 FastAPI
├── start_celery.sh               # 启动 Celery Worker
├── update_knowledge_base.sh      # 更新知识库脚本
├── run_all.sh                    # 一键启动所有服务
├── .env.example                  # 环境变量模板
├── ARCHITECTURE.md               # 系统架构文档
└── PRD.md                        # 本文件
```

---

## 12. 里程碑与迭代计划

### Milestone 1: MVP (已完成)

- [x] 图片上传与补剂识别
- [x] 用户作息设置
- [x] 基础排期生成
- [x] 移动端 UI（4 页面）
- [x] 异步任务队列
- [x] NIH 知识库初始化

### Milestone 2: 安全增强 (已完成)

- [x] Layer 1 安全校验（RxNorm + OpenFDA）
- [x] 药物-补剂相互作用检查
- [x] 安全评分系统
- [x] 黑盒警告 / 召回通知展示
- [x] 流式生成（SSE）

### Milestone 3: 知识库管理 (已完成)

- [x] 知识库自动更新
- [x] 版本管理
- [x] 变更日志
- [x] 增量更新

### Milestone 4: 未来规划

- [ ] 用户账户系统（保存历史排期）
- [ ] 每日推送提醒（PWA / 小程序）
- [ ] 扫码识别（条形码/二维码）
- [ ] 多语言支持
- [ ] 社区分享（排期模板）
- [ ] iOS / Android 原生应用

---

## 13. 附录

### 13.1 参考资料

- [RxNorm API Documentation](https://rxnormapi.nlm.nih.gov/)
- [OpenFDA API Documentation](https://open.fda.gov/apis/)
- [NIH ODS Fact Sheets](https://ods.od.nih.gov/factsheets/list-all/)
- [DashScope API Documentation](https://help.aliyun.com/document_detail/611033.html)

### 13.2 术语表

| 术语 | 说明 |
|------|------|
| RAG | Retrieval-Augmented Generation，检索增强生成 |
| RxCUI | RxNorm Concept Unique Identifier，药物唯一标识 |
| FAERS | FDA Adverse Event Reporting System，不良事件报告系统 |
| SPL | Structured Product Label，结构化产品标签 |
| SSE | Server-Sent Events，服务器推送事件 |
| ChromaDB | 开源向量数据库 |
