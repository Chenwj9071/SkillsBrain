# SkillsBrain 安装与首次使用指南

本文档面向首次使用 SkillsBrain 的用户，说明如何安装、启动、查询技能以及订阅外部技能源。

---

## 1. 安装

### 开发模式安装

```bash
git clone https://github.com/Chenwj9071/SkillsBrain.git
cd SkillsBrain
pip install -e .
```

### 打包安装

如果已经构建为安装包，可以直接：

```bash
pip install .
```

---

## 2. 安装后可用命令

安装完成后会获得全局命令：

```bash
skillsbrain
```

可用子命令包括：
- `serve`
- `match`
- `list`
- `stats`
- `reindex`
- `subscribe`
- `sources`
- `unsubscribe`

---

## 3. 启动服务

```bash
skillsbrain serve
```

默认会启动在：
- `127.0.0.1:8765`
- 默认数据目录：用户目录下的 `~/.skillsbrain/`

如果需要指定技能目录：

```bash
skillsbrain serve --skills ./skills
skillsbrain serve --data-dir D:/data/project-a
```

说明：
- `--skills` 只影响技能扫描目录
- `--data-dir` 可指定整套数据根目录，适合多项目管理
- 索引和日志默认保存在用户目录下的 `~/.skillsbrain/`

---

## 4. 准备技能目录

默认会扫描项目根目录下的 `skills/`。

标准结构如下：

```text
skills/
  pdf/
    SKILL.md
  weather/
    SKILL.md
```

每个技能目录中需要包含一个 `SKILL.md` 文件。

---

## 5. 查询技能

```bash
skillsbrain match "提取PDF中的表格"
```

常用参数：

```bash
skillsbrain match "生成Word报告" --agent claude_code --top-k 3
```

输出中会显示：
- 技能名称
- `skill_id`
- 来源
- 评分

---

## 6. 列出技能

```bash
skillsbrain list
```

按 Agent 类型过滤：

```bash
skillsbrain list --agent codex
```

---

## 7. 查看统计

```bash
skillsbrain stats
```

可以查看：
- 当前索引总量
- 使用的模型

---

## 8. 重建索引

```bash
skillsbrain reindex
```

适用于：
- 技能文件批量更新后
- 索引异常时

---

## 9. 订阅外部技能源

如果你有一个独立的技能目录，可以订阅后纳入检索：

```bash
skillsbrain subscribe D:/shared-skills --name shared
```

查看订阅源：

```bash
skillsbrain sources
```

取消订阅：

```bash
skillsbrain unsubscribe shared
```

### 订阅源行为
- 不修改原目录文件
- 订阅后自动索引
- 订阅后自动启动 watcher
- 取消订阅后自动清理对应索引

---

## 10. 首次使用建议流程

1. 准备本地 `skills/` 目录
2. 运行 `skillsbrain serve`
3. 使用 `skillsbrain list` 确认技能已被识别
4. 使用 `skillsbrain match` 进行查询
5. 如需共享技能，使用 `skillsbrain subscribe`

---

## 11. 健康检查

服务提供两个健康检查接口：

- `GET /health`
- `GET /health/ready`

---

## 12. 常见问题

### 1）为什么查不到技能？
请确认：
- `skills/` 目录结构正确
- `SKILL.md` frontmatter 格式正确
- `enabled` 不是 `false`
- 服务已经启动并完成索引

### 2）为什么订阅源没有生效？
请确认：
- 目录存在且可访问
- 目录下确实有标准 `SKILL.md`
- 订阅后可以使用 `skillsbrain sources` 查看状态

### 3）如何重建索引？
运行：

```bash
skillsbrain reindex
```

---

## 13. 小结

SkillsBrain 1.0.0 面向本地可信环境使用，提供：
- 本地技能路由
- 语义检索
- 增量同步
- 外部技能源订阅

推荐先从 `serve + match + list` 开始，再逐步接入订阅源能力。
