# API 参考

只有在明确需要 HTTP 集成时才使用本文件。默认仍应优先 `skillsbrain` CLI。

## 服务信息

- 默认地址：`http://127.0.0.1:8765`
- Swagger：`http://127.0.0.1:8765/docs`

## 技能检索

### `POST /api/skill/match`

```json
{
  "query": "提取 PDF 表格",
  "agent_type": "codex",
  "session_id": "sess-001",
  "top_k": 5
}
```

返回字段包含：

- `skill_id`
- `name`
- `description`
- `compatibility`
- `tags`
- `file_path`
- `relative_path`
- `source_name`
- `source_root`
- `score`

## 技能列表

### `GET /api/skill/list`

查询参数：

- `agent_type`
- `enabled_only`
- `offset`
- `limit`

示例：

```bash
curl "http://127.0.0.1:8765/api/skill/list?agent_type=codex&offset=0&limit=50"
```

### `GET /api/skill/detail/{name}`

按技能名读取单个技能详情。

## 索引与统计

### `POST /api/skill/reindex`

手动触发全量重建索引。

### `GET /api/skill/stats`

读取索引总量与当前 embedding 模型。

## 订阅源

### `GET /api/source/list`

列出所有订阅源。

### `POST /api/source/subscribe`

```json
{
  "path": "D:/shared-skills",
  "name": "shared"
}
```

### `POST /api/source/unsubscribe`

```json
{
  "name_or_root": "shared"
}
```

## 健康检查

- `GET /health`
- `GET /health/ready`
