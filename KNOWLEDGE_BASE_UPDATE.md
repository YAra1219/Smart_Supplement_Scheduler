# 知识库更新管理指南

## 概述

本系统支持定期从 NIH ODS (美国国立卫生研究院膳食补充剂办公室) 自动更新知识库，具备：
- **版本管理** - 每次更新保存完整快照
- **增量更新** - 只更新有变化的部分
- **变更日志** - 详细记录每次更新内容

## 快速开始

### 1. 手动检查更新

```bash
python -m app.knowledge_base_updater --check
```

输出示例：
```
============================================================
检查知识库更新
============================================================
上次更新：2026-03-01
正在抓取 NIH 最新数据...
找到 50 个补剂页面
  [1/50] 正在抓取：Vitamin A
  ...

比较结果:
  新增：2 个
  更新：5 个
  删除：0 个
  未变：43 个

需要更新：True
```

### 2. 执行更新

```bash
# 正常更新（检查是否到更新时间）
python -m app.knowledge_base_updater --update

# 强制更新（忽略时间检查）
python -m app.knowledge_base_updater --update --force
```

### 3. 查看状态

```bash
python -m app.knowledge_base_updater --status
```

输出示例：
```
============================================================
知识库状态
============================================================
当前版本：v20260331
最后更新：2026-03-31T10:30:00
下次检查：2026-04-30T10:30:00
补剂数量：50
更新频率：每 30 天
版本数量：3
```

### 4. 查看更新历史

```bash
python -m app.knowledge_base_updater --history
```

输出示例：
```
============================================================
更新历史
============================================================

[v20260331] 2026-03-31
  操作：updated
  补剂：Vitamin D
  变更：intake: 150 词 → 162 词

[v20260331] 2026-03-31
  操作：added
  补剂：Omega-3 Fatty Acids
  ...
```

---

## API 端点

### 获取知识库状态

```bash
GET /api/knowledge-base/status
```

响应：
```json
{
  "current_version": "v20260331",
  "last_updated": "2026-03-31T10:30:00",
  "next_check": "2026-04-30T10:30:00",
  "total_supplements": 50,
  "update_frequency_days": 30,
  "version_count": 3
}
```

### 检查是否有更新

```bash
POST /api/knowledge-base/check
```

### 执行更新（异步）

```bash
POST /api/knowledge-base/update
# 可选参数：?force=true 强制更新
```

响应：
```json
{
  "task_id": "abc123...",
  "status": "submitted",
  "message": "知识库更新任务已提交，预计耗时 2-5 分钟"
}
```

### 查看更新历史

```bash
GET /api/knowledge-base/history?limit=10
```

---

## 定时任务配置

### Cron 配置（推荐）

每月 1 日凌晨 3 点自动检查更新：

```bash
# 编辑 crontab
crontab -e

# 添加以下行
0 3 1 * * /path/to/Smart_Med-Supplement_Scheduler/update_knowledge_base.sh
```

### systemd Timer 配置

创建定时器 `/etc/systemd/system/knowledge-base-update.timer`：

```ini
[Unit]
Description=Monthly Knowledge Base Update

[Timer]
OnCalendar=*-*-01 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

创建服务 `/etc/systemd/system/knowledge-base-update.service`：

```ini
[Unit]
Description=Knowledge Base Update Service

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/Smart_Med-Supplement_Scheduler
ExecStart=/usr/bin/python -m app.knowledge_base_updater --update
```

启用定时器：
```bash
sudo systemctl enable knowledge-base-update.timer
sudo systemctl start knowledge-base-update.timer
```

---

## 目录结构

```
knowledge_base/
├── metadata.json          # 元数据
├── changelog.json         # 变更日志
├── raw/                   # 原始抓取数据
├── processed/             # 处理后数据（RAG 使用）
└── versions/              # 版本快照
    ├── v20260101/
    │   ├── Vitamin_A.json
    │   ├── Vitamin_D.json
    │   └── ...
    ├── v20260201/
    └── v20260331/
```

### metadata.json 格式

```json
{
  "current_version": "v20260331",
  "last_updated": "2026-03-31T10:30:00",
  "total_supplements": 50,
  "next_check": "2026-04-30T10:30:00",
  "update_frequency_days": 30
}
```

### changelog.json 格式

```json
[
  {
    "version": "v20260331",
    "timestamp": "2026-03-31T10:30:00",
    "action": "updated",
    "supplement_name": "Vitamin D",
    "details": {
      "name_en": "Vitamin_D",
      "url": "https://ods.od.nih.gov/...",
      "diff": "intake: 150 词 → 162 词"
    },
    "diff_summary": "intake: 150 词 → 162 词"
  }
]
```

---

## 变更检测机制

系统使用 **内容哈希（MD5）** 检测变化：

1. **抓取新数据** - 从 NIH ODS 抓取最新内容
2. **计算哈希** - 对每个补剂的 `intake + interactions + risks` 计算 MD5
3. **对比旧记录** - 比较新旧哈希值
4. **判定变更**：
   - 哈希相同 → `unchanged`
   - 哈希不同 → `updated`
   - 新增补剂 → `added`
   - 缺失补剂 → `removed`

### 差异摘要生成

对于更新的记录，生成差异摘要：
- 比较各章节的单词数量变化
- 输出格式：`intake: 150 词 → 162 词; risks: 80 词 → 85 词`

---

## 故障排查

### 问题：抓取速度慢

**原因**: NIH ODS 服务器响应慢或网络延迟

**解决方案**:
- 增加抓取延迟：修改 `scrape_all(delay=0.5)` 参数
- 使用代理服务器
- 离线缓存：首次全量抓取后，本地保存副本

### 问题：更新失败

**检查**:
1. Redis 是否运行：`redis-cli ping`
2. Celery Worker 是否运行：`celery -A app.celery_config worker`
3. 网络连接：`curl https://ods.od.nih.gov/factsheets/list-all/`

### 问题：版本冲突

**场景**: 多个进程同时更新

**解决方案**:
- 使用文件锁
- 通过 Celery 队列串行执行更新任务

---

## 最佳实践

1. **定期备份**: 每月复制 `knowledge_base/` 目录到安全位置
2. **监控更新**: 配置告警，更新失败时通知
3. **回滚测试**: 定期测试版本回滚功能
4. **日志审计**: 定期检查 `changelog.json` 确保更新正常

---

## 数据来源说明

所有数据来自 **NIH ODS (Office of Dietary Supplements)**：
- 官网：https://ods.od.nih.gov/
- 事实清单：https://ods.od.nih.gov/factsheets/list-all/
- 数据性质：公有领域，免费使用
- 更新频率：NIH 不定期更新，建议每月检查

**引用格式**:
```
National Institutes of Health, Office of Dietary Supplements.
Dietary Supplement Fact Sheets.
https://ods.od.nih.gov/factsheets/list-all/
```


