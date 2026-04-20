# 订阅源功能设计说明

## 1. 功能目标

SkillsBrain 支持在本地默认 `skills/` 目录之外，再订阅一个或多个外部技能目录作为额外的技能来源。

目标：
- 不修改订阅目录中的源文件
- 标准技能仍使用 `SKILL.md` 结构
- 订阅后即可参与检索与列表展示
- 取消订阅后，相关技能自动从索引中移除
- 订阅信息需本地持久化，服务重启后仍然生效

---

## 2. 核心设计

### 2.1 多源统一索引
系统将所有技能来源统一纳入同一个 Chroma 索引，但在 metadata 中保留来源信息。

当前来源分为：
- `local`：本仓库默认 `skills/` 目录
- `subscribed`：用户额外订阅的目录

### 2.2 索引主键
索引 id 采用：
```text
{source_name}:{skill_id}
```

例如：
- `local:pdf`
- `shared:pdf`

这样可以：
- 避免不同来源同名 skill 冲突
- 便于按来源删除
- 便于来源切换和统计

---

## 3. skill_id 规则

`skill_id` 仍沿用目录结构推导规则：

- 对标准结构 `skills/<name>/SKILL.md`
  - `skill_id = <name>`
- 对嵌套结构 `skills/tools/pdf/SKILL.md`
  - `skill_id = tools/pdf`

订阅源中的技能也遵循同一规则，只是索引时会附加来源名前缀。

---

## 4. 订阅信息持久化

订阅目录信息保存在：
```text
.index/subscriptions.json
```

示例：
```json
[
  {
    "name": "shared",
    "root": "D:/shared-skills",
    "enabled": true
  }
]
```

### 字段说明
- `name`：订阅源名称
- `root`：目录路径
- `enabled`：是否启用

---

## 5. 订阅流程

### 5.1 订阅
当用户执行：
```bash
skillsbrain subscribe D:\shared-skills --name shared
```

系统会：
1. 校验目录存在
2. 写入订阅配置
3. 扫描目录下所有 `SKILL.md`
4. 写入统一索引
5. 为该目录启动 watcher

### 5.2 取消订阅
当用户执行：
```bash
skillsbrain unsubscribe shared
```

系统会：
1. 查找订阅源
2. 停止该源 watcher
3. 从订阅配置中删除
4. 删除该源对应的全部索引数据

---

## 6. watcher 设计

### 当前策略
订阅后立即启动 watcher，监听该目录下的变更：
- 新增 `SKILL.md`
- 修改 `SKILL.md`
- 删除 `SKILL.md`

### 行为
- 变更时自动增量同步索引
- 不修改源目录文件本身
- 与本地默认 `skills/` 目录行为一致

### 说明
这一策略能保证订阅源的技能状态更接近实时。

---

## 7. API 与 CLI

### CLI
新增命令：
- `skillsbrain subscribe <path> [--name NAME]`
- `skillsbrain unsubscribe <name_or_root>`
- `skillsbrain sources`

### API
新增接口：
- `GET /api/source/list`
- `POST /api/source/subscribe`
- `POST /api/source/unsubscribe`

---

## 8. 返回字段

当技能被 match 或 list 出来时，推荐携带：
- `skill_id`
- `source_name`
- `source_root`
- `source_rel_path`
- `relative_path`
- `enabled`

这样可以让调用方知道技能来源，并决定后续如何加载。

---

## 9. 设计约束

- 不复制、不修改订阅目录中的源文件
- 订阅源与本地源统一索引
- 索引主键必须带来源前缀
- 取消订阅必须清理对应索引
- watcher 只做增量同步，不写回源文件

---

## 10. 总结

订阅源功能的目标是扩展 SkillsBrain 的技能来源能力，而不是改变源文件管理方式。

推荐实现策略：
- 统一索引
- 源信息入 metadata
- 订阅信息本地持久化
- 订阅后自动 watcher
- 取消订阅后自动清理索引
