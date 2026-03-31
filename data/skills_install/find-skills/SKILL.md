---
name: find-skills
description: 为当前任务检索可安装的 Agent Skills，经用户确认后安装到该任务目录（非应用全局）。
---

# find-skills

## 何时使用

- 任务级需要额外 Skills，而应用级技能（技能管理安装的）不够用。
- 用户明确要求为**当前任务**搜索或安装 Skills。

## 安装位置（必须）

- 仅写入 **当前任务根目录** 下：`<任务根>/.agentloom/skills/<skill-id>/`（内含 `SKILL.md`）。
- **不得**把任务级技能写入 `data/skills_install/`；该目录仅用于**应用级**（技能管理或内置默认副本）。

## 实现约定

- 安装副本请调用运行时 API：`agentloom.skills.skill_import.install_skill_roots_to_task_workspace`（由编排层注入 `task_workspace`）。
- 执行任意 Agent 时，可用 `agentloom.skills.registry.merged_skills_for_agents(task_workspace)` 得到 **应用级 + 当前任务级** 全部已启用技能（同名时任务级覆盖应用级）。

## 行为要点

1. **检索**：仓库 URL、本地路径、团队清单等；只读浏览元数据，不执行候选包内代码。
2. **展示**：name、description、来源、风险摘要。
3. **HITL**：安装前必须说明目标路径并获用户确认。
4. **安装后**：提示本任务内已可用；无需在「技能管理」中注册。

## 禁止

- 静默安装、覆盖已有目录不提示。
- 把任务级技能安装到应用全局目录。
