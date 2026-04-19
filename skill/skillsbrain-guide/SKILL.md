---
name: skillsbrain-guide
description: SkillsBrain 本地技能路由引擎使用指南。当 Agent 需要发现和使用技能、查询是否有相关技能可用、或在执行任务前主动检查技能库时应使用此 Skill。触发场景：(1) 接到用户任务需要确定是否有现成技能可用 (2) 处理文件操作（PDF/Excel/Word/图片/音视频）(3) 批量数据处理或格式转换 (4) 不确定如何完成任务时先查技能 (5) 需要最大化利用已有技能能力时。
---

# SkillsBrain 使用指南

SkillsBrain 是本地语义技能路由引擎，帮助 Agent 快速发现和调用相关技能。

## 快速开始

**服务地址**: `http://127.0.0.1:8765`

**核心 API**: `POST /api/skill/match`

```bash
curl -X POST http://127.0.0.1:8765/api/skill/match \
  -H "Content-Type: application/json" \
  -d '{
    "query": "提取PDF中的表格",
    "agent_type": "claude_code",
    "session_id": "当前会话ID",
    "top_k": 5
  }'
```

## 核心使用原则

### 1. 宁可多查，不要漏查

查询成本低（~20ms），但漏掉技能会导致重复造轮子。**不确定有没有技能时，先查一次。**

### 2. 主动触发查询的时机

| 时机 | 说明 |
|------|------|
| 接到用户任务时 | 先查技能，再执行 |
| 遇到文件操作时 | PDF/Excel/Word/图片/音视频 → 必查 |
| 任务分解后 | 每个子任务查一次 |
| 不确定怎么做时 | 查技能看有没有现成方案 |

### 3. 查询关键词策略

**最有效：任务动词 + 文件类型**

```python
# 好的查询
"提取PDF表格数据"
"编辑Excel单元格公式"
"创建Word文档模板"
"裁剪图片尺寸"

# 避免：模糊描述
"帮我处理一下"  # 太模糊，可能命中多个不相关技能
```

### 4. 返回结果处理

返回 `top_k` 个候选，按 `score` 排序。**如果第一个不匹配，看第二个、第三个。**

```json
[
  {"name": "pdf-table-extract", "score": 0.82},
  {"name": "xlsx-cell-edit", "score": 0.71}  // 也相关，别漏
]
```

## 标准调用流程

```
用户任务 → 查询技能 → 命中？
                         ↓是
                    读 SKILL.md → 执行技能
                         ↓否
                    用通用方案执行
```

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `query` | ✅ | 自然语言查询，描述任务意图 |
| `agent_type` | ❌ | `claude_code` 或 `codex`，用于过滤兼容性 |
| `session_id` | ❌ | 会话ID，用于追踪调用链路 |
| `top_k` | ❌ | 返回数量，默认 5，范围 1-20 |

## 详细文档

- **API 完整参考**: 见 [references/API_REFERENCE.md](references/API_REFERENCE.md)
- **查询模式与最佳实践**: 见 [references/QUERY_PATTERNS.md](references/QUERY_PATTERNS.md)

## 常见错误

| 问题 | 解决方案 |
|------|----------|
| 服务未启动 | 先运行 `python api/main.py` |
| 返回空数组 | 没有匹配技能，用通用方案 |
| score 太低 | 阈值 0.65，低于此不返回；可调整关键词重试 |

## 日志追踪

所有调用记录在 `logs/calls/YYYY-MM-DD.jsonl`，包含：

- `source`: 调用来源
- `session_id`: 会话ID
- `query`: 查询内容
- `hits`: 命中技能列表
- `latency_ms`: 延迟
