# AgentLoom 群聊体验重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AgentLoom 从任务执行工具转变为群聊协作体验，包含浅色主题、中文 Agent 命名、打字动画、三态控制按钮和需求收集多轮对话。

**Architecture:** 前端 React + Zustand 状态管理改造 UI/UX；后端 FastAPI WebSocket 新增需求收集对话流程和暂停/继续机制；LangGraph 图谱执行流程保持不变，仅调整 prompt 和事件格式。

**Tech Stack:** React 19, TypeScript 5.9, Zustand 5, Tailwind CSS 4.2, FastAPI, LangGraph, WebSocket

---

## 文件结构总览

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `client/src/types/index.ts` | Agent 中文 label、nameColor 适配浅色 |
| Modify | `client/src/styles/globals.css` | 浅色毛玻璃主题 + 打字动画 keyframes |
| Modify | `client/src/components/layout/TaskList.tsx` | "新建项目组"文案 |
| Modify | `client/src/components/chat/ChatArea.tsx` | 加入群聊提示、三态按钮、打字动画气泡、空状态文案 |
| Modify | `client/src/components/chat/ChatInput.tsx` | 需求收集阶段启用输入 |
| Modify | `client/src/components/chat/AgentMessage.tsx` | 适配浅色主题样式 |
| Modify | `client/src/components/chat/SystemMessage.tsx` | "加入群聊"药丸样式 |
| Modify | `client/src/stores/chatStore.ts` | isPaused 状态、pauseGraph、需求收集模式 |
| Modify | `client/src/services/websocket.ts` | pause action 支持 |
| Modify | `src/agentloom/api/routes/graph.py` | agent_thinking 事件、暂停处理、需求收集 WS 流程 |
| Modify | `src/agentloom/graph/nodes/stubs.py` | Agent prompt 字数限制 + 群聊风格 |

---

### Task 1: Agent 中文名称

**Files:**
- Modify: `client/src/types/index.ts:84-115`

- [ ] **Step 1: 修改 AGENT_META 的 label 和 nameColor**

打开 `client/src/types/index.ts`，将 `AGENT_META` 对象替换为：

```typescript
export const AGENT_META: Record<AgentId, AgentMeta> = {
  consultant: {
    label: "需求分析师",
    emoji: "\u{1F50D}",
    gradient: ["#8b5cf6", "#6366f1"],
    nameColor: "#7c3aed",
  },
  architect: {
    label: "架构设计师",
    emoji: "\u{1F4D0}",
    gradient: ["#3b82f6", "#06b6d4"],
    nameColor: "#2563eb",
  },
  hitl_blueprint: {
    label: "方案审核员",
    emoji: "\u23F8",
    gradient: ["#f59e0b", "#f97316"],
    nameColor: "#d97706",
  },
  experts: {
    label: "执行专家组",
    emoji: "\u26A1",
    gradient: ["#22c55e", "#10b981"],
    nameColor: "#16a34a",
  },
  reviewer: {
    label: "质量审查员",
    emoji: "\u{1F50E}",
    gradient: ["#ec4899", "#f43f5e"],
    nameColor: "#db2777",
  },
};
```

注意：`nameColor` 从浅色（适配暗色背景）改为深色（适配浅色背景）。

- [ ] **Step 2: 验证前端编译通过**

Run: `cd client && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 3: Commit**

```bash
git add client/src/types/index.ts
git commit -m "feat: rename agents to Chinese professional titles"
```

---

### Task 2: 浅色毛玻璃主题

**Files:**
- Modify: `client/src/styles/globals.css`

- [ ] **Step 1: 替换 CSS 变量为浅色值**

打开 `client/src/styles/globals.css`，将 `@theme` 块（行 3-30）替换为：

```css
@theme {
  --color-bg-base: #f8f9fc;
  --color-bg-surface: #f0f2f8;
  --color-bg-elevated: rgba(255, 255, 255, 0.7);
  --color-bg-hover: rgba(139, 92, 246, 0.06);

  --color-border-subtle: rgba(139, 92, 246, 0.06);
  --color-border-default: rgba(139, 92, 246, 0.10);
  --color-border-strong: rgba(139, 92, 246, 0.15);

  --color-text-primary: #1e293b;
  --color-text-body: #334155;
  --color-text-secondary: #64748b;
  --color-text-muted: #94a3b8;
  --color-text-disabled: #cbd5e1;

  --color-brand-purple: #8b5cf6;
  --color-brand-blue: #3b82f6;

  --color-status-success: #22c55e;
  --color-status-warning: #f59e0b;
  --color-status-error: #ef4444;
  --color-status-info: #3b82f6;

  --radius-card: 12px;
  --radius-sm: 8px;
  --radius-lg: 14px;
}
```

- [ ] **Step 2: 更新 body 和滚动条样式**

将 `body` 样式块（行 38-46）更新为：

```css
body {
  margin: 0;
  background: linear-gradient(180deg, #f8f9fc 0%, #f0f2f8 100%);
  color: var(--color-text-primary);
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", system-ui,
    -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow: hidden;
}
```

将滚动条样式（行 49-58）更新为：

```css
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(139, 92, 246, 0.12);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(139, 92, 246, 0.22);
}
```

- [ ] **Step 3: 更新玻璃态样式**

将 `.glass` 和 `.glass-hover` 样式（行 62-68）更新为：

```css
.glass {
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-card);
  backdrop-filter: blur(12px);
  box-shadow: 0 1px 3px rgba(139, 92, 246, 0.04);
}

.glass-hover {
  transition: background 200ms, border-color 200ms, box-shadow 200ms;
}
.glass-hover:hover {
  background: rgba(255, 255, 255, 0.85);
  border-color: var(--color-border-default);
  box-shadow: 0 2px 8px rgba(139, 92, 246, 0.08);
}
```

- [ ] **Step 4: 添加打字动画 keyframes**

在文件末尾（`animate-pulse-glow` 后面）添加：

```css
/* ── 打字中动画 ─────────────────────────────────────── */

@keyframes typing-dot {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  40% {
    opacity: 1;
    transform: scale(1);
  }
}

.typing-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-muted);
  animation: typing-dot 1.4s ease-in-out infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}
```

- [ ] **Step 5: 启动开发服务器，目视验证浅色主题效果**

Run: `cd client && npm run dev`

打开浏览器确认：
- 背景为浅色渐变
- 玻璃态元素可见
- 文字清晰可读
- 品牌紫蓝渐变保留

- [ ] **Step 6: Commit**

```bash
git add client/src/styles/globals.css
git commit -m "feat: switch to light glassmorphism theme with typing animation CSS"
```

---

### Task 3: "新建任务" → "新建项目组"

**Files:**
- Modify: `client/src/components/layout/TaskList.tsx`
- Modify: `client/src/components/chat/ChatArea.tsx:26-33,80`

- [ ] **Step 1: 修改 TaskList 文案**

打开 `client/src/components/layout/TaskList.tsx`。

将搜索框 placeholder（行 26）从 `"搜索任务..."` 改为 `"搜索项目组..."`。

将新建按钮区域的标题文案从 `"新建任务"` 改为 `"新建项目组"`。

将输入框 placeholder（行 35）从 `"任务名称..."` 改为 `"项目组名称..."`。

将创建按钮文案从 `"创建"` 改为 `"创建"`（保持不变）。

- [ ] **Step 2: 修改 ChatArea 空状态文案**

打开 `client/src/components/chat/ChatArea.tsx`。

将未选择任务时的空状态文案（行 30-31）从：
```tsx
<p className="text-text-muted text-sm">选择一个任务开始对话</p>
<p className="text-text-disabled text-xs">或在左侧创建新任务</p>
```
改为：
```tsx
<p className="text-text-muted text-sm">选择一个项目组开始协作</p>
<p className="text-text-disabled text-xs">或在左侧创建新项目组</p>
```

将无事件时的提示（行 80）从 `"点击「运行图谱」启动任务"` 改为 `"新项目组已创建，等待启动..."`。

- [ ] **Step 3: 目视验证文案变更**

启动前端开发服务器，确认侧边栏按钮、输入框、空状态文案全部已更新。

- [ ] **Step 4: Commit**

```bash
git add client/src/components/layout/TaskList.tsx client/src/components/chat/ChatArea.tsx
git commit -m "feat: rename '新建任务' to '新建项目组' throughout UI"
```

---

### Task 4: "加入群聊" 系统消息

**Files:**
- Modify: `client/src/components/chat/SystemMessage.tsx`
- Modify: `src/agentloom/api/routes/graph.py:34-40`

- [ ] **Step 1: 读取当前 SystemMessage 组件**

先阅读 `client/src/components/chat/SystemMessage.tsx` 了解当前实现。

- [ ] **Step 2: 修改后端 phase_start 事件内容**

打开 `src/agentloom/api/routes/graph.py`。

定义 Agent 中文名映射（在 `_ts()` 函数后面添加）：

```python
_AGENT_LABELS: dict[str, str] = {
    "consultant": "需求分析师",
    "architect": "架构设计师",
    "hitl_blueprint": "方案审核员",
    "experts": "执行专家组",
    "reviewer": "质量审查员",
}
```

修改 `_iter_graph_events` 中的 `phase_start` 事件（行 34-40）：

将：
```python
yield {
    "type": "phase_start",
    "timestamp": _ts(),
    "phase": phase,
    "agent": node,
    "content": f"阶段: {node}",
}
```

改为：
```python
label = _AGENT_LABELS.get(node, node)
yield {
    "type": "phase_start",
    "timestamp": _ts(),
    "phase": phase,
    "agent": node,
    "content": f"{label} 加入群聊",
}
```

同时修改初始 "start" action 中的 phase_start 事件（行 113-118）：

将：
```python
await websocket.send_json({
    "type": "phase_start",
    "timestamp": _ts(),
    "phase": "pending",
    "content": "已收到任务，正在运行图谱…",
})
```

改为：
```python
await websocket.send_json({
    "type": "phase_start",
    "timestamp": _ts(),
    "phase": "pending",
    "content": "项目已启动，Agent 正在就位…",
})
```

- [ ] **Step 3: 修改 SystemMessage 组件为"加入群聊"药丸样式**

修改 `client/src/components/chat/SystemMessage.tsx`，使 `phase_start` 类型事件渲染为居中的浅色药丸标签：

```tsx
import type { ChatEvent } from "../../types";
import { AGENT_META } from "../../types";
import type { AgentId } from "../../types";

export function SystemMessage({ event }: { event: ChatEvent }) {
  const isJoin = event.type === "phase_start" && event.agent;
  const meta = event.agent ? AGENT_META[event.agent as AgentId] : null;

  if (isJoin && meta) {
    return (
      <div className="flex justify-center my-3">
        <span className="text-xs px-3 py-1 rounded-full bg-black/5 text-text-secondary">
          {meta.emoji} {meta.label} 加入群聊
        </span>
      </div>
    );
  }

  // 其他系统消息（task_complete, phase_complete 等）
  return (
    <div className="flex justify-center my-3">
      <span className="text-xs px-3 py-1 rounded-full bg-black/5 text-text-secondary">
        {event.content}
      </span>
    </div>
  );
}
```

- [ ] **Step 4: 目视验证**

启动前后端，运行一个任务，确认：
- 每个 agent 阶段开始时显示 "🔍 需求分析师 加入群聊" 样式的居中药丸
- 任务完成时显示 "任务完成" 药丸

- [ ] **Step 5: Commit**

```bash
git add src/agentloom/api/routes/graph.py client/src/components/chat/SystemMessage.tsx
git commit -m "feat: show '加入群聊' pill notification when agents join"
```

---

### Task 5: 打字中动画

**Files:**
- Modify: `src/agentloom/api/routes/graph.py:29-47`
- Modify: `client/src/components/chat/ChatArea.tsx:83-100`

- [ ] **Step 1: 后端在 LLM 调用前发送 agent_thinking 事件**

打开 `src/agentloom/api/routes/graph.py`。

修改 `_iter_graph_events` 函数，在每个节点的 `phase_start` 之后、`agent_output` 之前，插入 `agent_thinking` 事件：

将循环体（行 32-47）：
```python
for node, upd in parts:
    phase = upd.get("phase", node)
    label = _AGENT_LABELS.get(node, node)
    yield {
        "type": "phase_start",
        "timestamp": _ts(),
        "phase": phase,
        "agent": node,
        "content": f"{label} 加入群聊",
    }
    content = upd.get("message") or json.dumps(upd, ensure_ascii=False, default=str)
    yield {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": phase,
        "agent": node,
        "content": content,
    }
```

改为（注意：由于 stubs 是同步调用 LLM，graph.stream 只在节点完成后才 yield，所以 thinking 和 output 会紧挨着发出。要实现真正的"等待 LLM"效果，需要将 thinking 事件在节点执行**之前**发送。）

实际上，当前架构下 `graph.stream(stream_mode="updates")` 是在每个节点**完成后**才发出 chunk。要在节点执行前发 thinking，需要改为 `stream_mode="values"` 或在 `_pump_graph_to_ws` 中手动跟踪。

更好的方案：利用 `interrupt_before` 机制的模式。在 `_iter_graph_events` 开始循环之前，先获取 graph state 的 `next` 节点列表，发送 thinking 事件；然后在收到节点输出后发送 output。

改写 `_iter_graph_events` 为：

```python
def _iter_graph_events(graph: Any, input_obj: Any, cfg: dict) -> Iterator[dict[str, Any]]:
    # 在开始 stream 之前，预测即将执行的节点，发送 thinking
    try:
        st = graph.get_state(cfg)
        for nxt_node in (st.next or []):
            label = _AGENT_LABELS.get(nxt_node, nxt_node)
            yield {
                "type": "phase_start",
                "timestamp": _ts(),
                "phase": nxt_node,
                "agent": nxt_node,
                "content": f"{label} 加入群聊",
            }
            yield {
                "type": "agent_thinking",
                "timestamp": _ts(),
                "phase": nxt_node,
                "agent": nxt_node,
                "content": "",
            }
    except Exception:
        pass  # 首次 start 时无 state，跳过

    for chunk in graph.stream(input_obj, cfg, stream_mode="updates"):
        parts, has_interrupt = split_stream_chunk(chunk)
        for node, upd in parts:
            phase = upd.get("phase", node)
            content = upd.get("message") or json.dumps(upd, ensure_ascii=False, default=str)
            yield {
                "type": "agent_output",
                "timestamp": _ts(),
                "phase": phase,
                "agent": node,
                "content": content,
            }
            # 检查下一个即将执行的节点，提前发送 thinking
            try:
                st = graph.get_state(cfg)
                for nxt_node in (st.next or []):
                    if nxt_node == node:
                        continue
                    label = _AGENT_LABELS.get(nxt_node, nxt_node)
                    yield {
                        "type": "phase_start",
                        "timestamp": _ts(),
                        "phase": nxt_node,
                        "agent": nxt_node,
                        "content": f"{label} 加入群聊",
                    }
                    yield {
                        "type": "agent_thinking",
                        "timestamp": _ts(),
                        "phase": nxt_node,
                        "agent": nxt_node,
                        "content": "",
                    }
            except Exception:
                pass
        if has_interrupt:
            st = graph.get_state(cfg)
            nxt = st.next[0] if st.next else ""
            label = _AGENT_LABELS.get(nxt, nxt)
            interrupt_msg = f"{label} 等待人工审核"
            yield {
                "type": "hitl_interrupt",
                "timestamp": _ts(),
                "phase": nxt,
                "agent": nxt,
                "content": interrupt_msg,
            }
            return
    yield {
        "type": "task_complete",
        "timestamp": _ts(),
        "content": "项目执行完成",
    }
```

- [ ] **Step 2: 前端渲染 agent_thinking 为动画气泡**

打开 `client/src/components/chat/ChatArea.tsx`。

在 `events.map` 的 switch 中，将 `agent_thinking` 和 `agent_output` 分开处理。当遇到 `agent_thinking` 事件时，检查后续是否有同一 agent 的 `agent_output`，如果有则跳过 thinking（已被 output 替换）：

修改事件渲染逻辑（行 83-100）为：

```tsx
events.map((event, i) => {
  switch (event.type) {
    case "phase_start":
    case "phase_complete":
    case "task_complete":
      return <SystemMessage key={i} event={event} />;
    case "agent_thinking": {
      // 检查后续是否已有同一 agent 的 output，如有则不渲染 thinking
      const hasOutput = events.slice(i + 1).some(
        (e) => e.type === "agent_output" && e.agent === event.agent
      );
      if (hasOutput) return null;
      return <ThinkingBubble key={i} event={event} />;
    }
    case "agent_output":
      return <AgentMessage key={i} event={event} />;
    case "hitl_interrupt":
      return <HITLCard key={i} event={event} />;
    case "user_response":
      return <UserMessage key={i} event={event} />;
    case "error":
      return <ErrorCard key={i} event={event} />;
    default:
      return null;
  }
})
```

- [ ] **Step 3: 创建 ThinkingBubble 组件**

在 `ChatArea.tsx` 文件底部（`ErrorCard` 组件之后）添加 `ThinkingBubble`：

```tsx
function ThinkingBubble({ event }: { event: ChatEvent }) {
  const meta = event.agent ? AGENT_META[event.agent as AgentId] : null;
  if (!meta) return null;

  return (
    <div className="flex gap-3 px-5 py-2">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0"
        style={{ background: `linear-gradient(135deg, ${meta.gradient[0]}, ${meta.gradient[1]})` }}
      >
        {meta.emoji}
      </div>
      <div>
        <span className="text-xs font-semibold" style={{ color: meta.nameColor }}>
          {meta.label}
        </span>
        <div className="mt-1 px-3 py-2 rounded-[0_12px_12px_12px] glass">
          <div className="typing-dots">
            <span /><span /><span />
          </div>
        </div>
      </div>
    </div>
  );
}
```

在文件顶部 import 中添加：
```tsx
import { AGENT_META } from "../../types";
import type { AgentId, ChatEvent } from "../../types";
```

- [ ] **Step 4: 目视验证打字动画**

启动前后端，运行项目，确认：
- 每个 agent 节点执行前出现 "加入群聊" + 打字动画气泡
- LLM 返回后动画气泡消失，完整消息出现
- 动画有脉冲效果

- [ ] **Step 5: Commit**

```bash
git add src/agentloom/api/routes/graph.py client/src/components/chat/ChatArea.tsx
git commit -m "feat: add typing animation bubble while agent generates response"
```

---

### Task 6: Agent 回复限制 100-200 字符

**Files:**
- Modify: `src/agentloom/graph/nodes/stubs.py`

- [ ] **Step 1: 修改各 agent 的 system prompt**

打开 `src/agentloom/graph/nodes/stubs.py`。

修改 `consultant` 函数（行 22-42）的 system prompt：

```python
def consultant(state: AgentLoomState) -> dict[str, Any]:
    """需求分析师：分析用户需求，输出简短摘要。"""
    user_request = state.get("user_request", "未提供任务描述")

    system = (
        "你是需求分析师。在一个项目群聊中，你的职责是快速分析用户需求并给出简短总结。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格回复，不要使用 Markdown 标题格式\n"
        "- 直接说重点：需求概要、关键风险、明确度评估\n"
        "- 像在工作群里给同事发消息一样说话\n"
    )
    user = f"请分析这个需求：{user_request}"

    message = _call_llm(system, user)

    return {
        "phase": "consult",
        "consult_confidence": 0.9,
        "consult_summary": message,
        "message": message,
    }
```

修改 `architect` 函数（行 45-72）的 system prompt：

```python
def architect(state: AgentLoomState) -> dict[str, Any]:
    """架构设计师：基于需求分析设计技术方案。"""
    user_request = state.get("user_request", "")
    consult_summary = state.get("consult_summary", "")

    system = (
        "你是架构设计师。在一个项目群聊中，你的职责是给出简洁的技术方案。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格，不要使用 Markdown 标题格式\n"
        "- 直接说：技术选型 + 核心步骤（3-5步，每步一句话）\n"
        "- 像在工作群里给同事发消息一样说话\n"
    )
    user = f"需求：{user_request}\n分析：{consult_summary}\n请给出技术方案。"

    message = _call_llm(system, user)

    return {
        "phase": "architect",
        "blueprint": {"raw": message},
        "architect_gap_notes": "",
        "message": message,
    }
```

修改 `hitl_blueprint` 函数（行 75-83）：

```python
def hitl_blueprint(state: AgentLoomState) -> dict[str, Any]:
    """方案审核员：等待人工审核蓝图。"""
    return {
        "phase": "hitl_blueprint",
        "message": "方案已提交，请审核上面架构设计师的方案。确认无误回复「继续」，需要调整请说明修改意见。",
    }
```

修改 `experts` 函数（行 85-109）的 system prompt：

```python
def experts(state: AgentLoomState) -> dict[str, Any]:
    """执行专家组：根据蓝图执行任务。"""
    user_request = state.get("user_request", "")
    blueprint = state.get("blueprint", {})
    blueprint_text = blueprint.get("raw", "") if isinstance(blueprint, dict) else str(blueprint)

    system = (
        "你是执行专家组。在一个项目群聊中，你的职责是汇报执行进展。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格，不要使用 Markdown 标题格式\n"
        "- 直接说：做了什么、关键结果、有无问题\n"
        "- 像在工作群里给同事发进度汇报一样说话\n"
    )
    user = f"需求：{user_request}\n蓝图：{blueprint_text}\n请汇报执行结果。"

    message = _call_llm(system, user)

    return {
        "phase": "experts",
        "expert_runs": [{"swarm_output": message}],
        "message": message,
    }
```

修改 `reviewer` 函数（行 111-148）的 system prompt：

```python
def reviewer(state: AgentLoomState) -> dict[str, Any]:
    """质量审查员：审查执行结果。"""
    user_request = state.get("user_request", "")
    blueprint = state.get("blueprint", {})
    blueprint_text = blueprint.get("raw", "") if isinstance(blueprint, dict) else str(blueprint)
    expert_runs = state.get("expert_runs", [])
    expert_text = ""
    for run in expert_runs:
        if isinstance(run, dict):
            expert_text += run.get("swarm_output", str(run)) + "\n"

    r = int(state.get("review_round", 0))

    system = (
        "你是质量审查员。在一个项目群聊中，你的职责是快速给出审查结论。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格，不要使用 Markdown 标题格式\n"
        "- 直接说：审查结论（通过/需修改）、关键问题\n"
        "- 最后必须包含 PASS 或 NEEDS_REVISION\n"
        "- 像在工作群里给同事发审查意见一样说话\n"
    )
    user = (
        f"需求：{user_request}\n蓝图：{blueprint_text}\n"
        f"执行结果：{expert_text}\n第{r + 1}轮审查，请给出结论。"
    )

    message = _call_llm(system, user)

    verdict = "pass" if "PASS" in message.upper() and "NEEDS_REVISION" not in message.upper() else "needs_revision"

    return {
        "phase": "review",
        "review_round": r + 1,
        "review_verdict": verdict,
        "message": message,
    }
```

- [ ] **Step 2: 目视验证回复长度**

启动后端，运行图谱，确认每个 agent 的回复控制在 100-200 字符左右，语言风格简洁像群聊。

- [ ] **Step 3: Commit**

```bash
git add src/agentloom/graph/nodes/stubs.py
git commit -m "feat: limit agent replies to 100-200 chars with group chat style"
```

---

### Task 7: 三态控制按钮（启动/暂停/继续）

**Files:**
- Modify: `client/src/stores/chatStore.ts`
- Modify: `client/src/services/websocket.ts`
- Modify: `client/src/components/chat/ChatArea.tsx`
- Modify: `src/agentloom/api/routes/graph.py`

- [ ] **Step 1: 后端新增 pause action 处理**

打开 `src/agentloom/api/routes/graph.py`。

在 `graph_websocket` 函数的 `elif action == "resume":` 块之后，`else:` 块之前，添加 pause 处理：

```python
            elif action == "pause":
                session = _sessions.get(session_id)
                if session:
                    session["paused"] = True
                await websocket.send_json({
                    "type": "phase_complete",
                    "timestamp": _ts(),
                    "content": "项目已暂停",
                })
```

在 `_pump_graph_to_ws` 函数中添加暂停检测。修改 while 循环：

```python
async def _pump_graph_to_ws(
    websocket: WebSocket, graph: Any, input_obj: Any, cfg: dict,
    session_id: str = "",
) -> bool:
    """返回 True 表示正常完成，False 表示被暂停。"""
    q: queue.Queue[Any] = queue.Queue()

    def worker() -> None:
        try:
            for ev in _iter_graph_events(graph, input_obj, cfg):
                q.put(ev)
        except BaseException as exc:
            q.put({
                "type": "error",
                "timestamp": _ts(),
                "content": str(exc),
            })
        finally:
            q.put(_SENTINEL)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        # 检查是否被暂停
        session = _sessions.get(session_id, {})
        if session.get("paused"):
            return False
        try:
            item = await asyncio.wait_for(asyncio.to_thread(q.get), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        if item is _SENTINEL:
            break
        await websocket.send_json(item)
    return True
```

更新 `_pump_graph_to_ws` 的调用处，传入 `session_id`：

在 `action == "start"` 块中：
```python
await _pump_graph_to_ws(
    websocket, graph,
    {"task_id": task_id, "user_request": user_request},
    cfg, session_id=session_id,
)
```

在 `action == "resume"` 块中：
```python
session["paused"] = False
await _pump_graph_to_ws(websocket, graph, resume_input, cfg, session_id=session_id)
```

- [ ] **Step 2: WebSocket 客户端新增 pause 方法**

打开 `client/src/services/websocket.ts`。

在 `GraphSocket` 类中 `send` 方法已经可以通用发送 JSON。无需新增方法，直接用 `send({ action: "pause" })` 即可。

- [ ] **Step 3: 扩展 chatStore 状态**

打开 `client/src/stores/chatStore.ts`。

替换整个文件内容为：

```typescript
import { create } from "zustand";
import type { ChatEvent } from "../types";
import { graphSocket } from "../services/websocket";

interface ChatStore {
  events: ChatEvent[];
  currentPhase: string | null;
  isRunning: boolean;
  isPaused: boolean;
  isInterrupted: boolean;

  addEvent: (event: ChatEvent) => void;
  clearEvents: () => void;
  startGraph: (taskId: string, userRequest?: string) => void;
  pauseGraph: () => void;
  resumeGraph: (feedback: string) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  events: [],
  currentPhase: null,
  isRunning: false,
  isPaused: false,
  isInterrupted: false,

  addEvent: (event) =>
    set((s) => {
      const isPaused =
        event.type === "phase_complete" && event.content === "项目已暂停"
          ? true
          : s.isPaused;
      const isRunning =
        event.type === "task_complete" || event.type === "error"
          ? false
          : isPaused
            ? false
            : s.isRunning;
      return {
        events: [...s.events, event],
        currentPhase:
          event.type === "phase_start"
            ? (event.phase ?? s.currentPhase)
            : s.currentPhase,
        isInterrupted: event.type === "hitl_interrupt",
        isRunning,
        isPaused,
      };
    }),

  clearEvents: () =>
    set({
      events: [],
      currentPhase: null,
      isRunning: false,
      isPaused: false,
      isInterrupted: false,
    }),

  startGraph: (taskId, userRequest) => {
    const sessionId = crypto.randomUUID();
    graphSocket.connect(sessionId, {
      initial: {
        action: "start",
        task_id: taskId,
        user_request: userRequest || taskId,
      },
      onEvent: (event) => get().addEvent(event),
    });
    set({ isRunning: true, isPaused: false, isInterrupted: false, events: [] });
  },

  pauseGraph: () => {
    graphSocket.send({ action: "pause" });
  },

  resumeGraph: (feedback) => {
    graphSocket.send({ action: "resume", feedback });
    set({ isInterrupted: false, isPaused: false, isRunning: true });
  },
}));
```

- [ ] **Step 4: 修改 ChatArea 按钮为三态**

打开 `client/src/components/chat/ChatArea.tsx`。

从 useChatStore 中解构新增字段：

```tsx
const { events, isRunning, isPaused, isInterrupted, startGraph, pauseGraph, clearEvents } = useChatStore();
```

导入新图标：
```tsx
import { Play, Pause, RotateCcw } from "lucide-react";
```

替换按钮区域（行 53-74）为：

```tsx
<div className="flex items-center gap-2">
  {isRunning && !isPaused && (
    <button
      onClick={pauseGraph}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-warning"
    >
      <Pause size={12} />
      暂停项目
    </button>
  )}
  {isPaused && (
    <>
      <button
        onClick={() => {
          useChatStore.getState().resumeGraph("继续执行");
        }}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-success"
      >
        <Play size={12} />
        继续项目
      </button>
      <button
        onClick={() => {
          clearEvents();
          startGraph(activeTask.id, activeTask.name);
        }}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-text-secondary"
      >
        <RotateCcw size={12} />
        重新开始
      </button>
    </>
  )}
  {!isRunning && !isPaused && (
    <button
      onClick={() => {
        clearEvents();
        startGraph(activeTask.id, activeTask.name);
      }}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-success"
    >
      <Play size={12} />
      启动项目
    </button>
  )}
</div>
```

更新 status 计算逻辑（行 36-41）：

```tsx
const status = isRunning
  ? "running"
  : isPaused
    ? "paused"
    : isInterrupted
      ? "paused"
      : events.some((e) => e.type === "task_complete")
        ? "completed"
        : "idle";
```

- [ ] **Step 5: 目视验证三态按钮**

启动前后端：
1. 新建项目组 → 看到「启动项目」按钮（绿色）
2. 点击启动 → 按钮变为「暂停项目」（黄色）
3. 点击暂停 → 出现「继续项目」+「重新开始」按钮
4. 点击继续 → 恢复执行

- [ ] **Step 6: Commit**

```bash
git add client/src/stores/chatStore.ts client/src/components/chat/ChatArea.tsx src/agentloom/api/routes/graph.py client/src/services/websocket.ts
git commit -m "feat: add start/pause/resume project control buttons"
```

---

### Task 8: 需求收集 Agent 多轮对话

**Files:**
- Modify: `src/agentloom/api/routes/graph.py`
- Modify: `client/src/stores/chatStore.ts`
- Modify: `client/src/components/chat/ChatInput.tsx`
- Modify: `client/src/components/chat/ChatArea.tsx`

- [ ] **Step 1: 后端新增需求收集 WebSocket 处理**

打开 `src/agentloom/api/routes/graph.py`。

在文件顶部导入中添加：
```python
from agentloom.config.manager import load_full_config
```

在 `_AGENT_LABELS` 字典后添加需求收集对话函数：

```python
def _build_collect_system_prompt() -> str:
    """构建需求收集 agent 的 system prompt，包含工具信息。"""
    tools_info = ""
    try:
        cfg = load_full_config()
        mcp_entries = cfg.get("mcp", [])
        skill_entries = cfg.get("skills", [])
        if mcp_entries:
            tools_info += "可用的 MCP 工具：\n"
            for entry in mcp_entries:
                name = entry.get("name", entry.get("command", "未知"))
                tools_info += f"- {name}\n"
        if skill_entries:
            tools_info += "可用的技能：\n"
            for entry in skill_entries:
                name = entry.get("name", "未知")
                desc = entry.get("description", "")
                if entry.get("enabled", True):
                    tools_info += f"- {name}: {desc}\n"
    except Exception:
        tools_info = "（暂无工具信息）"

    return (
        "你是需求分析师，在一个项目群聊中负责收集用户的真实需求。\n"
        "规则：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁友好的群聊对话风格\n"
        "- 先做简短自我介绍，然后顺势询问用户想做什么\n"
        "- 根据用户回复判断需求是否足够清晰\n"
        "- 如果需要补充信息，继续提问（每次只问一个问题）\n"
        "- 如果需求已经明确，回复格式必须是：\n"
        "  「需求已明确：<简短总结>。是否启动项目？」\n"
        "- 如果判断当前工具无法完成需求，如实告知用户\n\n"
        f"当前可用的工具和技能：\n{tools_info}"
    )


async def _handle_collect(websocket: WebSocket, session_id: str, msg: dict) -> None:
    """处理需求收集多轮对话。"""
    session = _sessions.get(session_id)

    if session is None:
        # 首次：发送需求分析师加入群聊 + 自我介绍
        system_prompt = _build_collect_system_prompt()
        history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "（用户刚创建了项目组，请自我介绍并询问需求）"},
        ]

        await websocket.send_json({
            "type": "phase_start",
            "timestamp": _ts(),
            "phase": "consultant",
            "agent": "consultant",
            "content": "需求分析师 加入群聊",
        })
        await websocket.send_json({
            "type": "agent_thinking",
            "timestamp": _ts(),
            "phase": "consultant",
            "agent": "consultant",
            "content": "",
        })

        from agentloom.llm.factory import get_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage as SysMsg

        llm = get_chat_model()
        resp = llm.invoke([
            SysMsg(content=system_prompt),
            HumanMessage(content="（用户刚创建了项目组，请自我介绍并询问需求）"),
        ])
        reply = resp.content

        await websocket.send_json({
            "type": "agent_output",
            "timestamp": _ts(),
            "phase": "consultant",
            "agent": "consultant",
            "content": reply,
        })

        history.append({"role": "assistant", "content": reply})
        _sessions[session_id] = {
            "mode": "collect",
            "history": history,
            "system_prompt": system_prompt,
            "collected_request": "",
        }

    else:
        # 后续轮次：用户回复
        user_msg = msg.get("content", "")
        history = session["history"]
        system_prompt = session["system_prompt"]

        history.append({"role": "user", "content": user_msg})

        await websocket.send_json({
            "type": "agent_thinking",
            "timestamp": _ts(),
            "phase": "consultant",
            "agent": "consultant",
            "content": "",
        })

        from agentloom.llm.factory import get_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage as SysMsg, AIMessage

        llm = get_chat_model()
        messages = [SysMsg(content=system_prompt)]
        for h in history[1:]:  # skip system
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                messages.append(AIMessage(content=h["content"]))

        resp = llm.invoke(messages)
        reply = resp.content

        await websocket.send_json({
            "type": "agent_output",
            "timestamp": _ts(),
            "phase": "consultant",
            "agent": "consultant",
            "content": reply,
        })

        history.append({"role": "assistant", "content": reply})
        session["history"] = history

        # 检查是否需求已确认
        if "是否启动项目" in reply:
            # 从对话历史整理需求摘要
            session["collected_request"] = user_msg
```

修改 `graph_websocket` 函数，在 `action == "start"` 之前添加 collect 和 confirm 处理：

```python
            if action == "collect":
                await _handle_collect(websocket, session_id, msg)

            elif action == "confirm_start":
                # 用户确认启动项目，从需求收集切换到图谱执行
                session = _sessions.get(session_id)
                collected = ""
                if session and session.get("mode") == "collect":
                    # 从对话历史拼接用户需求
                    history = session.get("history", [])
                    user_msgs = [h["content"] for h in history if h["role"] == "user" and not h["content"].startswith("（")]
                    collected = "\n".join(user_msgs)
                    _sessions.pop(session_id, None)

                task_id = msg.get("task_id", "api-task")
                user_request = collected or msg.get("user_request", task_id)
                thread_id = str(uuid.uuid4())
                cfg = {"configurable": {"thread_id": thread_id}}
                graph = build_graph()

                await _pump_graph_to_ws(
                    websocket, graph,
                    {"task_id": task_id, "user_request": user_request},
                    cfg, session_id=session_id,
                )
                _sessions[session_id] = {"graph": graph, "cfg": cfg}

            elif action == "start":
```

- [ ] **Step 2: 前端 chatStore 新增需求收集模式**

打开 `client/src/stores/chatStore.ts`。

在 `ChatStore` interface 中添加：
```typescript
isCollecting: boolean;
startCollect: (taskId: string) => void;
sendCollectMessage: (content: string) => void;
confirmStart: (taskId: string) => void;
```

在 create 中添加初始值和实现：

```typescript
isCollecting: false,

startCollect: (taskId) => {
  const sessionId = crypto.randomUUID();
  graphSocket.connect(sessionId, {
    initial: {
      action: "collect",
      task_id: taskId,
    },
    onEvent: (event) => get().addEvent(event),
  });
  set({ isCollecting: true, isRunning: false, isPaused: false, isInterrupted: false, events: [] });
},

sendCollectMessage: (content) => {
  get().addEvent({
    type: "user_response",
    timestamp: new Date().toISOString(),
    content,
  });
  graphSocket.send({ action: "collect", content });
},

confirmStart: (taskId) => {
  graphSocket.send({ action: "confirm_start", task_id: taskId });
  set({ isCollecting: false, isRunning: true });
},
```

更新 `clearEvents` 中重置 `isCollecting: false`。

更新 `addEvent` 中对 `task_complete` 和 `error` 也重置 `isCollecting: false`。

- [ ] **Step 3: 修改 ChatInput 在需求收集阶段可用**

打开 `client/src/components/chat/ChatInput.tsx`。

更新 store 解构：
```tsx
const { isInterrupted, isRunning, isCollecting, resumeGraph, sendCollectMessage, addEvent } = useChatStore();
```

修改 `handleSend`：
```tsx
const handleSend = () => {
  const msg = text.trim();
  if (!msg) return;

  if (isCollecting) {
    sendCollectMessage(msg);
    setText("");
    return;
  }

  addEvent({
    type: "user_response",
    timestamp: new Date().toISOString(),
    content: msg,
  });
  resumeGraph(msg);
  setText("");
};
```

修改 `canSend`：
```tsx
const canSend = text.trim().length > 0 && (isCollecting || isInterrupted || !isRunning);
```

修改 placeholder：
```tsx
placeholder={isCollecting ? "回复需求分析师..." : isInterrupted ? "回复 Agent..." : "输入消息与 Agent 对话..."}
```

自动聚焦条件扩展：
```tsx
useEffect(() => {
  if (isInterrupted || isCollecting) {
    textareaRef.current?.focus();
  }
}, [isInterrupted, isCollecting]);
```

- [ ] **Step 4: ChatArea 新建项目组后自动触发需求收集**

打开 `client/src/components/chat/ChatArea.tsx`。

从 store 解构新增：
```tsx
const { events, isRunning, isPaused, isInterrupted, isCollecting, startGraph, pauseGraph, clearEvents, startCollect, confirmStart } = useChatStore();
```

新建项目组后自动触发需求收集（在组件中添加 useEffect）：

```tsx
// 新项目组自动触发需求收集
const prevTaskRef = useRef<string | null>(null);
useEffect(() => {
  if (activeTask && activeTask.id !== prevTaskRef.current) {
    prevTaskRef.current = activeTask.id;
    // 仅当没有事件时自动启动收集（避免切换回旧项目组时重复触发）
    if (events.length === 0 && !isRunning && !isCollecting) {
      startCollect(activeTask.id);
    }
  }
}, [activeTask?.id]);
```

修改「启动项目」按钮逻辑，在需求收集完成后变为确认启动：

在按钮区域中添加：
```tsx
{isCollecting && (
  <button
    onClick={() => confirmStart(activeTask.id)}
    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-success"
  >
    <Play size={12} />
    启动项目
  </button>
)}
```

修改空事件提示为只在非收集模式时显示：
```tsx
{events.length === 0 && !isCollecting ? (
  <div className="flex flex-col items-center justify-center h-full gap-2">
    <p className="text-text-muted text-sm">新项目组已创建，等待启动...</p>
  </div>
) : (
  events.map((event, i) => { ... })
)}
```

- [ ] **Step 5: 目视验证完整流程**

启动前后端：
1. 新建项目组 → 需求分析师自动"加入群聊"→ 发送自我介绍和提问
2. 用户输入需求 → 需求分析师追问或确认
3. 多轮对话直到需求明确 → 需求分析师发出"是否启动项目？"
4. 用户点击「启动项目」→ 后续 agent 按序执行
5. 打字动画、加入群聊提示、回复长度均正常

- [ ] **Step 6: Commit**

```bash
git add src/agentloom/api/routes/graph.py client/src/stores/chatStore.ts client/src/components/chat/ChatInput.tsx client/src/components/chat/ChatArea.tsx
git commit -m "feat: add multi-round requirement collection dialog before project execution"
```

---

### Task 9: AgentMessage 适配浅色主题

**Files:**
- Modify: `client/src/components/chat/AgentMessage.tsx`

- [ ] **Step 1: 阅读当前 AgentMessage 组件**

先读取 `client/src/components/chat/AgentMessage.tsx` 了解当前实现。

- [ ] **Step 2: 更新消息气泡样式为浅色**

当前 AgentMessage 可能使用暗色背景气泡。改为：
- 气泡背景：`bg-white/80 backdrop-blur-sm`
- 边框：`border border-black/5`
- 文字：`text-text-body`（深色）
- Agent 名称颜色使用 `meta.nameColor`（Task 1 中已改为深色值）

具体修改取决于读到的当前实现，确保气泡在浅色背景上可读且有轻微投影效果。

- [ ] **Step 3: 目视验证消息在浅色主题上的效果**

确认 agent 消息气泡在浅色背景上：
- 白底半透明 + 轻投影
- 文字清晰可读
- Agent 名称颜色与各自品牌色一致

- [ ] **Step 4: Commit**

```bash
git add client/src/components/chat/AgentMessage.tsx
git commit -m "feat: adapt AgentMessage component to light theme"
```

---

### Task 10: 最终集成验证

- [ ] **Step 1: 完整流程端到端验证**

启动前后端，按以下步骤验证：

1. 打开应用 → 浅色毛玻璃主题，紫蓝渐变品牌色
2. 点击「新建项目组」→ 输入名称 → 创建
3. 需求分析师自动"加入群聊"→ 打字动画 → 自我介绍 + 提问
4. 用户输入需求 → 多轮对话 → 需求明确后确认
5. 点击「启动项目」→ 架构设计师"加入群聊"→ 打字动画 → 简短回复
6. 方案审核员"加入群聊"→ HITL 中断 → 用户审核
7. 点击「暂停项目」→ 项目暂停 → 点击「继续项目」→ 恢复
8. 执行专家组 → 质量审查员 → 项目完成
9. 所有 agent 回复长度 ≤ 200 字符
10. 所有 agent 显示中文名称

- [ ] **Step 2: 检查控制台无错误**

打开浏览器 DevTools，确认无 JS 错误和未捕获的 WebSocket 异常。

- [ ] **Step 3: Commit 最终调整（如有）**

```bash
git add -A
git commit -m "fix: final integration adjustments for group chat UX"
```
