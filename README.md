# SkillsBrain - 本地技能路由引擎

基于 **ChromaDB + bge-small-zh-v1.5** 的本地语义检索引擎，专为 AI Agent 技能路由设计。

---

## 安装与卸载

### 安装（开发模式）

```bash
# 克隆仓库
git clone https://github.com/Chenwj9071/SkillsBrain.git
cd SkillsBrain

# 安装（可编辑模式，修改代码后无需重装）
pip install -e .
```

### 安装（离线环境）

```bash
# 先在有网环境导出依赖
pip freeze > requirements.txt

# 拷贝到目标机器后离线安装
pip install -r requirements.txt
pip install -e .
```

### 卸载

```bash
# 卸载包
pip uninstall skillsbrain -y

# 删除数据（可选）
rm -rf .index/
rm -rf logs/
```

---

## CLI 使用

安装后自动提供全局命令 `skillsbrain`：

### 启动服务

```bash
# 默认端口 8765
skillsbrain serve

# 指定端口和技能目录
skillsbrain serve --port 9000 --skills ./my-skills
```

### 查询技能

```bash
# 基本查询
skillsbrain match "提取PDF中的表格"

# 指定返回数量和会话ID
skillsbrain match "编辑Excel公式" --top-k 3 --session sess-001

# 指定 Agent 类型
skillsbrain match "生成Word报告" --agent claude_code
```

### 管理技能

```bash
# 列出所有技能
skillsbrain list

# 过滤特定 Agent 的技能
skillsbrain list --agent codex

# 查看统计
skillsbrain stats

# 重建索引
skillsbrain reindex
```

### 订阅外部 skills 源

```bash
# 订阅一个目录并自动纳入索引
skillsbrain subscribe D:/shared-skills --name shared

# 查看所有订阅源
skillsbrain sources

# 取消订阅
skillsbrain unsubscribe shared
```

---

## API 接口

服务启动后，访问 `http://127.0.0.1:8765/docs` 查看 Swagger 文档。

### 核心接口

```bash
POST /api/skill/match
{
  "query": "提取PDF中的表格",
  "agent_type": "claude_code",
  "session_id": "session-001",
  "top_k": 5
}
```

### 技能列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skill/list` | 列出技能，支持 `agent_type`、`offset`、`limit` |
| GET | `/api/skill/detail/{name}` | 查看单个技能详情 |
| POST | `/api/skill/reindex` | 重建索引 |
| GET | `/api/skill/stats` | 统计信息 |
| GET | `/health` | 健康检查 |
| GET | `/health/ready` | 就绪检查 |

### 订阅源管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/source/list` | 查看已订阅源 |
| POST | `/api/source/subscribe` | 订阅一个新目录 |
| POST | `/api/source/unsubscribe` | 取消订阅目录 |

---

## 技术架构

| 层级 | 组件 | 作用 |
|------|------|------|
| 技能接入层 | `core/parser.py` | 解析 SKILL.md 元数据 |
| 索引层 | `core/indexer.py` + ChromaDB | 向量存储 + 元数据持久化 |
| 检索引擎 | `core/engine.py` | 三层检索（过滤→召回→阈值筛选） |
| API 层 | `api/main.py` + FastAPI | REST 接口 / 管理入口 |
| 文件监听 | `core/watcher.py` + watchdog | 增量同步，防抖 1s |

## 三层检索流程

1. **快速过滤层** — 按 `enabled`、`compatibility` 过滤候选集
2. **宽语义召回层** — bge-small-zh-v1.5 向量召回 Top12
3. **精筛层** — 阈值 ≥ 0.65 过滤，输出 Top5

---

## 目录结构

```
SkillsBrain/
├── pyproject.toml
├── src/skillsbrain/
│   ├── cli.py
│   ├── config.py
│   ├── core/
│   ├── api/
│   └── utils/
├── skills/
├── .index/
├── logs/
└── docs/
```

---

## 技能格式

`skills/<skill-name>/SKILL.md`

示例：

```yaml
---
name: pdf-table-extract
description: 提取PDF中的表格数据，支持多页PDF批量处理
compatibility: ["claude_code", "codex"]
tags: ["pdf", "表格", "数据提取"]
version: 1.0.0
author: local-agent
enabled: true
created_at: 2026-04-19
---

# 技能正文
```

---

## 订阅源设计

SkillsBrain 支持订阅外部 skills 目录。

### 特点
- 不修改订阅目录中的源文件
- 订阅后自动扫描并纳入索引
- 订阅后自动启动 watcher
- 可随时取消订阅

### 推荐命令
```bash
skillsbrain subscribe D:/shared-skills --name shared
skillsbrain sources
skillsbrain unsubscribe shared
```

---

## 说明

当前服务定位为本地可信环境使用：
- 默认监听 `127.0.0.1`
- skills 文件由本机 Agent / CLI 消费
- 索引与订阅状态保存在本地 `.index/`
