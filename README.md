# AgentLoom

多智能体协作平台 — 通过**四阶段流水线**将用户需求转化为实际执行：需求收集 → 架构设计 → 多 Agent 执行 → 审核反馈。所有交互在**群聊界面**中以拟真项目组对话形式展现。

**仓库：** [github.com/ZhaoQi0202/AgentLoom](https://github.com/ZhaoQi0202/AgentLoom)

## 核心流程

```
[需求收集] ←→ [架构设计] → [多Agent执行 ←→ 审核] → [完成]
     ↑              ↑              ↑
     └──不可行退回───┘     └──降级退回──┘
```

| 阶段 | 负责 Agent | 做什么 | 产出 |
|------|-----------|--------|------|
| **需求收集** | 需求分析师 | 与用户多轮对话，逐步澄清需求（混合模式：用户自由描述 + AI 追问） | `requirement.json` |
| **架构设计** | 架构设计师 | 读取需求 + 查询可用工具（Skills/MCP/内置能力），生成 DAG 任务规划 | `blueprint.json` |
| **多 Agent 执行** | 动态生成 N 个执行专家 | 按 DAG 依赖关系调度，每个 Agent 用 ReAct 循环执行（思考→调用工具→观察→重复） | `task_outputs/` |
| **审核反馈** | 质量审查员 | 每个任务完成后即时审核，不通过则带反馈重试（最多 3 次），最终汇总 | 通过/降级处理 |

### 降级链路

```
Agent 执行 → Reviewer 审核
  ├─ pass → 完成，触发下游依赖
  └─ fail → 退回 Agent 修改（≤3次）
               └─ 仍 fail → 最终汇总，用户决策（接受/重做）
```

## 架构

| 部分 | 说明 |
|------|------|
| **Python 后端** | FastAPI（`src/agentloom/`），监听 `127.0.0.1:9800`；REST 配置与任务管理；WebSocket `ws://127.0.0.1:9800/api/ws/graph/{session_id}` 实时推送事件 |
| **桌面客户端** | `client/`：Electron + React 19 + Vite + Tailwind；开发端口 `25527` |
| **图引擎** | LangGraph 多阶段流水线 + SQLite checkpoint；支持 HITL（人在回路）中断 |
| **事件总线** | Event Bus 允许 Agent 内部实时推送事件到 WebSocket，实现流式群聊输出 |

## 技术栈

- **后端：** Python 3.11+、FastAPI、Uvicorn、WebSockets
- **AI：** LangChain（Anthropic + OpenAI）、LangGraph、SQLite checkpoint
- **工具执行：** Shell（cmd/PowerShell）、Python（workspace venv）
- **数据：** Pydantic、JSON 配置
- **前端：** React 19、TypeScript、Zustand、Framer Motion、Tailwind CSS、Electron

## 项目结构

```
src/agentloom/
├── api/                    # FastAPI 路由（REST + WebSocket）
│   └── routes/
│       ├── graph.py        # WebSocket：collect/confirm_start/start/resume
│       ├── tasks.py        # 项目组 CRUD
│       └── config.py       # 模型/MCP/Skills 配置
├── graph/                  # LangGraph 图引擎
│   ├── builder.py          # 图构建与编译
│   ├── state.py            # AgentLoomState 类型定义
│   ├── event_bus.py        # 事件总线（实时流式推送）
│   ├── orchestrator.py     # DAG 调度器（拓扑排序 + 分层执行）
│   └── nodes/
│       ├── consultant_agent.py  # 需求收集多轮对话
│       ├── architect_agent.py   # 架构设计 + blueprint 生成
│       ├── react_agent.py       # ReAct 循环执行器
│       ├── reviewer_agent.py    # 单任务审核
│       └── stubs.py             # 图节点入口（调用上述 agent）
├── tools/                  # Agent 工具层
│   ├── shell_tool.py       # Shell 命令执行（复用 ShellRunner）
│   ├── python_tool.py      # Python 脚本执行（workspace venv）
│   └── tool_registry.py    # 工具 ID → LangChain Tool 映射
├── tasks/                  # 任务数据管理
│   ├── workspace.py        # 项目组目录管理
│   ├── requirement.py      # requirement.json 存取
│   └── blueprint.py        # blueprint.json 存取
├── config/                 # 配置加载
├── llm/                    # LLM 工厂（支持多厂商）
├── skills/                 # Skills 注册与合并
└── runtime/                # 底层进程执行

client/src/
├── components/
│   ├── chat/               # 群聊界面（ChatArea、ChatInput、AgentMessage 等）
│   ├── layout/             # 布局（TaskList、RightPanel、IconSidebar）
│   ├── config/             # 配置页面（Models、MCP、Skills、Settings）
│   └── shared/             # 通用组件
├── stores/                 # Zustand 状态管理
│   ├── chatStore.ts        # 聊天/流程状态
│   ├── taskStore.ts        # 项目组状态
│   └── configStore.ts      # 配置状态
├── services/               # API 和 WebSocket 客户端
└── types/                  # TypeScript 类型定义
```

## 环境要求

- **Python 3.11+**、已安装 [uv](https://github.com/astral-sh/uv)
- **Node.js**（LTS 推荐）、`npm`
- 至少配置一个 LLM 连接（OpenAI 兼容 / Anthropic）

## 快速开始

**1. 克隆与安装依赖**

```powershell
git clone https://github.com/ZhaoQi0202/AgentLoom.git
cd AgentLoom
uv sync
```

**2. 启动方式**

- **桌面应用（推荐）：**

  ```powershell
  cd client
  npm install
  npm run dev:electron
  ```

  并行启动 Vite（25527）+ Electron；Electron 自动拉起后端 API（9800）。

- **仅后端 API：**

  ```powershell
  uv run python -m agentloom
  ```

**3. 使用流程**

1. 在左侧「新建项目组」
2. 需求分析师自动加入群聊，与你沟通需求
3. 需求确认后点击「启动项目」
4. 架构设计师生成任务规划 → 你审核确认
5. 多个执行 Agent 按 DAG 依赖调度执行，群聊实时展示进展
6. 每个任务完成后 Reviewer 即时审核，不通过自动重试
7. 最终汇总报告

## 配置

| 项 | 说明 |
|------|------|
| 项目组工作区 | `workspaces/task_<时间戳>_<名称>/`，含独立 venv、`requirement.json`、`blueprint.json`、`task_outputs/` |
| 模型连接 | 客户端「模型」页配置，或手写 `config/model_connections/`（勿提交） |
| MCP 服务 | `config/mcp/<id>.json` |
| Skills | 应用级 `data/skills_install/`；项目级 `<workspace>/.agentloom/skills/`（同名以项目级优先） |
| 阈值参数 | `max_agent_retry = 3`（Agent 重试次数）、`max_iterations = 15`（ReAct 循环上限） |

## 测试

```powershell
uv sync --group dev
uv run pytest -q
```

当前 72 个测试覆盖：图编译、需求收集、架构设计、工具注册、ReAct Agent、DAG 拓扑排序、审核判定、事件总线等。

## 常见问题

- **Vite 报 `Port 25527 is already in use`：** 上次进程未退出。PowerShell 中执行：

  ```powershell
  Get-NetTCPConnection -LocalPort 25527 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  ```

- **Electron 里后端起不来：** 确认已在仓库根执行 `uv sync` 生成 `.venv`。

- **Agent 不调用工具：** 确认已配置 LLM 连接（需要支持 tool calling 的模型，如 GPT-4o、Claude 3.5+）。

## 设计文档

- 四阶段流水线架构：`docs/superpowers/specs/2026-04-02-four-phase-pipeline-design.md`
- 历史设计：`docs/superpowers/specs/` 目录

## 许可证

Apache License 2.0 — 见 [LICENSE](LICENSE)。
