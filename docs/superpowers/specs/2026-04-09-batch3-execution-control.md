# Batch 3 设计规格：执行控制 — 暂停/审核超限/重规划

> **日期**：2026-04-09
> **范围**：F-12、F-13、F-14、G2、G3
> **前置**：Batch 1（Agent 身份）+ Batch 2（执行 Agent 个性、聊天持久化）

---

## 1. F-12 + G2：真正的任务间暂停

### 1.1 问题

当前 `pauseGraph()` 只在前端设置 `isPaused = true`，后端继续执行无感知。`resumeGraph()` 直接向 WS 发送 "继续执行" 文本，被当作 HITL resume 处理。

### 1.2 方案

每个 session 维护一个 `threading.Event`（暂停信号），orchestrator 在每个任务间隙检查信号。

#### 1.2.1 新增 `src/agentcrewchat/graph/pause_manager.py`

```python
"""暂停管理器：为每个 session 维护暂停信号。"""
from __future__ import annotations

import threading

_pauses: dict[str, threading.Event] = {}
_lock = threading.Lock()


def create_pause_signal(thread_id: str) -> threading.Event:
    """创建暂停信号（默认不暂停 = Event is set）。"""
    evt = threading.Event()
    evt.set()  # set 表示"可以继续"
    with _lock:
        _pauses[thread_id] = evt
    return evt


def pause(thread_id: str) -> None:
    """暂停执行（clear signal）。"""
    with _lock:
        evt = _pauses.get(thread_id)
    if evt:
        evt.clear()


def resume(thread_id: str) -> None:
    """继续执行（set signal）。"""
    with _lock:
        evt = _pauses.get(thread_id)
    if evt:
        evt.set()


def wait_if_paused(thread_id: str) -> None:
    """阻塞直到暂停解除。如果无信号则直接放行。"""
    with _lock:
        evt = _pauses.get(thread_id)
    if evt:
        evt.wait()


def is_paused(thread_id: str) -> bool:
    with _lock:
        evt = _pauses.get(thread_id)
    return evt is not None and not evt.is_set()


def cleanup(thread_id: str) -> None:
    with _lock:
        _pauses.pop(thread_id, None)
```

#### 1.2.2 修改 `orchestrator.py`

在每层任务循环的每个任务执行**之前**检查暂停信号：

```python
from agentcrewchat.graph.pause_manager import wait_if_paused, is_paused

# 在 for task in layer: 循环体内，创建工具之前：
wait_if_paused(thread_id)
```

任务开始时 `emit_event` 一个状态事件：

```python
emit_event(thread_id, {
    "type": "agent_output",
    "timestamp": _ts(),
    "phase": "experts",
    "agent": "experts",
    "agent_name": identity.name,
    "agent_color": identity.color,
    "content": f"⏸️ 已暂停，等待继续...",
})
```

#### 1.2.3 修改 `graph.py` — 新增 `pause`/`resume` action

在 WebSocket handler 中：

```python
elif action == "pause":
    from agentcrewchat.graph.pause_manager import pause as pm_pause
    session = _sessions.get(session_id)
    if session and session.get("thread_id"):
        pm_pause(session["thread_id"])
        await websocket.send_json({
            "type": "agent_output",
            "timestamp": _ts(),
            "phase": "experts",
            "agent": "experts",
            "content": "收到暂停指令，当前任务完成后将暂停 ⏸️",
        })

elif action == "resume":
    from agentcrewchat.graph.pause_manager import resume as pm_resume
    session = _sessions.get(session_id)
    if session and session.get("thread_id"):
        pm_resume(session["thread_id"])
```

需要在 session dict 中存储 `thread_id`。在 `_pump_graph_to_ws` 调用前：`session["thread_id"] = thread_id`

#### 1.2.4 暂停信号注册

在 `_pump_graph_to_ws` 中，`register_queue` 之后调用 `create_pause_signal(thread_id)`。

在 `_SENTINEL` 之前调用 `cleanup(thread_id)`。

#### 1.2.5 前端 — 修改 `chatStore.ts`

`pauseGraph()` 现在发送 WS 消息而不是只改本地状态：

```typescript
pauseGraph: () => {
  graphSocket.send({ action: "pause" });
  set({ isPaused: true });
},

resumeGraph: (feedback: string) => {
  graphSocket.send({ action: "resume", feedback });
  set({ isInterrupted: false, isPaused: false });
},
```

#### 1.2.6 前端 — 修改 `ActionBar.tsx`

暂停按钮逻辑不变（已有），但 `pauseGraph` 现在走 WS 通道，暂停确认由后端事件驱动。

---

## 2. F-13 + G3：审核超限用户选项卡

### 2.1 问题

当前 orchestrator 中每个任务最多重试 `MAX_AGENT_RETRY`（= 3）次，超限后静默继续下一个任务。

### 2.2 方案

超限后，后端发送 `hitl_retry_limit` 中断事件，铁口用 LLM 生成自然语言说明并在话术中引导用户选择。前端显示三个快捷回复按钮 + 支持自由输入。

### 2.3 后端 — 修改 `orchestrator.py`

#### 2.3.1 新增超限事件

替换 `MAX_AGENT_RETRY` 循环结束后的当前逻辑：

```python
# 当前代码：超限后静默继续
if not review_passed:
    emit_event(thread_id, {
        "type": "agent_output",
        "content": f"⚠️ 任务「{task_name}」经过 {MAX_AGENT_RETRY} 次重试仍未通过审核，先记录结果继续推进",
    })

# 改为：
if not review_passed:
    # 超限，进入用户决策
    decision = await_orchestration_decision(
        task_id=task_id,
        task_name=task_name,
        task_goal=task_goal,
        review_msg=review_msg,
        attempt=attempt,
        thread_id=thread_id,
        can_reroute=not task.get("_rerouted"),  # 每个任务只能重规划一次
    )
    if decision == "skip":
        pass  # 继续后续任务
    elif decision == "reroute":
        # 局部重规划
        ...
    elif decision == "terminate":
        # 终止整个流水线
        ...
```

#### 2.3.2 新增 `src/agentcrewchat/graph/decision_handler.py`

```python
"""审核超限用户决策处理器。"""
from __future__ import annotations

import json
import threading
from typing import Any

from agentcrewchat.graph.event_bus import emit_event
from agentcrewchat.llm.factory import get_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

REVIEW_OVER_LIMIT_PROMPT = """\
你是铁口，一位毒舌但细致的审核员。某个任务已经尝试了 3 次仍未通过审核。
你需要用自然语言向用户说明情况，并在话术中自然引导用户做出选择。

## 你的话术中必须包含以下三个选项的引导（用自然语言，不要用编号列表）：
1. 让我们跳过这个任务继续推进
2. 交还架构师明哲重新规划这个任务点
3. 终止整个执行流程

语气要像在工作群里跟同事说正事，简短有力。
"""


def generate_review_limit_message(
    task_name: str,
    task_goal: str,
    review_msg: str,
) -> str:
    """让 LLM 生成铁口的超限说明消息。"""
    user_prompt = (
        f"任务名称: {task_name}\n"
        f"任务目标: {task_goal}\n"
        f"审核意见: {review_msg}\n\n"
        f"请用自然语言向用户说明情况。"
    )
    llm = get_chat_model(phase="review")
    resp = llm.invoke([
        SystemMessage(content=REVIEW_OVER_LIMIT_PROMPT),
        HumanMessage(content=user_prompt),
    ])
    return resp.content


# ── 决策信号 ──
_decision_signals: dict[str, str] = {}
_decision_events: dict[str, threading.Event] = {}
_lock = threading.Lock()


def wait_for_decision(thread_id: str, timeout: float = 600) -> str:
    """阻塞等待用户决策，返回 "skip" / "reroute" / "terminate"。"""
    evt = threading.Event()
    with _lock:
        _decision_events[thread_id] = evt
    evt.wait(timeout=timeout)
    with _lock:
        evt = _decision_events.pop(thread_id, None)
        decision = _decision_signals.pop(thread_id, "skip")
    return decision


def submit_decision(thread_id: str, decision: str) -> None:
    """提交用户决策。"""
    with _lock:
        _decision_signals[thread_id] = decision
        evt = _decision_events.get(thread_id)
    if evt:
        evt.set()


def classify_user_input(text: str, can_reroute: bool) -> str:
    """将用户自由文本归类为 skip/reroute/terminate。"""
    t = (text or "").strip().lower()

    terminate_kw = ["终止", "停止", "结束", "放弃", "不做了", "算了"]
    reroute_kw = ["重做", "重新规划", "重新设计", "交给明哲", "交还明哲", "reroute"]
    skip_kw = ["跳过", "继续", "忽略", "跳过继续", "算了继续", "先跳过", "skip"]

    for kw in terminate_kw:
        if kw in t:
            return "terminate"
    if can_reroute:
        for kw in reroute_kw:
            if kw in t:
                return "reroute"
    for kw in skip_kw:
        if kw in t:
            return "skip"
    # 默认跳过
    return "skip"
```

#### 2.3.3 orchestrator 集成

```python
from agentcrewchat.graph.decision_handler import (
    generate_review_limit_message,
    wait_for_decision,
)

# 超限时：
if not review_passed:
    limit_msg = generate_review_limit_message(task_name, task_goal, review_msg)
    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "review",
        "agent": "reviewer",
        "content": f"🔍 @{task_name} 审核未通过（{MAX_AGENT_RETRY} 次上限）：\n{limit_msg}",
        "metadata": {"task_id": task_id, "verdict": "over_limit", "quick_replies": ["跳过继续", "交还明哲", "终止执行"]},
    })
    emit_event(thread_id, {
        "type": "hitl_retry_limit",
        "timestamp": _ts(),
        "phase": "review",
        "agent": "reviewer",
        "content": "等待用户决策",
        "metadata": {"task_id": task_id},
    })

    decision = wait_for_decision(thread_id)
    # ... 处理 decision
```

#### 2.3.4 修改 `graph.py` WS handler

新增 action 处理：

```python
elif action == "decision":
    from agentcrewchat.graph.decision_handler import submit_decision, classify_user_input
    session = _sessions.get(session_id)
    decision_type = msg.get("decision", "")
    user_text = msg.get("message", "")
    thread_id = session.get("thread_id", "") if session else ""

    if decision_type in ("skip", "reroute", "terminate"):
        submit_decision(thread_id, decision_type)
    elif user_text:
        can_reroute = session.get("_can_reroute", True) if session else True
        decision_type = classify_user_input(user_text, can_reroute)
        submit_decision(thread_id, decision_type)
```

### 2.4 局部重规划（F-14）

当 `decision == "reroute"` 时：

1. 向明哲（architect_agent）发送重规划请求

```python
elif decision == "reroute":
    task["_rerouted"] = True  # 标记已重规划，防止二次 reroute
    new_blueprint = _reroute_task(
        task=task,
        review_msg=review_msg,
        result=final_result,
        workspace=workspace,
        thread_id=thread_id,
    )
    if new_blueprint:
        # 替换原任务节点
        for i, t in enumerate(blueprint["tasks"]):
            if t["id"] == task_id:
                blueprint["tasks"][i] = new_blueprint
                break
        # 重新执行该任务（同层内）
        # ... 用新蓝图重新调用 react_agent
```

#### 2.4.1 新增 `_reroute_task` 函数

```python
def _reroute_task(
    task: dict,
    review_msg: str,
    result: dict,
    workspace: Path,
    thread_id: str,
) -> dict | None:
    """让架构师为失败任务生成替代方案。"""
    from agentcrewchat.graph.nodes.architect_agent import generate_blueprint

    reroute_requirement = {
        "core_goal": task.get("goal", ""),
        "failure_context": {
            "original_task": task,
            "execution_output": result.get("output", ""),
            "review_feedback": review_msg,
            "guidance": "请为这个任务设计替代方案，更换工具或思路，保持 task_id 不变。",
        },
    }

    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "experts",
        "agent": "architect",
        "content": f"收到，「{task.get('name')}」没跑通，我来看看怎么调整方案 🔧",
    })

    _, blueprint = generate_blueprint(reroute_requirement, workspace)
    if blueprint and blueprint.get("tasks"):
        new_task = blueprint["tasks"][0]
        new_task["id"] = task.get("id")  # 保持原 task_id
        return new_task
    return None
```

### 2.5 前端 — 快捷回复按钮

#### 2.5.1 修改 `chatStore.ts`

新增状态：

```typescript
interface ChatStore {
  // ... existing
  quickReplies: string[];  // 后端推来的快捷回复选项
  setQuickReplies: (replies: string[]) => void;
}
```

在 `addEvent` 中：

```typescript
if (event.type === "hitl_retry_limit") {
  const replies = (event.metadata?.quick_replies as string[]) || [];
  set({ quickReplies: replies, isInterrupted: true });
  return;
}
```

在 `resumeGraph` 和用户输入时：

```typescript
set({ quickReplies: [] });
```

#### 2.5.2 修改 `ChatInput.tsx`

在输入框上方渲染快捷回复按钮：

```tsx
{quickReplies.length > 0 && (
  <div className="flex gap-2 mb-2 flex-wrap">
    {quickReplies.map((reply) => (
      <button
        key={reply}
        onClick={() => {
          addEvent({
            type: "user_response",
            timestamp: new Date().toISOString(),
            content: reply,
          });
          graphSocket.send({ action: "decision", message: reply });
          setQuickReplies([]);
        }}
        className="px-3 py-1.5 text-xs font-medium rounded-lg glass glass-hover text-text-primary border border-border-subtle"
      >
        {reply}
      </button>
    ))}
  </div>
)}
```

#### 2.5.3 修改 `ChatInput.tsx` 自由输入

当用户忽略快捷按钮直接输入时，走 `resumeGraph` 路径（已有的），后端通过 `classify_user_input` 解析意图。

---

## 3. WS 事件类型扩展

新增事件 type：

| type | 方向 | 说明 |
|------|------|------|
| `hitl_retry_limit` | S→C | 审核超限，等待用户决策。`metadata.quick_replies` 包含快捷回复选项 |

需同步更新 `ChatEventType` 联合类型（`client/src/types/index.ts`）和 `product.md`。

### 3.1 前端类型

```typescript
export type ChatEventType =
  | "phase_start"
  | "agent_join"
  | "agent_thinking"
  | "agent_output"
  | "hitl_interrupt"
  | "hitl_retry_limit"  // 新增
  | "user_response"
  | "phase_complete"
  | "task_complete"
  | "error";
```

### 3.2 前端 `ChatArea.tsx`

在 `switch (event.type)` 中增加：

```tsx
case "hitl_retry_limit":
  // 由 ChatInput 渲染快捷按钮，这里只渲染铁口的消息
  return <AgentMessage key={i} event={events[i - 1]} />;
```

实际上 `hitl_retry_limit` 的前一条 `agent_output` 事件已经包含了铁口的消息和 `quick_replies` metadata。`ChatInput` 读取 `quickReplies` 状态渲染按钮。

---

## 4. orchestrator.py 决策循环完整流程

```python
for attempt in range(MAX_AGENT_RETRY + 1):
    result = run_react_agent(...)
    final_result = result

    if result["status"] == "error":
        break

    review_passed, review_msg = review_task(...)

    if review_passed:
        break

    if attempt < MAX_AGENT_RETRY:
        retry_feedback = review_msg
        emit_event(..., content="审核未通过，重新执行...")

# 审核结果处理
if review_passed:
    emit_event(..., content="✅ 审核通过！")
elif task.get("_rerouted"):
    # 已重规划过，不能再 reroute
    limit_msg = generate_review_limit_message(...)
    emit_event(..., content=limit_msg, metadata={"quick_replies": ["跳过继续", "终止执行"]})
    decision = wait_for_decision(thread_id)
    if decision == "terminate":
        emit_event(..., content="流水线已终止")
        return all_results
    # skip: 继续
else:
    limit_msg = generate_review_limit_message(...)
    emit_event(..., content=limit_msg, metadata={"quick_replies": ["跳过继续", "交还明哲", "终止执行"]})
    decision = wait_for_decision(thread_id)
    if decision == "terminate":
        emit_event(..., content="流水线已终止")
        return all_results
    elif decision == "reroute":
        task["_rerouted"] = True
        new_task = _reroute_task(...)
        if new_task:
            blueprint["tasks"][...] = new_task
            # 重新执行（非递归，直接替换当前 task dict 并再来一轮）
            retry_feedback = review_msg
            rerouted_result = run_react_agent(...)
            # 审核 rerouted_result...
        # reroute 失败或仍不通过 → skip
```

为避免复杂递归，reroute 后的重新执行放在当前 task 循环内、用一个 `if not review_passed and decision == "reroute"` 分支处理。

---

## 5. 文件改动汇总

| 文件 | 操作 | 哪一节 |
|------|------|--------|
| `src/agentcrewchat/graph/pause_manager.py` | 新增 | 1.2.1 |
| `src/agentcrewchat/graph/orchestrator.py` | 修改 | 1.2.2, 2.3.3, 2.4.1 |
| `src/agentcrewchat/graph/decision_handler.py` | 新增 | 2.3.2 |
| `src/agentcrewchat/graph/event_bus.py` | 修改 | 1.2.4（pause signal 注册） |
| `src/agentcrewchat/api/routes/graph.py` | 修改 | 1.2.3, 2.3.4 |
| `client/src/types/index.ts` | 修改 | 3.1 |
| `client/src/stores/chatStore.ts` | 修改 | 1.2.5, 2.5.1 |
| `client/src/components/chat/ChatInput.tsx` | 修改 | 2.5.2, 2.5.3 |
| `client/src/components/chat/ActionBar.tsx` | 小改 | 1.2.6（确认后端消息走 WS） |

---

## 6. 不涉及的内容

以下内容属于后续 Batch，本次不做：
- 执行 Agent 随机名/性格池（Batch 2）
- 聊天历史持久化（Batch 2）
- 右侧面板（Batch 2）
- 安装包打包（Batch 4）
