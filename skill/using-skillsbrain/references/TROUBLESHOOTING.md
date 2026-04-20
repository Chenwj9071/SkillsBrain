# 安装与排障

## 1. `skillsbrain` 命令不存在

说明当前机器尚未安装 CLI，或环境变量未生效。优先提示安装：

```bash
git clone https://github.com/Chenwj9071/SkillsBrain.git
cd SkillsBrain
pip install -e .
```

项目地址：

`https://github.com/Chenwj9071/SkillsBrain`

## 2. CLI 已安装，但无法连接服务

常见报错：

- `Error: Cannot connect to SkillsBrain server.`

处理方式：

```bash
skillsbrain serve
```

如果技能目录在当前仓库内而不是默认目录，改用：

```bash
skillsbrain serve --skills ./skill
```

## 3. 缺少 Python 依赖

如果执行 CLI 时出现依赖导入错误，按安装流程重新执行：

```bash
git clone https://github.com/Chenwj9071/SkillsBrain.git
cd SkillsBrain
pip install -e .
```

## 4. 新技能没有被检索到

按顺序检查：

1. `SKILL.md` frontmatter 是否有效
2. 服务启动时是否指向正确技能目录
3. 是否需要重建索引

对应命令：

```bash
skillsbrain list
skillsbrain reindex
```

## 5. 当前仓库技能目录与默认目录不一致

SkillsBrain 默认扫描用户目录下的 `~/.skillsbrain/skills`。如果技能在仓库内，例如当前项目的 `./skill`，需要显式指定：

```bash
skillsbrain serve --skills ./skill
```
