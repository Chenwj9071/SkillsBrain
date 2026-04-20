# CLI 参考

默认优先使用 `skillsbrain` CLI，而不是直接调用 HTTP API。

## 启动服务

```bash
skillsbrain serve
skillsbrain serve --host 127.0.0.1 --port 8765
skillsbrain serve --skills ./skill
```

- `--skills` 用于指定技能目录
- 如果当前项目把技能放在仓库内，常见用法是 `--skills ./skill`

## 查询技能

```bash
skillsbrain match "提取 PDF 表格"
skillsbrain match "生成 Word 报告" --agent codex
skillsbrain match "编辑 Excel 公式" --agent claude_code --top-k 3 --session sess-001
```

- `--agent` 可选值：`codex`、`claude_code`
- `--top-k` 默认 `5`
- `--session` 用于记录会话链路

## 列出与统计

```bash
skillsbrain list
skillsbrain list --agent codex
skillsbrain stats
```

## 索引维护

```bash
skillsbrain reindex
```

适用场景：

- 批量修改了多个技能文件
- 新增技能后未被识别
- 索引状态异常

## 订阅外部技能源

```bash
skillsbrain subscribe D:/shared-skills --name shared
skillsbrain sources
skillsbrain unsubscribe shared
```

适用场景：

- 技能目录不在当前仓库
- 需要接入共享技能仓库
- 需要查看或移除已订阅源
