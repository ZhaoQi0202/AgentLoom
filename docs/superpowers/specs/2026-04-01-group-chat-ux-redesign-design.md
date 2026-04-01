# AgentLoom 群聊体验重构设计

## 概述

将 AgentLoom 从"任务执行工具"转变为"群聊协作体验"，让用户感受到与一群 AI 专家在群聊中协作完成项目的沉浸感。

## 修改清单

### 1. "新建任务" → "新建项目组"

**当前行为：** 侧边栏 TaskList 中用户输入任务名创建任务，任务名同时作为 user_request 传给图谱。

**目标行为：**
- 按钮文案改为 **"新建项目组"**
- 输入框提示文字改为 "项目组名称..."
- 创建后自动进入聊天界面
- 需求分析师自动"加入群聊"并发起对话（见第 6 点）

**影响文件：**
- `client/src/components/layout/TaskList.tsx` — 按钮文案、placeholder

### 2. "加入群聊" 提示

**当前行为：** `phase_start` 事件显示为 "阶段: consultant" 样式的系统消息。

**目标行为：**
- 每个 agent 阶段开始时，聊天区显示居中系统消息：`<Agent中文名> 加入群聊`
- 样式：浅色药丸标签（类似微信群提示）
- 替代现有的 `phase_start` 系统消息展示方式

**影响文件：**
- `client/src/components/chat/ChatArea.tsx` — `phase_start` 事件渲染逻辑
- `src/agentloom/api/routes/graph.py` — `phase_start` 事件 content 字段改为中文名

### 3. 打字中动画

**当前行为：** 无打字中动画，agent 输出直接出现。

**目标行为：**
- 后端在调用 LLM **之前**发送 `agent_thinking` 事件（携带 agent 信息）
- 前端收到后显示该 agent 的 `......` 动画气泡（脉冲/波浪效果）
- 动画持续时间 = LLM 实际生成时间（非固定时长）
- 后端 LLM 返回后发送 `agent_output` 事件
- 前端收到 `agent_output` 后，用完整消息一次性替换动画气泡

**影响文件：**
- `client/src/components/chat/ChatArea.tsx` — `agent_thinking` 事件渲染（动画气泡组件）
- `client/src/styles/globals.css` — 打字动画 CSS keyframes
- `src/agentloom/api/routes/graph.py` — 在 agent 节点执行前发送 `agent_thinking` 事件

### 4. Agent 回复限制 100-200 字符

**当前行为：** agent 输出较长，不符合群聊风格。

**目标行为：**
- 每个 agent 的 system prompt 中添加字数限制指令
- 要求 agent 用简短、群聊风格的语言回复（100-200 字符）
- 使回复更像真人在群聊中的发言

**影响文件：**
- `src/agentloom/graph/nodes/stubs.py` — 各 agent 节点的 prompt 模板

### 5. 运行按钮改为三态控制

**当前行为：** 单个"运行图谱"/"重新运行"按钮。

**目标行为：**
- **启动项目**（绿色）：替代原"运行图谱"按钮，开始执行图谱
- **暂停项目**（黄色）：运行中显示，点击后立即暂停
  - 中断当前 WebSocket 流
  - 利用 LangGraph SQLite checkpointer 保存当前状态
  - 记录暂停位置（当前 agent 节点）
- **继续项目**（绿色）：暂停后显示，从暂停点继续执行
  - 由于是立即暂停，当前节点可能未完成，继续时重新运行当前节点

**状态机：**
```
idle → [启动项目] → running → [暂停项目] → paused → [继续项目] → running
                                                   ↘ [启动项目] → running (重新开始)
```

**影响文件：**
- `client/src/components/chat/ChatArea.tsx` — 按钮渲染逻辑
- `client/src/stores/chatStore.ts` — 新增 `isPaused` 状态、`pauseGraph()`、`resumeGraph()` 方法
- `client/src/services/websocket.ts` — 新增 `pause` action 支持
- `src/agentloom/api/routes/graph.py` — 处理 `pause` action，保存暂停点

### 6. 需求收集 Agent 自动发起对话

**当前行为：** 用户创建任务后需手动点击"运行图谱"，所有 agent 按序自动执行。

**目标行为：**
1. 用户新建项目组后，自动触发需求收集流程
2. 发送 `phase_start` 事件 → "需求分析师 加入群聊"
3. 需求分析师发送自我介绍 + 顺势提问消息
4. 用户通过 ChatInput 回复
    - ChatInput 在需求收集阶段始终可用（不仅限于 HITL 中断时）
5. 需求分析师根据用户回复 + 已配置的工具情况判断是否需要补充信息
6. 如需补充 → 继续提问（多轮对话）
7. 如信息充足 → 发出确认提问："需求已明确，是否启动项目？"
8. 用户确认后 → 后续 agent 按序执行

**实现方式：**
- 需求收集阶段是一个独立的 WebSocket 交互流程，不走完整图谱
- 后端新增 `/api/ws/collect/{session_id}` 或复用现有 WebSocket 并新增 `action: "collect"` 模式
- 需求收集 agent 使用 LLM 进行多轮对话，结合已配置的 MCP tools/skills 信息判断可行性
- 收集完成后，将整理好的需求作为 `user_request` 传入图谱执行

**影响文件：**
- `client/src/stores/chatStore.ts` — 新增需求收集模式状态管理
- `client/src/components/chat/ChatInput.tsx` — 需求收集阶段也启用输入
- `src/agentloom/api/routes/graph.py` — 新增需求收集 WebSocket 处理逻辑
- `src/agentloom/graph/nodes/stubs.py` — 需求分析师多轮对话 prompt

### 7. 浅色毛玻璃主题

**当前行为：** 深色主题（#09090f 背景 + 白色半透明玻璃态）。

**目标行为：** 浅色主题 + 毛玻璃效果 + 紫蓝渐变品牌色保留。

**CSS 变量映射：**

| 变量 | 原值（深色） | 新值（浅色） |
|------|------------|------------|
| `--color-bg-base` | `#09090f` | `#fafafe` |
| `--color-bg-surface` | `#13131a` | `linear-gradient(180deg, #f5f5ff, #f0f4ff)` |
| `--color-bg-elevated` | `rgba(255,255,255,0.03)` | `rgba(255,255,255,0.7)` |
| `--color-bg-hover` | `rgba(255,255,255,0.05)` | `rgba(139,92,246,0.06)` |
| `--color-border-subtle` | `rgba(255,255,255,0.06)` | `rgba(139,92,246,0.06)` |
| `--color-border-default` | `rgba(255,255,255,0.08)` | `rgba(139,92,246,0.10)` |
| `--color-border-strong` | `rgba(255,255,255,0.12)` | `rgba(139,92,246,0.15)` |
| `--color-text-primary` | `#e4e4e7` | `#1e293b` |
| `--color-text-body` | `#d4d4d8` | `#334155` |
| `--color-text-secondary` | `#a1a1aa` | `#64748b` |
| `--color-text-muted` | `#71717a` | `#94a3b8` |
| `--color-text-disabled` | `#52525b` | `#cbd5e1` |

- 品牌色保留：`--color-brand-purple: #8b5cf6`、`--color-brand-blue: #3b82f6`
- `.glass` 效果：`background: rgba(255,255,255,0.7); backdrop-filter: blur(12px);`
- 滚动条：调整为浅色系
- Agent 消息气泡：白底 + 淡边框 + 轻投影
- 用户消息气泡：紫蓝渐变背景 + 白色文字

**影响文件：**
- `client/src/styles/globals.css` — 全部 CSS 变量 + 组件样式
- `client/src/types/index.ts` — Agent `nameColor` 调整为适配浅色背景的颜色

### 8. Agent 中文名称

| AgentId (不变) | 原 label | 新 label | emoji (不变) |
|---------------|---------|---------|-------------|
| `consultant` | Consultant | 需求分析师 | 🔍 |
| `architect` | Architect | 架构设计师 | 📐 |
| `hitl_blueprint` | HITL Blueprint | 方案审核员 | ⏸ |
| `experts` | Expert (Swarm) | 执行专家组 | ⚡ |
| `reviewer` | Reviewer | 质量审查员 | 🔎 |

- 前端 `AGENT_META` 的 `label` 字段改为中文
- 后端 `graph.py` 事件消息中使用中文名
- `AgentId` 类型保持英文不变，确保前后端通信兼容

**影响文件：**
- `client/src/types/index.ts` — `AGENT_META` label 字段
- `src/agentloom/api/routes/graph.py` — 事件 content 中的 agent 名称

## 不在范围内

- 暗色/亮色主题切换功能（只做浅色）
- Agent 头像自定义
- 消息撤回、删除功能
- 文件/图片发送功能
- 新增 agent 角色
