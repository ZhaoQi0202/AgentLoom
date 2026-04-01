# AgentLoom 四阶段流水线架构设计

> 日期: 2026-04-02
> 状态: 待实现
> 实现策略: 逐环节完善（按阶段顺序依次实现到位）

---

## 1. 概述

AgentLoom 的核心是一条 **四阶段流水线**，每个阶段有明确的输入/输出/退回机制：

```
[需求收集] ←→ [架构设计] → [多Agent执行 ←→ 审核] → [完成]
     ↑              ↑              ↑
     └──不可行退回───┘     └──降级退回──┘
```

**技术选型**: LangGraph 多层图架构 — 顶层状态机管理四阶段流转，第三阶段内部用动态 DAG 子图管理并行 Agent。

---

## 2. 阶段一：需求收集

### 2.1 核心理念

混合模式对话（参考 superpowers brainstorming skill）：先让用户自由描述，AI 分析完整度后决定是否追问，最终由 AI 提出摘要、用户确认后进入下一阶段。

### 2.2 Consultant Agent 行为流程

1. **开场**: 用户创建项目组后，Consultant 在群聊中"加入群聊"并自我介绍，邀请用户描述需求
2. **用户自由描述**: 用户输入初始需求（一句话或一大段均可）
3. **AI 分析 + 追问**: Consultant 分析用户描述，从以下维度检查缺失：
   - 核心目标（要做什么）
   - 约束条件（技术栈、平台、时间）
   - 成功标准（怎样算完成）
   - 优先级（哪些必须有，哪些可选）
   - **一次只问一个问题，选择题优先**
4. **摘要确认**: 当 Consultant 判断信息充分时，输出结构化需求摘要，询问用户是否确认
5. **用户确认** → 生成 `requirement.json` 存入 workspace，进入阶段二

### 2.3 后端实现要点

- Consultant Agent 使用 ReAct 循环 + 对话历史（LangGraph checkpoint 保持多轮状态）
- 不再是单次 LLM 调用，而是一个持续对话的 Agent
- WebSocket `collect` action 传递用户每轮输入，`confirm_start` 触发阶段转换

### 2.4 产出物

`requirement.json` — 结构化需求文档，作为架构设计的输入。

---

## 3. 阶段二：架构设计

### 3.1 Architect Agent 行为流程

1. **加入群聊**: Consultant 确认需求后，Architect "加入群聊"，@Consultant 表示收到需求
2. **工具盘点**: Architect 自动查询当前可用能力：
   - 全局 skills（已安装的）
   - 全局 MCPs（已配置的）
   - 内置能力（Python 执行、Shell 命令）
   - 通过 find-skill 搜索可能需要的额外 skill
3. **Skill 装载流程**（发现需要安装新 skill 时）:
   - 在群聊中告知用户 skill 的名称、作用、为什么需要它
   - 用户确认同意安装 → 继续；用户拒绝 → 寻找替代方案
   - 调用内置漏洞检查 skill 扫描目标 skill
     - 扫描通过 → 安装到项目组级别
     - 扫描发现问题 → 在群聊中报告问题详情，询问用户是否仍然安装
       - 用户同意 → 安装（带风险标记）
       - 用户拒绝 → 寻找替代方案或调整规划
   - 若无替代方案且该 skill 是关键依赖 → 标记对应功能点为不可行，触发退回
4. **可行性分析**:
   - 将需求拆解为功能点
   - 每个功能点匹配可用工具
   - 若某功能点无法实现 → 在群聊中说明原因，@Consultant 提议回退需求收集重新讨论
5. **DAG 规划生成**: 输出结构化规划 `blueprint.json`
6. **用户确认规划**: 在群聊中展示规划摘要（HITL 中断），用户可以：
   - 确认 → 进入阶段三
   - 提出修改意见 → Architect 调整后重新展示
   - 回退 → 返回阶段一重新收集需求

### 3.2 Blueprint 数据结构

```json
{
  "tasks": [
    {
      "id": "t1",
      "name": "实现天气API后端",
      "goal": "创建 /api/weather 端点，接收城市名返回天气数据",
      "acceptance_criteria": ["API 返回 JSON 格式", "错误处理完备"],
      "tools": ["shell", "python", "weather-mcp"],
      "depends_on": []
    },
    {
      "id": "t2",
      "name": "实现前端页面",
      "goal": "创建天气查询页面，调用后端 API 展示结果",
      "acceptance_criteria": ["页面可输入城市名", "正确展示天气数据"],
      "tools": ["shell", "frontend-skill"],
      "depends_on": ["t1"]
    }
  ]
}
```

### 3.3 不可行退回机制

- Architect 明确说明哪些功能点无法实现、为什么
- 给出建议（降低需求 / 换一种方式实现 / 补充工具）
- 自动回退到阶段一，Consultant 接手继续与用户讨论

### 3.4 产出物

`blueprint.json` — DAG 任务规划，包含每个任务的 id、目标、验收标准、工具集、依赖关系。

---

## 4. 阶段三：多 Agent 执行

### 4.1 核心机制

这是最核心的环节。Architect 输出的 `blueprint.json` 是一个 DAG，系统据此动态生成并调度 Agent。

### 4.2 Orchestrator（调度器）行为

1. **解析 DAG**: 读取 `blueprint.json`，构建任务依赖图
2. **动态生成 Agent**: 为每个任务点创建一个 ReAct Agent，配置：
   - 专属 system prompt（包含任务目标、验收标准、人格化语气指引）
   - 授权工具集（blueprint 中指定的 tools）
   - 工作目录（项目组 workspace）
3. **调度执行**:
   - 无依赖的任务 → 立即并行启动（asyncio 并发）
   - 有依赖的任务 → 等待前置任务完成且审核通过后启动
4. **群聊互动**:
   - Agent 启动时在群聊中发消息
   - 有依赖时 @上游 Agent 确认收到产出
   - 上游 Agent 完成时 @下游 Agent 通知
   - 执行过程中只报告关键里程碑（不刷屏）

### 4.3 单个 ReAct Agent 执行循环

```
思考（分析当前状态和下一步）
  → 调用工具（skill / MCP / Python / Shell）
  → 观察结果
  → 判断是否完成
  → 未完成则继续循环
  → 完成则输出产出物，触发审核
```

### 4.4 Agent 可用工具类型

| 工具类型 | 说明 |
|---------|------|
| Shell | 执行命令行操作 |
| Python | 运行 Python 脚本（在 workspace 的 venv 中） |
| Skill | 调用已安装的 skill（全局 + 项目组级别） |
| MCP | 调用已配置的 MCP server 提供的工具 |

### 4.5 Agent 群聊语气

- 正事为主、语气活泼、偶尔打趣，避免机械式汇报
- 不同 Agent 有略微不同的性格倾向
- 示例：
  - 上游完成通知: "@前端Agent API 接口已就绪，文档放在 /docs 下了，别说我没给你留好吃的"
  - 下游接收回应: "@后端Agent 收到！接口看着很清晰，这次不用猜你的 API 了哈哈，开干"
  - 里程碑汇报: "登录模块搞定了，丝滑得像德芙，下一步搞权限校验"

### 4.6 产出物管理

- 每个 Agent 的产出（文件、代码、脚本等）写入 workspace 对应子目录
- 完成时生成 `task_output.json` 记录产出清单和自评摘要

---

## 5. 阶段四：审核反馈

### 5.1 Reviewer Agent 行为

1. **触发时机**: 每个执行 Agent 完成任务后立即触发（单任务完成即审，不阻塞其他并行任务）
2. **审核内容**: 对比任务目标（blueprint）和实际产出（task_output），检查：
   - 产出是否完整覆盖任务目标和验收标准
   - 代码/脚本是否可运行（可调用 shell 做简单验证）
   - 是否有明显遗漏或错误
3. **审核结果**:
   - **pass** → 标记任务完成，触发下游依赖任务启动
   - **fail** → 退回执行 Agent 并附上具体改进建议

### 5.2 Reviewer 人格

相对毒舌但专业。审核严格，通过时大方夸赞，不通过时犀利指出问题但给出具体建议。

- 审核通过: "@后端Agent 代码过了一遍，没毛病，稳得一批，下一位！"
- 审核不通过: "@后端Agent 哥们儿你这个接口少了错误处理，用户传个空值直接炸了，改一下？具体建议：..."

### 5.3 降级链路

```
Agent 执行完成 → Reviewer 审核
  ├─ pass → 完成，触发下游依赖任务
  └─ fail → 退回 Agent 修改（最多 3 次）
               └─ 仍 fail → 用户决策
                    ├─ 接受当前结果 → 继续下游
                    └─ 架构师调整 → Architect 重新设计该任务点（最多 2 次）
                         ├─ 新 Agent 执行 → 回到审核流程
                         └─ 仍 fail → 用户只能接受或跳过
                              ├─ 接受 → 继续下游
                              └─ 跳过 → 标记失败，通知下游依赖任务
```

### 5.4 下游依赖处理

当一个任务被跳过时：
- 所有下游依赖任务在群聊中收到通知
- 用户可选择：让下游任务尝试在缺失前置的情况下继续，或也跳过

---

## 6. 前端设计

### 6.1 整体布局

保持现有三栏布局：
- **左侧**: 项目组列表（TaskList）
- **中间**: 群聊主界面（ChatArea）— 所有阶段的交互都在此展现
- **右侧**: 状态总览面板（RightPanel）

### 6.2 群聊主界面

- 所有 Agent 在同一个群聊中交互，以不同头像/颜色区分
- Agent 之间用 @Name 互相引用，模拟真实项目组群聊
- 用户在同一个输入框参与对话（需求描述、确认、反馈）
- HITL 中断点以卡片形式展示，提供确认/修改/回退选项

### 6.3 右侧状态面板

分四栏，对应四个阶段，每栏显示该阶段中的 Agent：
- **需求收集栏**: Consultant Agent
- **架构设计栏**: Architect Agent
- **执行栏**: 动态生成的 N 个执行 Agent
- **审核栏**: Reviewer Agent

每个 Agent 右上角状态指示灯：
- 灰色圆点: 未执行
- 绿色圆点: 正在执行
- 红色圆点: 有问题（审核失败/执行出错）

---

## 7. 数据流总结

```
用户输入
  ↓
[Consultant] → requirement.json
  ↓
[Architect] → blueprint.json (DAG)
  ↓
[Orchestrator] → 动态生成 Agent-1..Agent-N
  ↓
[Agent-1..N] → task_output.json (各自)
  ↓
[Reviewer] → pass/fail 判定
  ↓
完成 / 退回修改 / 降级处理
```

---

## 8. 关键阈值配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_agent_retry` | 3 | 单个 Agent 被审核退回后的最大重试次数 |
| `max_architect_revision` | 2 | 架构师对同一功能点的最大调整次数 |

---

## 9. 与现有代码的关系

### 保留

- FastAPI + WebSocket 通信架构
- LangGraph 作为图引擎
- 前端 React + Zustand + 群聊 UI 框架
- 配置系统（model connections, MCPs, skills）
- 任务 workspace 隔离（uv venv）

### 重构

- `graph/builder.py`: 从固定 5 节点线性图 → 顶层状态机 + 动态 DAG 子图
- `graph/nodes/stubs.py`: 从 stub 单次调用 → 真正的 ReAct Agent 循环
- `graph/state.py`: 扩展状态定义以支持 DAG、多 Agent 运行状态、审核轮次
- `api/routes/graph.py`: WebSocket 事件类型扩展（支持 @互动、Agent 动态加入等）

### 新增

- `graph/orchestrator.py`: DAG 调度器
- `graph/nodes/react_agent.py`: 通用 ReAct Agent 工厂
- `tools/`: 工具适配层（shell、python、skill、mcp 统一接口）
- 前端右侧面板四栏布局组件
