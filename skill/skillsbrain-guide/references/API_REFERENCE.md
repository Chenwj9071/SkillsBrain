# API 完整参考

## 服务信息

- **地址**: `http://127.0.0.1:8765`
- **Swagger 文档**: `http://127.0.0.1:8765/docs`
- **端口**: 8765（可在 `api/main.py` 修改）

---

## 核心接口

### POST /api/skill/match

**语义检索最匹配技能** — Agent 主调用入口

**请求体**:
```json
{
  "query": "提取PDF中的表格数据",
  "agent_type": "claude_code",
  "session_id": "sess-abc123",
  "top_k": 5
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 自然语言查询，描述任务意图 |
| `agent_type` | string | ❌ | null | `claude_code` 或 `codex`，用于过滤兼容性 |
| `session_id` | string | ❌ | null | 会话ID，用于追踪调用链路 |
| `top_k` | int | ❌ | 5 | 返回数量，范围 1-20 |

**响应体**:
```json
[
  {
    "name": "pdf-table-extract",
    "description": "提取PDF中的表格数据，支持多页PDF批量处理",
    "compatibility": ["claude_code", "codex"],
    "tags": ["pdf", "表格", "数据提取"],
    "version": "1.0.0",
    "author": "local-agent",
    "enabled": true,
    "created_at": "2026-04-19",
    "file_path": "D:\\Project\\SkillsBrain\\skills\\pdf\\SKILL.md",
    "score": 0.7895
  }
]
```

**字段说明**:

| 字段 | 说明 |
|------|------|
| `name` | 技能唯一标识（kebab-case） |
| `description` | 技能描述 |
| `compatibility` | 兼容的 agent 类型 |
| `tags` | 技能标签 |
| `score` | 语义相似度分数，范围 0-1，阈值 0.65 |
| `file_path` | SKILL.md 文件路径 |

---

## 管理接口

### GET /api/skill/list

**列出所有技能**

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `agent_type` | string | null | 过滤兼容的技能 |
| `enabled_only` | bool | true | 只返回已启用的技能 |

**响应**:
```json
{
  "total": 6,
  "skills": [
    {"name": "pdf-table-extract", "description": "...", ...},
    ...
  ]
}
```

---

### GET /api/skill/detail/{name}

**查看单个技能详情**

**路径参数**: `name` — 技能名称

**响应**: 技能完整元数据

---

### POST /api/skill/enable/{name}

**上下线技能**

**查询参数**: `enabled` — `true` 启用 / `false` 禁用

---

### POST /api/skill/reindex

**手动触发全量重建索引**

**响应**:
```json
{
  "indexed": 6,
  "message": "全量重建完成"
}
```

---

### GET /api/skill/stats

**索引统计**

**响应**:
```json
{
  "total": 6,
  "model": "BAAI/bge-small-zh-v1.5"
}
```

---

### GET /health

**健康检查**

**响应**:
```json
{
  "status": "ok"
}
```

---

## 错误处理

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 404 | 技能不存在 |
| 500 | 服务器内部错误 |

---

## 调用示例

### Python (requests)

```python
import requests

response = requests.post(
    "http://127.0.0.1:8765/api/skill/match",
    json={
        "query": "编辑Excel公式",
        "agent_type": "claude_code",
        "session_id": "session-001",
        "top_k": 3
    },
    timeout=10
)

skills = response.json()
for skill in skills:
    print(f"{skill['name']}: {skill['score']}")
```

### cURL

```bash
curl -X POST http://127.0.0.1:8765/api/skill/match \
  -H "Content-Type: application/json" \
  -d '{"query": "提取PDF表格", "top_k": 3}'
```
