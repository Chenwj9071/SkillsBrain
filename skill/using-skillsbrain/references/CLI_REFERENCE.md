# CLI 参考

默认优先使用 `skillsbrain` CLI，而不是直接调用 HTTP API（除非你在做系统集成或调试）。

## 服务管理

```bash
# 后台常驻启动（命令会阻塞到服务 ready）
skillsbrain serve [--host 127.0.0.1] [--port 8765] [--skills <dir>] [--data-dir <dir>] [--startup-timeout <seconds>]

# 查看服务状态（会读取 data_dir 下的运行时元数据，并探测服务）
skillsbrain status [--host 127.0.0.1] [--port 8765] [--data-dir <dir>]

# 关闭服务（优雅关闭为主，必要时回退按 pid 终止）
skillsbrain stop [--host 127.0.0.1] [--port 8765] [--data-dir <dir>] [--timeout <seconds>]
```

常用示例：

```bash
skillsbrain serve
skillsbrain serve --port 9000 --skills ./skill
skillsbrain serve --data-dir D:/data/project-a

skillsbrain status
skillsbrain stop
```

## 查询与列表

```bash
# 语义匹配技能
skillsbrain match "<查询词>" [--agent codex|claude_code] [--session <id>] [--top-k 5] [--host <host>] [--port <port>]

# 列出技能（可按 agent 过滤）
skillsbrain list [--agent <agent>] [--host <host>] [--port <port>]

# 查看索引统计
skillsbrain stats [--host <host>] [--port <port>]
```

## 索引维护

```bash
# 手动触发全量重建索引
skillsbrain reindex [--host <host>] [--port <port>]
```

## 订阅外部技能源

```bash
# 订阅一个外部 skills 目录（会扫描并纳入索引）
skillsbrain subscribe <path> [--name <source-name>] [--host <host>] [--port <port>]

# 列出当前订阅源
skillsbrain sources [--host <host>] [--port <port>]

# 取消订阅（入参可以是订阅名或目录路径）
skillsbrain unsubscribe <name-or-root> [--host <host>] [--port <port>]
```

## PATH 未配置时的兜底入口

如果终端找不到 `skillsbrain` 命令，可以使用模块入口：

```bash
python -m skillsbrain.cli --help
python -m skillsbrain.cli serve
python -m skillsbrain.cli status
python -m skillsbrain.cli stop
```
