# Skill ID 与本地路由设计说明

## 1. 设计目标

SkillsBrain 是一个本地技能路由引擎，目标不是直接让 Agent 处理文件系统细节，而是提供稳定的技能检索与定位能力。

核心原则：
- `skill_id` 作为技能的逻辑主键
- `SKILL.md` 是技能状态的唯一事实来源
- 路由层负责发现、索引、查询和返回技能元信息
- 本地 Agent 可以基于 `skill_id` 或 `relative_path` 继续加载技能内容

---

## 2. skill_id 的生成规则

当前实现中，`skill_id` 由技能文件在 `skills/` 根目录下的相对路径推导而来。

### 规则

1. 先获取技能文件的绝对路径
2. 再计算它相对于 `skills_dir` 的相对路径
3. 如果文件名为 `SKILL.md`，则取其父目录作为 `skill_id`
4. 如果不是标准目录结构，则使用相对路径本身作为 `skill_id`

### 示例

#### 标准结构
```text
skills/pdf/SKILL.md
```
对应：
- `skill_id = "pdf"`
- `relative_path = "pdf/SKILL.md"`

#### 嵌套结构
```text
skills/tools/pdf/SKILL.md
```
对应：
- `skill_id = "tools/pdf"`
- `relative_path = "tools/pdf/SKILL.md"`

### 设计意义

- 便于 watcher 根据文件路径反推出稳定主键
- 避免把 `name` 当作唯一主键造成冲突
- 适配本地目录式技能组织方式

---

## 3. 路由与加载策略

### 当前策略
SkillsBrain 的职责是：
- 扫描 `skills/` 目录
- 解析 `SKILL.md`
- 建立索引
- 提供检索结果

检索结果中包含：
- `skill_id`
- `name`
- `relative_path`
- `file_path`（本地模式下保留）

### Agent 侧建议
Agent 优先使用：
- `skill_id`
- `relative_path`

而不是直接依赖绝对路径。

如果 Agent 运行在同一台机器上，并且需要直接读取文件，那么它可以：
- 先拿到 `relative_path`
- 再结合自己已知的 `skills_dir` 根目录进行拼接

这样可以避免将宿主机完整目录结构作为强依赖暴露给调用方。

---

## 4. enabled 状态策略

当前项目采用“**文件为准**”原则：

- `enabled` 只从 `SKILL.md` frontmatter 中读取
- 路由工具只负责读取，不提供修改 enabled 状态的接口
- 技能是否可用由技能文件自身元数据决定

这意味着：
- 索引只是镜像源文件状态
- 不存在单独的可写 enabled 覆盖层
- 重建索引时不会改变源文件表达的状态

### 示例
```yaml
---
name: pdf-table-extract
enabled: true
---
```

如果写成：
```yaml
---
name: pdf-table-extract
enabled: false
---
```
则该技能会在索引和查询结果中被视为禁用。

---

## 5. 文件路径暴露策略

在本地单机运行场景下，保留 `file_path` 是可接受的，因为它能直接支持本机 Agent 或 CLI 的后续处理。

但建议同时保留：
- `skill_id`
- `relative_path`

并将它们作为主要对外标识。

### 推荐使用顺序
1. `skill_id`
2. `relative_path`
3. `file_path`（仅本地可信环境）

---

## 6. 结果字段建议

建议检索返回的标准字段包括：
- `skill_id`
- `name`
- `description`
- `compatibility`
- `tags`
- `enabled`
- `relative_path`
- `file_path`（可选）
- `score`

这样可以兼顾：
- 路由判断
- 本地加载
- 调试排查
- 后续扩展

---

## 7. 总结

SkillsBrain 中的 `skill_id` 是一个由目录结构推导出来的稳定逻辑主键，而不是手工输入的业务名称。

推荐实践：
- 统一以 `skill_id` 作为索引主键
- `SKILL.md` 是状态事实来源
- 本地 Agent 优先使用 `skill_id` / `relative_path` 进行后续加载
- 保留 `file_path` 仅作为本地调试或兼容字段
