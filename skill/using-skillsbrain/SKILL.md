---
name: using-skillsbrain
description: SkillsBrain是本地技能调度中心，每次会话开始时必须加载。在执行任何任务（开发/测试/运行/排障/脚本/工具安装）前，必须先确认服务和可用技能，再决定后续操作。用户出现“需要使用技能/能力”等意图时优先触发；也用于订阅源管理与索引维护。
---

# using-skillsbrain

把本技能当作“每次任务开始前的默认前置检查”。只要你准备执行任何操作（跑命令、改代码、跑测试、安装依赖、排障、生成文件、更新文档），都先做一次 SkillsBrain 的可用性确认与技能检索，避免盲做和重复劳动。

## 触发条件

当出现以下任一情况时，应优先调用本技能作为第一步：

1. 用户提出“做一件事”，但未明确指定要用哪个 skill/工具/脚本。
2. 需要在本机执行任何命令或脚本（`git`、编译、测试等）。
3. 需要查找“已有能力/已有工具/现成命令/支持哪些操作/怎么做最好”。
4. 需要管理技能来源：订阅/取消订阅/查看 sources/重建索引。
5. 服务可能没起、刚重启、刚升级、刚切换环境，需要确认服务状态。

如果你不确定是否要用本技能：默认先用本技能。

## 会话起步（推荐顺序）

1. 确认 CLI 可用：执行 `skillsbrain --help`（或使用 `python -m skillsbrain.cli --help` 兜底）。
2. 确认服务是否已启动：`skillsbrain status`。
3. 服务未运行则启动：`skillsbrain serve`。
4. 先检索再行动：查询技能用 `skillsbrain match`，列出技能用 `skillsbrain list`，统计用 `skillsbrain stats`。
5. 技能变更或疑似索引异常时：`skillsbrain reindex`。
6. 需要接入共享技能库：`skillsbrain subscribe` / `skillsbrain sources` / `skillsbrain unsubscribe`。
7. 结束会话或升级前关闭服务：`skillsbrain stop`。

## 最小前置流程（建议固定执行）

在每个任务开始时，优先执行下面这组最小动作（顺序固定）：

```bash
skillsbrain status || skillsbrain serve
skillsbrain match "<本次任务的一句话描述>" --agent codex --top-k 5
```

说明：

- `serve` 会阻塞到服务 ready 才返回，所以 `status || serve` 之后立刻 `match/list/stats` 是安全的。
- `match` 的输出就是你下一步应该调用的 skill/命令入口，不要跳过。

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
