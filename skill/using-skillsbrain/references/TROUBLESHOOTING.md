# 安装与排障

## 1. 终端找不到 `skillsbrain` 命令

原因通常是 Python 的 `Scripts` 目录没有加入 PATH。

Windows（仅让当前终端立即生效）：

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts;$env:PATH"
```

如果暂时不想修改 PATH，可直接使用模块入口：

```bash
python -m skillsbrain.cli --help
```

## 2. 重装/升级失败：`WinError 32 ... skillsbrain.exe`

Windows 下如果存在正在运行的 `skillsbrain serve` 常驻进程，系统会锁定 `skillsbrain.exe`，导致重装失败。

建议顺序：

```bash
skillsbrain stop
python -m pip install -e . --force-reinstall --no-deps
```

如果当前终端还不能执行 `skillsbrain`，改用：

```bash
python -m skillsbrain.cli stop
python -m pip install -e . --force-reinstall --no-deps
```

## 3. CLI 报错：无法连接服务

常见报错：

- `Error: Cannot connect to SkillsBrain server.`

处理方式：

```bash
skillsbrain status
skillsbrain serve
```

如果端口冲突，可换端口：

```bash
skillsbrain serve --port 9000
```

## 4. 新技能没有被检索到

按顺序检查：

1. 技能目录结构是否正确：每个技能目录中必须有 `SKILL.md`。
2. 是否启动时指向了正确的技能目录：`skillsbrain serve --skills <dir>`。
3. 是否需要重建索引：`skillsbrain reindex`。

## 5. 订阅源不生效

检查点：

1. `subscribe` 的目录可访问，且目录内包含符合规范的技能子目录。
2. 用 `skillsbrain sources` 确认订阅源存在。
3. 用 `skillsbrain list` 确认技能数量变化。
