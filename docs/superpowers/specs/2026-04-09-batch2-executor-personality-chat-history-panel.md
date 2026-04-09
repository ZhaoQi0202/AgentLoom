# Batch 2 设计规格：执行 Agent 个性 + @主题色渲染 + 聊天持久化 + 右侧面板

> **日期**：2026-04-09
> **范围**：F-08、F-09、F-10、F-11
> **前置**：Batch 1（Agent 身份系统、四阶段 LLM 分配、工具注册对齐）

---

## 1. F-08：执行 Agent 个性池

### 1.1 新增 `src/agentcrewchat/graph/executor_identity.py`

集中管理执行 Agent 的随机命名和性格分配。

```python
"""执行 Agent 身份管理：随机中文名 + 性格池 + 主题色分配。"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

# ── 名字池 ──
_FIRST_CHARS = "见瑶辰榆澜悦诗沐云晴芯羽霁霜霓岚"
_second_chars = "杰灵巧锋凯帆宇宁萱琪铭颖晨萱"


def generate_executor_name(task_id: str, used: set[str]) -> str:
    """从 task_id 哈希生成随机两字中文名，格式「小X」，不与 used 重复。"""
    seed = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    for _ in range(200):
        first = rng.choice(_FIRST_CHARS)
        candidate = f"小{first}"
        if candidate not in used:
            return candidate
    # 兜底：加数字后缀
    for n in range(2, 100):
        first = rng.choice(_FIRST_CHARS)
        candidate = f"小{first}{n}"
        if candidate not in used:
            return candidate
    return f"小{task_id[:3]}"


# ── 性格池 ──
PERSONALITY_POOL = [
    "急性子", "碎嘴子", "自信派", "谨慎派",
    "乐观派", "毒舌徒弟", "学院派", "佛系",
]

PERSONALITY_PROMPTS: dict[str, str] = {
    "急性子":  "你说话简洁直接，不废话，给结果。",
    "碎嘴子":  "你喜欢解释你的操作过程，说话稍啰嗦但认真负责。",
    "自信派":  "你语气笃定，偶尔自夸一下，但活确实干得漂亮。",
    "谨慎派":  "你经常确认步骤，会标注不确定的地方，做事稳。",
    "乐观派":  "你说话积极向上，喜欢加油打气，遇到问题也不慌。",
    "毒舌徒弟": "你受审核员铁口的影响，偶尔嘴硬但执行力很强。",
    "学院派":  "你喜欢引用方法论，说话偏正式规范。",
    "佛系":    "你什么都说「好的没问题」，但做事很靠谱。",
}


def pick_personality(task_id: str) -> str:
    """根据 task_id 确定性选性格。"""
    idx = int(hashlib.sha256(task_id.encode()).hexdigest(), 16) % len(PERSONALITY_POOL)
    return PERSONALITY_POOL[idx]


# ── 主题色 ──
EXECUTOR_COLOR_PALETTE = [
    "#0891b2", "#16a34a", "#db2777", "#4f46e5",
    "#a16207", "#f97316", "#059669", "#e11d48",
    "#2563eb", "#d97706", "#8b5cf6", "#0284c7",
    "#65a30d", "#475569", "#9f1239",
]

# 不与固定 Agent 主题色重复
_FIXED_COLORS = {"#7c3aed", "#2563eb", "#ea580c"}


def pick_executor_color(task_id: str, used_colors: set[str]) -> str:
    """为执行 Agent 分配主题色。优先从色板取，超 15 个随机 HSL。"""
    available = [c for c in EXECUTOR_COLOR_PALETTE if c not in _FIXED_COLORS and c not in used_colors]
    if available:
        seed = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        return rng.choice(available)
    # 超出 15 色，随机 HSL
    seed = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    h = rng.randint(0, 360)
    # 检查色相距已分配色至少 30°
    for _ in range(100):
        too_close = False
        for uc in used_colors:
            # 粗略比较：将 hex 转 HSL 比色相
            existing_h = _hex_to_hue(uc)
            if existing_h is not None and abs((h - existing_h) % 360) < 30:
                too_close = True
                break
        if not too_close:
            break
        h = rng.randint(0, 360)
    s = rng.randint(60, 80)
    l = rng.randint(40, 55)
    return f"hsl({h}, {s}%, {l}%)"


def _hex_to_hue(hex_color: str) -> float | None:
    """简易 hex → hue 转换，用于色相距离计算。"""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == mn:
            return 0.0
        d = mx - mn
        if mx == r:
            h_deg = 60 * ((g - b) / d % 6)
        elif mx == g:
            h_deg = 60 * ((b - r) / d + 2)
        else:
            h_deg = 60 * ((r - g) / d + 4)
        return h_deg % 360
    except Exception:
        return None


@dataclass
class ExecutorIdentity:
    name: str
    personality: str
    personality_prompt: str
    color: str


def create_executor_identity(
    task_id: str,
    used_names: set[str],
    used_colors: set[str],
) -> ExecutorIdentity:
    """为单个执行任务创建完整身份。"""
    name = generate_executor_name(task_id, used_names)
    used_names.add(name)
    personality = pick_personality(task_id)
    personality_prompt = PERSONALITY_PROMPTS[personality]
    color = pick_executor_color(task_id, used_colors)
    used_colors.add(color)
    return ExecutorIdentity(
        name=name,
        personality=personality,
        personality_prompt=personality_prompt,
        color=color,
    )
```

### 1.2 修改 `react_agent.py`

在 `run_react_agent()` 内部：

1. 接收可选参数 `executor_identity: str | None`（显示名）和 `executor_color: str | None`
2. 系统提示词注入性格：在 `system_prompt` 末尾追加 `executor_identity_prompt`（如有）
3. `emit_event` 调用中使用 executor 的 name/color 而非 "experts" 默认值

```python
def run_react_agent(
    task_id: str,
    task_name: str,
    task_goal: str,
    acceptance_criteria: list[str],
    tools: list[BaseTool],
    workspace_path: str,
    thread_id: str = "",
    max_iterations: int = MAX_ITERATIONS,
    retry_feedback: str | None = None,
    executor_name: str = "",
    executor_color: str = "",
    executor_personality_prompt: str = "",
) -> dict[str, Any]:
```

- system_prompt 末尾追加：`if executor_personality_prompt: system_prompt += f"\n\n## 你的性格\n{executor_personality_prompt}"`
- 所有 `emit_event` 的 `agent_name` 使用 `executor_name or task_name`，`agent_color` 使用 `executor_color`
- 事件 dict 中新增 `"agent_name"` 和 `"agent_color"` 字段

### 1.3 修改 `orchestrator.py`

在 `run_orchestration` 中：

1. 导入 `create_executor_identity` 和 `executor_identity` 模块
2. 维护 `used_names: set[str]` 和 `used_colors: set[str]`
3. 每个任务创建前调用 `create_executor_identity(task_id, used_names, used_colors)`
4. 将 identity 信息传递给 `run_react_agent()`
5. `emit_event` 中 `agent` 字段仍为 "experts"，但 `agent_name` 使用 executor 的中文名

```python
from agentcrewchat.graph.executor_identity import create_executor_identity

# 在 run_orchestration 内，for task in layer: 之前：
used_names: set[str] = set()
used_colors: set[str] = set()

# 每个任务：
identity = create_executor_identity(task_id, used_names, used_colors)
# ...
result = run_react_agent(
    ...,
    executor_name=identity.name,
    executor_color=identity.color,
    executor_personality_prompt=identity.personality_prompt,
)
```

### 1.4 修改 `agent_identity.py`

`get_agent_display()` 对未知 agent_id 的 fallback 改为使用前端默认值，后端不再为 "experts" 硬编码名称（动态名称由 WS 事件携带）。

### 1.5 WS 事件扩展

执行 Agent 事件载荷中 `agent_name` 和 `agent_color` 由 `emit_event` 自动注入（Batch 1 已实现自动 enrichment），但 `orchestrator.py` 需要在 `emit_event` 时显式传入动态值以覆盖静态 lookup：

```python
emit_event(thread_id, {
    "type": "agent_output",
    "timestamp": _ts(),
    "phase": "experts",
    "agent": "experts",
    "agent_name": identity.name,      # 动态执行 Agent 名
    "agent_color": identity.color,     # 动态主题色
    "content": "...",
    "metadata": {"agent_name": identity.name, "task_id": task_id},
})
```

### 1.6 前端 `AgentMessage.tsx`（无需额外修改）

Batch 1 中已实现 `event.agent_name || meta?.label` 的优先级逻辑。动态执行 Agent 的 name/color 通过 WS 事件 `agent_name`/`agent_color` 字段传入，会自动显示。

---

## 2. F-09：`@名称` 主题色渲染

### 2.1 后端修改 — `graph.py` 移交消息

在 `_run_pipeline_after_confirm()` 中，将 `@架构设计师` 改为 `@明哲`，已在 Batch 1 中完成。

在 `orchestrator.py` 中，依赖提及消息 `@{task_name}` 需改为 `@{executor_name}`：

```python
# orchestrator.py
if deps:
    dep_names = [completed_tasks[d]["executor_name"] for d in deps if d in completed_tasks]
    if dep_names:
        mentions = "、".join(f"@{n}" for n in dep_names)
        emit_event(thread_id, {
            ...
            "content": f"{mentions} 的产出我看到了，接下来轮到我「{task_name}」了！",
            "metadata": {"agent_name": identity.name, "task_id": task_id},
        })
```

需要在 `completed_tasks` dict 中存储 `executor_name` 字段。

### 2.2 前端 — `AgentMessage.tsx` 新增 `@名称` 解析渲染

在消息气泡渲染 `ReactMarkdown` 之前，添加 `@名称` 解析逻辑：

```tsx
// 在 AgentMessage.tsx 中
import { AGENT_META } from "../../types";
import type { AgentId } from "../../types";

function renderAtMentions(content: string, events: ChatEvent[]): React.ReactNode {
  // 收集已知 Agent 名列表
  const knownNames = new Set<string>();
  for (const meta of Object.values(AGENT_META)) {
    knownNames.add(meta.label);
  }
  // 从事件流中收集动态执行 Agent 名
  for (const e of events) {
    const name = e.agent_name;
    if (name) knownNames.add(name);
  }

  // 按名字长度降序排列，优先匹配长名
  const names = [...knownNames].sort((a, b) => b.length - a.length);
  if (names.length === 0) return content;

  const pattern = new RegExp(`@(${names.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g');
  const parts: (string | React.ReactNode)[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(content)) !== null) {
    if (match.index > lastIdx) {
      parts.push(content.slice(lastIdx, match.index));
    }
    const name = match[1];
    const color = getAgentColorByName(name);
    parts.push(
      <span key={match.index} style={{ color, fontWeight: 600 }}>@{name}</span>
    );
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < content.length) {
    parts.push(content.slice(lastIdx));
  }
  return parts.length > 0 ? parts : content;
}
```

### 2.3 修改 `AgentMessage.tsx` 组件

将 `ReactMarkdown` 的内容从 `event.content || ""` 改为先经过 `renderAtMentions` 处理。由于 ReactMarkdown 不支持 inline React 节点，改用自定义解析：

方案：在 `ReactMarkdown` **外层**做 `@名称` 替换 — 对 content 做 `split`，将 `@名称` 部分替换为带颜色的 `<span>`，其余部分仍交给 `ReactMarkdown`。

```tsx
// AgentMessage.tsx 中新增
import { useChatStore } from "../../stores/chatStore";

function AtMentionContent({ content }: { content: string }) {
  const events = useChatStore((s) => s.events);
  const allEvents = [...useChatStore((s) => s.pendingEvents), ...events];

  // 收集已知名称
  const nameColorMap = new Map<string, string>();
  for (const [_, meta] of Object.entries(AGENT_META)) {
    if (!nameColorMap.has(meta.label)) {
      nameColorMap.set(meta.label, meta.color);
    }
  }
  for (const e of allEvents) {
    if (e.agent_name && e.agent_color && !nameColorMap.has(e.agent_name)) {
      nameColorMap.set(e.agent_name, e.agent_color);
    }
  }

  const names = [...nameColorMap.keys()].sort((a, b) => b.length - a.length);
  if (names.length === 0) {
    return <ReactMarkdown>{content}</ReactMarkdown>;
  }

  // 用 @名称 分割内容，逐段处理
  const pattern = new RegExp(
    `@(${names.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
    'g'
  );
  const segments: { type: 'text' | 'mention'; value: string }[] = [];
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(content)) !== null) {
    if (m.index > lastIdx) {
      segments.push({ type: 'text', value: content.slice(lastIdx, m.index) });
    }
    segments.push({ type: 'mention', value: m[1] });
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < content.length) {
    segments.push({ type: 'text', value: content.slice(lastIdx) });
  }

  return (
    <>
      {segments.map((seg, i) =>
        seg.type === 'mention' ? (
          <span key={i} style={{ color: nameColorMap.get(seg.value) || '#16a34a', fontWeight: 600 }}>
            @{seg.value}
          </span>
        ) : (
          <ReactMarkdown key={i}>{seg.value}</ReactMarkdown>
        )
      )}
    </>
  );
}
```

然后在 `AgentMessage` 组件中将 `<ReactMarkdown>{event.content || ""}</ReactMarkdown>` 替换为 `<AtMentionContent content={event.content || ""} />`。

---

## 3. F-10：聊天历史持久化

### 3.1 后端 — 事件持久化

#### 3.1.1 修改 `event_bus.py`

新增 `emit_event` 中同步写入 `chat_history.json`：

```python
def _save_event_to_history(thread_id: str, event: dict) -> None:
    """将事件追加写入对应项目的 chat_history.json。"""
    try:
        from agentcrewchat.paths import workspaces_dir
        from pathlib import Path
        import json

        # thread_id → task_id 映射通过 _thread_tasks 维护
        task_id = _thread_tasks.get(thread_id)
        if not task_id:
            return
        history_path = workspaces_dir() / task_id / "chat_history.json"
        if not history_path.parent.exists():
            return

        with _lock:
            events = []
            if history_path.is_file():
                try:
                    events = json.loads(history_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    events = []
            events.append(event)
            history_path.write_text(
                json.dumps(events, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception:
        logger.error("保存聊天历史失败", exc_info=True)
```

在 `emit_event` 中，`q.put(event)` 之前调用 `_save_event_to_history(thread_id, event)`。

#### 3.1.2 thread_id → task_id 映射

在 `event_bus.py` 中新增：

```python
_thread_tasks: dict[str, str] = {}

def register_thread_task(thread_id: str, task_id: str) -> None:
    with _lock:
        _thread_tasks[thread_id] = task_id
```

在 `graph.py` 的 `_pump_graph_to_ws` 和 `_run_pipeline_after_confirm` 中，`register_queue` 之后调用 `register_thread_task(thread_id, task_id)`。

#### 3.1.3 WS 断线不清理 session

在 `graph.py` 的 `WebSocketDisconnect` handler 中，**不再** `_sessions.pop(session_id, None)`，改为保留 session 并标记 WS 断开：

```python
except WebSocketDisconnect:
    session = _sessions.get(session_id)
    if session:
        session["ws_connected"] = False
    # 不删除 session，后端继续执行
```

WS 重连时，检测到已有 session 则恢复（不重新创建 graph），通过 chat history API 补发事件。

### 3.2 后端 — 新增 REST 端点

在 `api/routes/tasks.py` 中新增：

```python
@router.get("/{task_id}/chat-history")
async def get_chat_history(task_id: str) -> list[dict]:
    from agentcrewchat.paths import workspaces_dir
    import json

    history_path = workspaces_dir() / task_id / "chat_history.json"
    if not history_path.is_file():
        return []
    try:
        return json.loads(history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
```

### 3.3 前端 — 拉取历史

#### 3.3.1 在 `api.ts` 中新增：

```typescript
export const tasksApi = {
  // ... existing methods
  getChatHistory: (taskId: string) =>
    request<ChatEvent[]>(`/tasks/${taskId}/chat-history`),
};
```

#### 3.3.2 修改 `chatStore.ts` — `startCollect`

在 `startCollect` 中，连接 WS 前先拉取历史事件：

```typescript
startCollect: async (taskId: string) => {
  // 拉取历史
  let historyEvents: ChatEvent[] = [];
  try {
    historyEvents = await tasksApi.getChatHistory(taskId);
  } catch { /* 忽略错误 */ }

  const sessionId = crypto.randomUUID();
  set({
    isCollecting: true,
    isConsultantThinking: false,
    isPaused: false,
    isRunning: false,
    isInterrupted: false,
    events: historyEvents, // 注入历史事件
    pendingEvents: [],
  });
  graphSocket.connect(sessionId, {
    initial: { action: "collect", task_id: taskId, message: "" },
    onEvent: (event) => get().addEvent(event),
  });
},
```

### 3.4 前端 — 差集补发

`addEvent` 中，对新收到的事件做去重（基于 `timestamp + type + content`）：

```typescript
addEvent: (event) => {
  // 去重：如果 events 中已有相同事件则跳过
  const isDuplicate = get().events.some(
    (e) => e.timestamp === event.timestamp &&
           e.type === event.type &&
           e.content === event.content
  );
  if (isDuplicate) return;
  // ... 原有逻辑
}
```

---

## 4. F-11：右侧四阶段分栏面板

### 4.1 重构 `RightPanel.tsx`

将现有的「工作流进度」时间线改为四阶段卡片布局。

#### 阶段定义

```typescript
const PHASE_PANELS = [
  { key: "consult", label: "需求收集", agentIds: ["consultant"] as AgentId[] },
  { key: "architect", label: "架构规划", agentIds: ["architect"] as AgentId[] },
  { key: "execute", label: "执行", agentIds: ["experts"] as AgentId[] },
  { key: "review", label: "审核", agentIds: ["reviewer"] as AgentId[] },
] as const;
```

#### 阶段状态推断

```typescript
function getPhaseStatus(
  phaseKey: string,
  events: ChatEvent[],
  currentPhase: string | null,
  isRunning: boolean,
  isCollecting: boolean,
): "pending" | "active" | "completed" | "error" {
  const hasPhaseEvent = events.some(
    (e) => e.phase === phaseKey && (e.type === "agent_output" || e.type === "agent_join")
  );
  const hasNextPhase = events.some(
    (e) => e.phase !== phaseKey && e.type === "agent_join"
      && _PHASE_ORDER.indexOf(e.phase || "") > _PHASE_ORDER.indexOf(phaseKey)
  );
  const hasError = events.some(
    (e) => e.phase === phaseKey && e.type === "error"
  );

  if (hasError) return "error";
  if (hasPhaseEvent && hasNextPhase) return "completed";
  if (hasPhaseEvent || currentPhase === phaseKey) return "active";
  return "pending";
}
```

#### 渲染结构

```tsx
<aside className="w-[260px] shrink-0 border-l border-border-subtle bg-bg-surface/50 flex flex-col overflow-y-auto">
  <div className="p-4">
    <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
      工作流进度
    </h3>
    <div className="space-y-3">
      {PHASE_PANELS.map((phase) => {
        const status = getPhaseStatus(phase.key, events, currentPhase, isRunning, isCollecting);
        return (
          <GlassCard key={phase.key} className={`p-3 ${status === 'active' ? 'ring-1 ring-brand-purple/30' : ''}`}>
            {/* 阶段标题 + 状态点 */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-primary">{phase.label}</span>
              <StatusDot status={status} />
            </div>
            {/* Agent 头像列表 */}
            <div className="flex items-center gap-2">
              {phase.agentIds.map((agentId) => {
                const meta = AGENT_META[agentId];
                return (
                  <div key={agentId} className="flex items-center gap-1.5">
                    <AgentAvatar agentId={agentId} size={24} />
                    <span className="text-[11px]" style={{ color: meta.nameColor }}>
                      {meta.label}
                    </span>
                  </div>
                );
              })}
              {/* 动态执行 Agent（执行阶段） */}
              {phase.key === "execute" && dynamicAgents.map((agent) => (
                <div key={agent.taskId} className="flex items-center gap-1.5">
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-bold"
                    style={{ backgroundColor: agent.color }}
                  >
                    {agent.name[0]}
                  </div>
                  <span className="text-[11px]" style={{ color: agent.color }}>
                    {agent.name}
                  </span>
                </div>
              ))}
            </div>
          </GlassCard>
        );
      })}
    </div>
  </div>
  {/* 任务信息（保留） */}
  ...
</aside>
```

#### StatusDot 组件

```tsx
function StatusDot({ status }: { status: "pending" | "active" | "completed" | "error" }) {
  const colors = {
    pending: "bg-text-disabled",
    active: "bg-status-warning animate-pulse-glow",
    completed: "bg-status-success",
    error: "bg-status-error",
  };
  return <span className={`w-2 h-2 rounded-full shrink-0 ${colors[status]}`} />;
}
```

#### 动态执行 Agent 提取

从事件流中提取动态执行 Agent，包含 `name`、`color`、`status`：

```typescript
const dynamicAgents: { name: string; color: string; taskId: string; status: string }[] = [];
const seenDynamic = new Set<string>();
for (const e of events) {
  const agentName = (e.agent_name || e.metadata?.agent_name) as string | undefined;
  const agentColor = (e.agent_color) as string | undefined;
  const taskId = e.metadata?.task_id as string | undefined;
  if (agentName && taskId && !seenDynamic.has(taskId)) {
    seenDynamic.add(taskId);
    dynamicAgents.push({
      name: agentName,
      color: agentColor || "#0891b2",
      taskId,
      status: "running",
    });
  }
}
for (const e of events) {
  const taskId = e.metadata?.task_id as string | undefined;
  if (taskId && e.content?.includes("执行完毕")) {
    const agent = dynamicAgents.find((a) => a.taskId === taskId);
    if (agent) agent.status = e.content.includes("✅") ? "completed" : "error";
  }
}
```

---

## 5. 文件改动汇总

| 文件 | 操作 | Batch 2 哪一节 |
|------|------|----------------|
| `src/agentcrewchat/graph/executor_identity.py` | 新增 | 1.1 |
| `src/agentcrewchat/graph/nodes/react_agent.py` | 修改 | 1.2 |
| `src/agentcrewchat/graph/orchestrator.py` | 修改 | 1.3, 2.1 |
| `src/agentcrewchat/graph/event_bus.py` | 修改 | 3.1 |
| `src/agentcrewchat/api/routes/graph.py` | 修改 | 3.1.3 |
| `src/agentcrewchat/api/routes/tasks.py` | 修改 | 3.2 |
| `client/src/components/layout/RightPanel.tsx` | 重构 | 4.1 |
| `client/src/components/chat/AgentMessage.tsx` | 修改 | 2.2-2.3 |
| `client/src/stores/chatStore.ts` | 修改 | 3.3.2, 3.4 |
| `client/src/services/api.ts` | 修改 | 3.3.1 |

---

## 6. 不涉及的内容

以下内容属于后续 Batch，本次不做：
- 暂停/审核超限/重规划（Batch 3）
- 安装包打包（Batch 4）
