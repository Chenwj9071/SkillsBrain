---
name: using-skillsbrain
description: SkillsBrain 本地技能调度入口。优先通过 `skillsbrain` CLI 启动/查询/维护本地技能索引；当不确定该用哪个技能或需要管理订阅源时使用。
---

# using-skillsbrain

把本技能当作“每次会话开始时的轻量入口”，优先用 CLI 完成：启动服务、查询匹配、列出技能、订阅外部技能源、重建索引、查看状态与关闭服务。

## 会话起步（推荐顺序）

1. 确认 CLI 可用：执行 `skillsbrain --help`（或使用 `python -m skillsbrain.cli --help` 兜底）。
2. 确认服务是否已启动：`skillsbrain status`。
3. 服务未运行则启动：`skillsbrain serve`。
4. 查询技能用 `skillsbrain match`，列出技能用 `skillsbrain list`，统计用 `skillsbrain stats`。
5. 技能变更或疑似索引异常时：`skillsbrain reindex`。
6. 需要接入共享技能库：`skillsbrain subscribe` / `skillsbrain sources` / `skillsbrain unsubscribe`。
7. 结束会话或升级前关闭服务：`skillsbrain stop`。

## 关键行为说明（最新）

- `skillsbrain serve` 默认“后台常驻启动服务”，但命令本身会阻塞到服务 ready 后才返回，避免后续立刻执行 `match/list/stats` 失败。
- 同一个 `data_dir` 下会维护运行时元数据文件，`serve` 会在启动前检查状态，避免重复启动冲突。
- `skillsbrain stop` 会优先优雅关闭；若优雅关闭不可用，会回退到按 pid 终止（以确保能停掉）。

## 常用命令

```bash
# 启动/状态/关闭
skillsbrain serve
skillsbrain status
skillsbrain stop

# 查询/列表/统计
skillsbrain match "<任务描述>" --agent codex
skillsbrain match "<任务描述>" --agent claude_code --top-k 3 --session <session-id>
skillsbrain list --agent codex
skillsbrain stats

# 索引维护
skillsbrain reindex

# 订阅外部技能源
skillsbrain subscribe D:/shared-skills --name shared
skillsbrain sources
skillsbrain unsubscribe shared
```

## 安装与升级（Windows 重点）

- 如果终端提示找不到 `skillsbrain`，通常是 Python 的 `Scripts` 目录未加入 PATH。
- 不想改 PATH 也可以直接使用模块入口：`python -m skillsbrain.cli <command>`。
- Windows 下升级/重装前建议先执行一次 `skillsbrain stop`，否则 `pip install -e . --force-reinstall` 可能因为 `skillsbrain.exe` 被占用而失败。

## 进一步阅读

- CLI 参数与示例：`references/CLI_REFERENCE.md`
- 查询词设计：`references/QUERY_PATTERNS.md`
- HTTP 接口（仅在需要集成时）：`references/API_REFERENCE.md`
- 安装与排障：`references/TROUBLESHOOTING.md`
