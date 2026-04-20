---
name: using-skillsbrain
description: SkillsBrain 本地技能调度入口。每次会话开始时都必须先加载本技能，用于优先通过 `skillsbrain` CLI 发现、匹配、列出和维护本地技能；当任务开始前需要确认是否已有可复用技能、或不确定该用什么技能时使用。
---

# using-skillsbrain

将本技能作为每次会话开始时的轻量入口。默认优先 CLI；只有明确需要 HTTP 集成、复杂查询策略或排障时，再读取 `references/`。

## 会话起步

1. 先确认 `skillsbrain` CLI 是否可用。
2. 需要查技能时，优先执行 `skillsbrain match`。
3. 需要看当前技能库时，执行 `skillsbrain list`。
4. CLI 已安装但服务未启动时，提示先运行 `skillsbrain serve`。
5. CLI 或依赖缺失时，直接提示安装，不假设本地环境已就绪。

## 常用命令

```bash
skillsbrain match "<任务描述>" --agent codex
skillsbrain match "<任务描述>" --agent claude_code --top-k 3 --session <session-id>
skillsbrain list --agent codex
skillsbrain stats
skillsbrain serve
skillsbrain reindex
```

查询词优先写“动作 + 对象或文件类型”，例如：`提取 PDF 表格`、`生成 Word 报告`、`批量处理 Excel 数据`。

## 缺失时的提示模板

出现以下任一情况时，直接提示安装：

- `skillsbrain` 命令不存在
- 执行 CLI 时提示缺少 Python 依赖
- 当前机器尚未安装 SkillsBrain

可直接使用这段提示：

```text
未检测到可用的 SkillsBrain CLI 或运行依赖。请先安装：
git clone https://github.com/Chenwj9071/SkillsBrain.git
cd SkillsBrain
pip install -e .

安装后可先运行 `skillsbrain serve`，再用 `skillsbrain match "<任务描述>"` 查询技能。
```

## 进一步读取

- 需要完整 CLI 参数时，读取 `references/CLI_REFERENCE.md`
- 需要查询词设计时，读取 `references/QUERY_PATTERNS.md`
- 需要 HTTP 接口时，读取 `references/API_REFERENCE.md`
- 需要安装或排障时，读取 `references/TROUBLESHOOTING.md`
