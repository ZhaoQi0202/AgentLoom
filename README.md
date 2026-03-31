# AgentLoom

桌面端多智能体协作：按**任务文件夹**隔离，任务内用 **uv** 建独立环境；编排为 **LangGraph** 多阶段流程（含人在回路中断）；支持 **MCP**、本机命令与 **Skills** 扩展。

**仓库：** [github.com/ZhaoQi0202/AgentLoom](https://github.com/ZhaoQi0202/AgentLoom)

## 架构

| 部分 | 说明 |
|------|------|
| **Python 后端** | FastAPI（`src/agentloom/`），默认监听 **`127.0.0.1:9800`**；REST 配置与任务；图谱通过 **WebSocket** `ws://127.0.0.1:9800/api/ws/graph/{session_id}` 推送事件 |
| **桌面客户端** | `client/`：**Electron + React + Vite + Tailwind**；开发时 Vite 固定 **`http://localhost:25527`**（`strictPort`）；Electron 可自动拉起项目根目录 **`.venv`** 里的 API 进程 |
| **数据与配置** | 相对**安装根**（项目根或环境变量 **`AGENTLOOM_ROOT`**）：`config/`、`data/`、`workspaces/` |

## 技术栈

- Python 3.11+、[uv](https://github.com/astral-sh/uv)
- FastAPI、Uvicorn、WebSockets
- LangChain（多厂商 Chat）+ LangGraph（SQLite checkpoint）
- Pydantic
- 客户端：React 19、Zustand、Framer Motion、Electron

## 环境要求

- **Python 3.11+**、已安装 **uv**
- 开发桌面客户端：**Node.js**（建议 LTS）、`npm`
- 任务工作区内执行 `uv venv` / `uv run` 时，本机需能调用 **uv**（与 PyInstaller 打包策略无关时可单独讨论）

## 快速开始

**1. 克隆与 Python 依赖**

```powershell
git clone https://github.com/ZhaoQi0202/AgentLoom.git
cd AgentLoom
uv sync
```

**2. 启动方式（任选）**

- **桌面应用（推荐日常开发）** — 在项目根执行：

  ```powershell
  cd client
  npm install
  npm run dev:electron
  ```

  会并行启动：Vite（**25527**）+ 等待页面就绪后启动 Electron；Electron 内会尝试启动 **`python -m agentloom.api.server`**（优先 `.venv\Scripts\python.exe`）。若 **25527 已被占用**，需先结束占用进程后再启动。

- **仅后端 API**（自行用浏览器或别的客户端连 `9800`）：

  ```powershell
  uv run python -m agentloom
  ```

  等价于启动 Uvicorn；安装根下会自动确保目录布局存在。

- **仅初始化目录、不启服务**：

  ```powershell
  uv run python -m agentloom --cli
  ```

- **客户端 UI 与浏览器**：界面**仅应在 Electron 内使用**；在浏览器中直接打开 Vite 开发地址会显示「请使用桌面客户端」。开发阶段若必须在浏览器里调试前端，可在 `client/` 构建/启动前设置 **`VITE_ALLOW_BROWSER=true`**（不要打进给最终用户的包）。

## 配置与数据

| 项 | 说明 |
|------|------|
| 任务工作区 | `workspaces/task_<时间戳>_<名称>/`，新建任务时初始化 uv 环境 |
| 模型与连接 | 客户端「模型」页，或手写 `config/settings.json`、`config/model_connections/`（**勿提交**，见 `.gitignore`） |
| MCP | `config/mcp/<id>.json` 与 `manifest.json` |
| 技能（应用级） | `data/skills_install/`；与任务目录下 `.agentloom/skills/` 在执行侧合并，同名以任务级为准 |

## 常见问题

- **Vite 报 `Port 25527 is already in use`**：上次 Node/Electron 未退出或其它程序占用。在 **PowerShell** 中查看并结束占用进程，例如：

  ```powershell
  Get-NetTCPConnection -LocalPort 25527 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
  ```

- **Electron 里后端起不来**：确认已在仓库根执行 **`uv sync`** 生成 `.venv`；Windows 下若未装全局 `python`，依赖上述 `.venv` 路径。

## Windows 打包（Python 壳）

```powershell
uv sync
uv run pyinstaller --noconfirm packaging\agentloom.spec
```

产物见 `dist\AgentLoom\`。当前入口为 **`python -m agentloom`**（控制台 + API）；Electron 客户端打包见 `client` 内 `electron-builder` 配置。

## 测试

```powershell
uv sync --group dev
uv run pytest -q
```

## 文档

设计与计划见 `docs/superpowers/specs/`、`docs/superpowers/plans/`。

## 许可证

Apache License 2.0 — 见 [LICENSE](LICENSE)。
