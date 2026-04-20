# SkillsBrain 1.0.0 发布说明

发布日期：2026-04-20

## 版本概述

SkillsBrain 1.0.0 是项目的初始稳定版本，提供本地技能路由、语义检索、索引管理、文件监听和外部技能源订阅能力，适合本地可信环境中的 AI Agent 使用。

---

## 核心能力

### 1. 本地技能路由
- 扫描本地 `skills/` 目录中的标准技能
- 解析 `SKILL.md` 中的 frontmatter 元数据
- 使用向量检索匹配最相关的技能

### 2. 语义检索
- 基于 **ChromaDB** 构建本地向量索引
- 使用 **bge-small-zh-v1.5** 作为默认嵌入模型
- 支持按 `agent_type` 过滤技能
- 支持 `enabled` 状态读取

### 3. 本地服务与 CLI
- 提供 FastAPI 服务
- 提供 `skillsbrain` 命令行工具
- 支持 `match`、`list`、`stats`、`reindex` 等常用命令

### 4. 文件监听与增量同步
- 监听 `skills/` 目录变化
- 自动同步新增、修改、删除的技能文件
- 支持订阅目录的实时监听

### 5. 外部技能源订阅
- 支持订阅一个外部 skills 目录
- 不修改源目录内容
- 订阅后自动纳入索引并启动 watcher
- 支持取消订阅并清理索引

---

## 主要命令

### 启动服务
```bash
skillsbrain serve
```

### 查询技能
```bash
skillsbrain match "提取PDF中的表格"
```

### 列出技能
```bash
skillsbrain list
```

### 查看统计
```bash
skillsbrain stats
```

### 重建索引
```bash
skillsbrain reindex
```

### 订阅外部技能源
```bash
skillsbrain subscribe D:/shared-skills --name shared
skillsbrain sources
skillsbrain unsubscribe shared
```

---

## API 概览

### 技能检索
- `POST /api/skill/match`

### 技能管理
- `GET /api/skill/list`
- `GET /api/skill/detail/{name}`
- `POST /api/skill/reindex`
- `GET /api/skill/stats`

### 订阅源管理
- `GET /api/source/list`
- `POST /api/source/subscribe`
- `POST /api/source/unsubscribe`

### 健康检查
- `GET /health`
- `GET /health/ready`

---

## 数据与索引规则

### skill_id
- 由 `skills/` 根目录下的相对路径推导
- 标准结构 `skills/<name>/SKILL.md` 的 `skill_id` 为 `<name>`
- 订阅源使用 `source_name:skill_id` 作为索引主键

### enabled
- 只读取技能文件自身的 `enabled` 属性
- 工具不提供修改 enabled 的接口

---

## 安装方式

### 开发模式
```bash
pip install -e .
```

### 打包后安装
```bash
pip install .
```

### 运行 CLI
安装后提供全局命令：
```bash
skillsbrain
```

---

## 兼容环境
- Python 3.10+
- Windows / Linux / macOS
- 本地可信环境

---

## 已知边界

- 这是一个**本地运行**的技能路由工具，不面向公网开放
- 默认监听 `127.0.0.1`
- 默认数据根目录：用户目录下的 `~/.skillsbrain/`
- 支持通过 `skillsbrain serve --data-dir` 指定整套数据根目录
- 技能源内容由本机 Agent / CLI 消费
- 订阅源和索引状态存储在本地 `~/.skillsbrain/`

---

## 推荐使用方式

1. 准备本地 `skills/` 目录
2. 启动服务：`skillsbrain serve`
3. 通过 `skillsbrain match` 查找技能
4. 如有共享技能源，可使用 `skillsbrain subscribe` 接入
5. 取消订阅时使用 `skillsbrain unsubscribe`

---

## 版本定位

`1.0.0` 作为初始版本，目标是提供一个可安装、可运行、可检索、可订阅外部技能源的本地技能路由基础设施。
