# API 参考

仅在你需要做 HTTP 集成或调试时使用本文件。默认建议优先使用 `skillsbrain` CLI。

## 服务信息

- 默认地址：`http://127.0.0.1:8765`
- Swagger：`http://127.0.0.1:8765/docs`

## 健康检查

- `GET /health`
- `GET /health/ready`

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

### `GET /api/skill/list`

查询参数：

- `agent_type`
- `enabled_only`
- `offset`
- `limit`

### `GET /api/skill/stats`

返回索引总量与 embedding 模型信息。

### `POST /api/skill/reindex`

触发全量重建索引。

## 订阅源管理

### `GET /api/source/list`

列出订阅源。

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

## 管理接口（生命周期）

### `GET /api/admin/status`

返回服务运行态与运行时元数据（不包含 shutdown token）。

### `POST /api/admin/shutdown`

用于触发服务优雅退出。入参需要 shutdown token（由 CLI 写入运行时元数据文件并用于 `skillsbrain stop`，不建议在外部系统硬编码使用）。

```json
{
  "token": "<shutdown-token>"
}
```
