# SkillsBrain - 本地技能路由引擎

基于 **ChromaDB + bge-small-zh-v1.5** 的本地语义检索引擎，专为 AI Agent 技能路由设计。

---

## 快速安装

```bash
# 克隆仓库
git clone https://github.com/Chenwj9071/SkillsBrain.git
cd SkillsBrain

# 安装
pip install -e .
```

---

## CLI 使用

安装后自动提供全局命令 `skillsbrain`:

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

### 管理命令

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

### 管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skill/list` | 列出所有技能 |
| GET | `/api/skill/detail/{name}` | 查看单个技能 |
| POST | `/api/skill/enable/{name}` | 上下线技能 |
| POST | `/api/skill/reindex` | 重建索引 |
| GET | `/api/skill/stats` | 统计信息 |
| GET | `/health` | 健康检查 |

---

## 技术架构

| 层级 | 组件 | 作用 |
|------|------|------|
| 技能接入层 | `core/parser.py` | 解析 SKILL.md 元数据 |
| 索引层 | `core/indexer.py` + ChromaDB | 向量存储 + 元数据持久化 |
| 检索引擎 | `core/engine.py` | 三层检索（过滤→召回→精排）|
| API 层 | `api/main.py` + FastAPI | REST 接口 / 管理后台入口 |
| 文件监听 | `core/watcher.py` + watchdog | 增量同步，防抖 1s |

## 三层检索流程

1. **快速过滤层** — 按 `compatibility`、`enabled` 过滤候选集
2. **宽语义召回层** — bge-small-zh-v1.5 向量召回 Top12（余弦相似度）
3. **精排层** — 阈值 ≥ 0.75 过滤，输出 Top5

## 目录结构

```
D:\Project\SkillsBrain\
├── config.py              # 全局配置（pydantic-settings）
├── core/
│   ├── parser.py          # SKILL.md 元数据解析
│   ├── indexer.py         # Chroma 向量索引构建
│   ├── engine.py          # 三层检索引擎
│   └── watcher.py         # 文件监听（增量同步）
├── api/
│   └── main.py            # FastAPI 服务入口
├── skills/                # 技能存放目录（可扩展子目录）
│   ├── pdf/SKILL.md
│   ├── xlsx/SKILL.md
│   └── docx/SKILL.md
├── .index/                # Chroma 向量索引（自动生成，勿删）
└── requirements.txt
```

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 放入技能
#    在 skills/ 目录下创建技能文件夹，每个文件夹放一个 SKILL.md

# 3. 启动服务
python api/main.py
# 服务地址: http://127.0.0.1:8765
# API 文档: http://127.0.0.1:8765/docs
```

## API 接口

### Agent 主调用
```bash
POST /api/skill/match
{
  "query": "帮我把PDF里的表格提取出来",
  "agent_type": "claude_code",
  "top_k": 5
}
```

### 管理接口
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skill/list` | 列出所有技能 |
| GET | `/api/skill/detail/{name}` | 查看单个技能 |
| POST | `/api/skill/enable/{name}` | 上下线技能 |
| POST | `/api/skill/reindex` | 重建全量索引 |
| GET | `/api/skill/stats` | 索引统计 |
| GET | `/health` | 健康检查 |

## 技能 SKILL.md 格式

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

# 技能标题

技能正文描述（不会被索引，仅供参考）
```

## 扩展技能目录

只需在 `skills/` 下新建子目录，放入符合规范的 `SKILL.md`，监听器会自动检测并更新索引，无需重启服务。
