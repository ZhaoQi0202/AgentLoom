# Batch 1 设计规格：Agent 身份系统 + LLM 四阶段分配 + 工具注册对齐

> **日期**：2026-04-09
> **范围**：F-07 + G5、F-03、G1
> **前置**：无（Batch 1 是基础层，无外部依赖）

---

## 1. F-07 + G5：Agent 身份系统落地

### 1.1 新增 `src/agentcrewchat/graph/agent_identity.py`

集中管理 Agent 身份信息的注册表模块。

```python
FIXED_AGENTS: dict[str, dict] = {
    "consultant": {"name": "晓柔", "role": "需求分析师", "color": "#7c3aed"},
    "architect":  {"name": "明哲", "role": "架构师",     "color": "#2563eb"},
    "reviewer":   {"name": "铁口", "role": "审核员",     "color": "#ea580c"},
}
```

提供 `get_agent_display(agent_id: str) -> dict` 函数，返回 `{name, role, color}`，未知 ID 返回 `{"name": agent_id, "role": "执行者", "color": "#0891b2"}`。

### 1.2 更新固定 Agent 系统提示词

| 文件 | 改动 |
|------|------|
| `consultant_agent.py` | 提示词开头改为「你是晓柔，一位温和耐心的需求分析师…」 |
| `architect_agent.py` | 改为「你是明哲，一位严谨理性的架构师…」 |
| `reviewer_agent.py` | 改为「你是铁口，一位毒舌挑剔但细致的审核员…」 |

名字和性格方向严格按 `product.md` 5.1 节。

### 1.3 WS 事件载荷扩展

所有 `agent_join` 和 `agent_output` 事件新增可选字段：

```json
{
  "agent_name": "晓柔",
  "agent_color": "#7c3aed"
}
```

改动位置：
- `graph.py` → `_iter_graph_events()` 中构造事件 dict 时，从 `agent_identity.FIXED_AGENTS` 查表注入
- `graph.py` → `_run_pipeline_after_confirm()` 中所有 `send_json` 调用同理
- `orchestrator.py` → `emit_event()` 调用处同理

### 1.4 移交消息更新

`graph.py` 第 143 行 `@架构设计师` → `@明哲`，所有移交消息中角色名统一用中文名。

### 1.5 前端 AGENT_META 更新

`client/src/types/index.ts`：

```typescript
export interface AgentMeta {
  label: string;
  role: string;
  color: string;  // 新增
}

export const AGENT_META: Record<AgentId, AgentMeta> = {
  consultant:     { label: "晓柔", role: "需求分析师", color: "#7c3aed" },
  architect:      { label: "明哲", role: "架构师",     color: "#2563eb" },
  hitl_blueprint: { label: "明哲", role: "架构师",     color: "#2563eb" },
  experts:        { label: "执行者", role: "执行",     color: "#0891b2" },
  reviewer:       { label: "铁口", role: "审核员",     color: "#ea580c" },
};
```

### 1.6 消息气泡名称与颜色渲染

`AgentMessage.tsx` 中：
- 名称显示：`event.agent_name || AGENT_META[event.agent]?.label`
- 颜色显示：`event.agent_color || AGENT_META[event.agent]?.color`

优先使用 WS 事件中的动态值（为后续 Batch 2 动态执行 Agent 做准备），回退到静态表。

---

## 2. F-03：按四阶段分配 LLM

### 2.1 扩展 `config/models.py`

```python
class PhaseModelConnections(BaseModel):
    model_config = ConfigDict(extra="ignore")
    collect: str | None = None
    architect: str | None = None
    execute: str | None = None
    review: str | None = None

class LlmSettings(BaseModel):
    # ... 现有字段不变
    phase_model_connections: PhaseModelConnections = PhaseModelConnections()
```

每个阶段值为 connection_id 字符串，`None` 表示跟随默认连接。

### 2.2 修改 `llm/factory.py`

`get_chat_model()` 新增 `phase` 参数：

```python
def get_chat_model(
    provider: str | None = None,
    *,
    install_root: Path | None = None,
    connection_id: str | None = None,
    phase: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    s = load_llm_settings(install_root)
    cfg_root = _config_root(install_root)

    # 优先级：显式 connection_id > phase 配置 > 默认连接
    cid = connection_id
    if not cid and phase:
        phase_conns = s.phase_model_connections
        cid = getattr(phase_conns, phase, None)
    if not cid:
        cid = s.default_model_connection_id or ""
    cid = cid.strip()
    # ... 后续逻辑不变
```

### 2.3 更新 Agent 节点调用

| 文件 | 改动 |
|------|------|
| `consultant_agent.py` | `get_chat_model(phase="collect")` |
| `architect_agent.py` | `get_chat_model(phase="architect")` |
| `react_agent.py` | `get_chat_model(phase="execute")` |
| `reviewer_agent.py` | `get_chat_model(phase="review")` |

### 2.4 REST API

无需新增端点。现有 `/api/llm-settings` GET/PUT 已是通用 dict 序列化，`phase_model_connections` 随 `settings.json` 自动读写。

### 2.5 前端类型扩展

`client/src/types/index.ts`：

```typescript
interface PhaseModelConnections {
  collect?: string;
  architect?: string;
  execute?: string;
  review?: string;
}

interface LlmSettings {
  // ... 现有字段
  phase_model_connections?: PhaseModelConnections;
}
```

### 2.6 SettingsPage UI

在现有设置项下方新增 GlassCard「阶段模型分配」区域，4 行下拉框：

| 行 | 标签 | 字段 |
|----|------|------|
| 1 | 需求收集 | `phase_model_connections.collect` |
| 2 | 架构规划 | `phase_model_connections.architect` |
| 3 | 执行 | `phase_model_connections.execute` |
| 4 | 审核 | `phase_model_connections.review` |

- 下拉选项来自 `configStore` 中已配置的 model connections
- 默认选项「跟随默认」（值为空字符串）
- 选择后调用 `updateLlmSettings()` 保存

---

## 3. G1：蓝图工具 ID 与执行对齐

### 3.1 扩展 `tool_registry.py`

```python
def create_tools_for_task(
    tool_ids: list[str],
    workspace: Path,
    *,
    install_root: Path | None = None,
    task_id: str | None = None,
) -> list[BaseTool]:
    tools = []
    for tid in tool_ids:
        if tid in _BUILTIN_TOOL_FACTORIES:
            tools.append(_BUILTIN_TOOL_FACTORIES[tid](workspace))
        elif tid.startswith("mcp:"):
            tools.extend(_load_mcp_tools(tid[4:], install_root))
        elif tid.startswith("skill:"):
            tools.extend(_load_skill_tools(tid[6:], install_root, task_id))
        else:
            logger.warning("Unknown tool ID in blueprint: %s", tid)
    return tools
```

### 3.2 新增内部加载函数

- `_load_mcp_tools(mcp_id, install_root)` — 从 `config/mcp/<mcp_id>.json` 读取 MCP 配置，实例化工具列表
- `_load_skill_tools(skill_id, install_root, task_id)` — 从 Skills 注册表查找（先项目级再全局级），加载工具

两个函数内部捕获异常，加载失败时 `logger.error` 并返回空列表，不中断执行。

### 3.3 架构师提示词约束

`architect_agent.py` 系统提示词中新增可用工具格式说明：

```
可用工具类型及 ID 格式：
- shell — 执行 shell 命令
- python — 执行 Python 脚本
- mcp:<mcp_id> — MCP 工具（如 mcp:filesystem）
- skill:<skill_id> — Skills 工具（如 skill:find-skills）
```

### 3.4 向下兼容

- 现有蓝图中只写 `shell` / `python` 的继续正常工作
- 未知 ID 从静默忽略改为 `logger.warning`

---

## 4. 不涉及的内容

以下内容属于后续 Batch，本次不做：
- 执行 Agent 随机中文名和性格池（Batch 2：F-08）
- `@名称` 主题色渲染（Batch 2：F-09）
- 聊天历史持久化（Batch 2：F-10）
- 右侧四阶段面板（Batch 2：F-11）
- 暂停/审核超限/重规划（Batch 3）
- 安装包打包（Batch 4）
