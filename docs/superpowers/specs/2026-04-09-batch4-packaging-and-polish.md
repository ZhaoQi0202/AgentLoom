# Batch 4 设计规格：打包发布 + 收尾打磨

> **日期**：2026-04-09
> **范围**：F-15、F-16、G4
> **前置**：Batch 1 + Batch 2 + Batch 3 全部完成

---

## 1. F-15：自包含 Windows 安装包

### 1.1 技术方案概述

| 层 | 方案 |
|----|------|
| Python 运行时 | [python-build-standalone](https://github.com/indygreg/python-build-standalone) 预编译独立 Python |
| 打包工具 | Electron Builder + NSIS installer |
| 依赖安装 | 首次启动时用嵌入式 pip 安装到 `resources/backend/.venv/` |
| 数据目录 | `%APPDATA%/AgentCrewChat/`（与安装目录分离） |

### 1.2 目录结构

```
安装目录/
├── AgentCrewChat.exe          # Electron 主进程
├── resources/
│   ├── python/                # 嵌入式 Python 运行时
│   │   ├── python.exe
│   │   ├── Lib/
│   │   └── Scripts/
│   ├── backend/               # 后端代码 + 依赖
│   │   ├── src/
│   │   ├── pyproject.toml
│   │   └── .venv/             # 首次启动时创建
│   └── app/                   # 前端构建产物
│       └── dist/
```

```
%APPDATA%/AgentCrewChat/
├── config/                    # 用户配置
│   ├── manifest.json
│   ├── mcp/
│   ├── skills/
│   └── settings.json
├── data/
│   ├── checkpoints.sqlite
│   └── skills_install/
└── workspaces/                # 项目组工作区
```

### 1.3 修改 `python-manager.cjs`（Electron 侧）

现有 `python-manager.cjs` 已有后端进程管理框架，需扩展：

#### 1.3.1 嵌入式 Python 路径检测

```javascript
const embeddedPython = path.join(
  process.resourcesPath || path.join(__dirname, '..'),
  'resources', 'python', 'python.exe'
);
```

#### 1.3.2 首次启动依赖安装

```javascript
async function ensureVenv() {
  const venvDir = path.join(backendDir, '.venv');
  const venvPython = path.join(venvDir, 'Scripts', 'python.exe');

  if (fs.existsSync(venvPython)) return venvPython;

  // 创建 venv
  await execFileAsync(embeddedPython, ['-m', 'venv', venvDir]);

  // 安装依赖
  await execFileAsync(venvPython, [
    '-m', 'pip', 'install', '-r',
    path.join(backendDir, 'requirements.txt'),
    '--quiet',
  ]);

  return venvPython;
}
```

#### 1.3.3 数据目录

```javascript
const dataDir = path.join(
  process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
  'AgentCrewChat'
);
process.env.AGENTCREWCHAT_ROOT = dataDir;
```

### 1.4 Electron Builder 配置

在 `client/package.json` 或 `electron-builder.yml` 中：

```yaml
extraResources:
  - from: "../resources/python"
    to: "python"
  - from: "../resources/backend"
    to: "backend"
nsis:
  allowToChangeInstallationDirectory: true
  oneClick: false
```

### 1.5 数据目录初始化

后端 `bootstrap.py` 中已有的 `ensure_layout()` 负责创建 `config/`、`data/`、`workspaces/` 目录。启动时以 `AGENTCREWCHAT_ROOT` 环境变量为根目录。

### 1.6 测试清单

- [ ] 全新安装：选择安装目录 → 首次启动 → 自动创建 venv + 安装依赖 → 后端启动
- [ ] 卸载后重装：数据目录不被删除（`%APPDATA%/AgentCrewChat/`）
- [ ] 无网络环境：嵌入式 Python 独立运行
- [ ] 不同 Windows 用户：各用户独立数据目录

---

## 2. F-16：Skills 启用/禁用开关 UI

### 2.1 后端 — 新增启用/禁用端点

在 `api/routes/config.py` 中新增：

```python
@router.patch("/skills/{skill_id}")
async def toggle_skill(skill_id: str, body: dict) -> SkillEntry:
    """切换 Skill 启用/禁用状态。"""
    from agentcrewchat.config.loader import load_all, save_skill_entry

    cfg = load_all()
    entry = next((s for s in cfg.skills if s.id == skill_id), None)
    if entry is None:
        raise HTTPException(404, f"Skill not found: {skill_id}")

    enabled = body.get("enabled", not entry.enabled)
    updated = entry.model_copy(update={"enabled": enabled})
    save_skill_entry(updated)
    return updated
```

### 2.2 前端 — `api.ts`

```typescript
export const skillsApi = {
  // ... existing methods
  toggle: (id: string, enabled: boolean) =>
    request<SkillEntry>(`/config/skills/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),
};
```

### 2.3 前端 — `SkillsPage.tsx`

在每个 Skill 卡片中添加启用/禁用开关：

```tsx
<button
  onClick={() => {
    skillsApi.toggle(skill.id, !skill.enabled).then((updated) => {
      // 更新 store
      set((s) => ({
        skills: s.skills.map((sk) => sk.id === skill.id ? updated : sk),
      }));
    });
  }}
  className={`w-9 h-5 rounded-full transition-colors ${
    skill.enabled ? 'bg-status-success' : 'bg-text-disabled'
  }`}
>
  <span className={`block w-4 h-4 rounded-full bg-white shadow transition-transform ${
    skill.enabled ? 'translate-x-4' : 'translate-x-0.5'
  }`} />
</button>
```

### 2.4 store 更新

在 `configStore.ts` 中新增：

```typescript
toggleSkill: (id: string, enabled: boolean) => Promise<void>;
```

实现：

```typescript
toggleSkill: async (id, enabled) => {
  const updated = await skillsApi.toggle(id, enabled);
  set((s) => ({
    skills: s.skills.map((sk) => sk.id === id ? updated : sk),
  }));
},
```

---

## 3. G4：WS 断线续跑

### 3.1 问题

当前 WS 断线后 `_sessions.pop(session_id, None)` 直接删除 session，导致正在运行的 graph 丢失上下文。

### 3.2 方案（依赖 Batch 2 F-10 聊天持久化）

#### 3.2.1 `graph.py` — WS 断线处理

```python
except WebSocketDisconnect:
    session = _sessions.get(session_id)
    if session:
        session["ws_connected"] = False
        session["ws"] = None
    # 不删除 session！graph 继续在后台执行
```

#### 3.2.2 WS 推送容错

在 `_pump_graph_to_ws` 中，向 WS 发送时捕获异常：

```python
while True:
    item = await asyncio.to_thread(q.get)
    if item is _SENTINEL:
        break
    try:
        await websocket.send_json(item)
    except Exception:
        # WS 已断开，事件已由 event_bus 持久化，跳过推送
        pass
```

在 `graph.py` 的 `_run_pipeline_after_confirm` 中所有直接 `send_json` 调用同理加 try/except。

#### 3.2.3 重连恢复

前端重连 WS 时（同一 session_id），后端检测到已有 session：

```python
if action == "reconnect":
    session = _sessions.get(session_id)
    if session:
        session["ws"] = websocket
        session["ws_connected"] = True
        # 前端通过 REST /chat-history 拉取断线期间事件
        await websocket.send_json({
            "type": "phase_start",
            "timestamp": _ts(),
            "phase": session.get("current_phase", "unknown"),
            "content": "已重新连接，断线期间的事件请通过历史 API 获取",
        })
```

#### 3.2.4 前端 — 重连逻辑

在 `websocket.ts` 中，`onclose` 时自动重连（最多 3 次，间隔递增）：

```typescript
ws.onclose = () => {
  if (this.ws === ws) {
    this.ws = null;
    this._reconnect(sessionId, options, retryCount + 1);
  }
};
```

`_reconnect` 方法：
- 等待 `2^retryCount` 秒后重连
- 重连成功后发送 `{ action: "reconnect", session_id }`
- 然后调用 `tasksApi.getChatHistory(taskId)` 拉取断线期间事件
- 与本地 `events` 做差集补发到 `addEvent`

---

## 4. 最终集成检查清单

### 4.1 端到端流程

- [ ] 新建项目组 → 晓柔需求对话 → 确认 → 明哲出蓝图 → HITL 确认 → 多个执行 Agent 执行（各有中文名/性格/主题色）→ 铁口逐任务审核 → 超限后用户选择 → 汇总
- [ ] WS 断线重连 → 历史事件补发 → 继续操作
- [ ] 暂停 → 继续 → 从断点恢复
- [ ] 四阶段 LLM 分配 → 各阶段使用指定模型连接

### 4.2 前端自检

- [ ] 无新裸色值（无 `#hex` 硬编码）
- [ ] 新面板走 glass 风格
- [ ] 未破坏标题栏拖拽区
- [ ] `@名称` 渲染使用对应 Agent 主题色
- [ ] 聊天气泡中无裸 JSON
- [ ] 快捷回复按钮在超限时正确显示/隐藏

### 4.3 后端自检

- [ ] 暂停/继续不阻塞其他 session
- [ ] 决策等待有超时（默认 10 分钟），超时后自动 skip
- [ ] 事件持久化不阻塞 WS 推送
- [ ] 日志不含敏感信息（API Key、路径）

---

## 5. 文件改动汇总

| 文件 | 操作 | 哪一节 |
|------|------|--------|
| `client/electron/python-manager.cjs` | 修改 | 1.3 |
| `client/package.json` / `electron-builder.yml` | 修改 | 1.4 |
| `src/agentcrewchat/api/routes/config.py` | 修改 | 2.1 |
| `src/agentcrewchat/api/routes/graph.py` | 修改 | 3.2.1, 3.2.2, 3.2.3 |
| `client/src/components/config/SkillsPage.tsx` | 修改 | 2.3 |
| `client/src/stores/configStore.ts` | 修改 | 2.4 |
| `client/src/services/api.ts` | 修改 | 2.2 |
| `client/src/services/websocket.ts` | 修改 | 3.2.4 |

---

## 6. Batch 依赖关系

```
Batch 1 (已完成) ──→ Batch 2 ──→ Batch 3 ──→ Batch 4
  F-03, F-07       F-08,F-09    F-12,F-13     F-15,F-16
  G1, G5           F-10,F-11    F-14,G2,G3    G4
```

每个 Batch 完成后应可独立演示该阶段的增量功能。
