"""事件总线：允许 graph 节点内部实时推送事件到 WebSocket。

使用方式：
- graph.py 在 _pump_graph_to_ws 中注册队列
- orchestrator/agent 通过 emit_event 推送事件
- 事件会实时发送到前端
- 事件同时持久化到 chat_history.json
"""
from __future__ import annotations

import json
import logging
import queue
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_queues: dict[str, queue.Queue] = {}
_thread_tasks: dict[str, str] = {}


def register_queue(thread_id: str, q: queue.Queue) -> None:
    """注册事件队列（由 _pump_graph_to_ws 调用）。"""
    with _lock:
        _queues[thread_id] = q


def unregister_queue(thread_id: str) -> None:
    """注销事件队列。"""
    with _lock:
        _queues.pop(thread_id, None)
        _thread_tasks.pop(thread_id, None)


def register_thread_task(thread_id: str, task_id: str) -> None:
    """将 thread_id 与 task_id 关联，用于聊天历史持久化。"""
    with _lock:
        _thread_tasks[thread_id] = task_id


def _save_event_to_history(thread_id: str, event: dict) -> None:
    """将事件追加写入对应项目的 chat_history.json。"""
    task_id = _thread_tasks.get(thread_id)
    if not task_id:
        return
    try:
        from agentcrewchat.paths import workspaces_dir

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
                json.dumps(events, ensure_ascii=False),
                encoding="utf-8",
            )
    except Exception:
        logger.error("保存聊天历史失败", exc_info=True)


def _enrich_with_identity(event: dict) -> dict:
    """为含 agent 字段的事件自动注入 agent_name / agent_color。"""
    agent_id = event.get("agent")
    if not agent_id:
        return event
    # 已有动态值则不覆盖
    if "agent_name" in event and "agent_color" in event:
        return event
    from agentcrewchat.graph.agent_identity import get_agent_display
    display = get_agent_display(agent_id)
    event.setdefault("agent_name", display["name"])
    event.setdefault("agent_color", display["color"])
    return event


def emit_event(thread_id: str, event: dict) -> None:
    """向指定 thread_id 的队列推送事件。线程安全。自动注入 Agent 身份信息。同时持久化到 chat_history.json。"""
    event = _enrich_with_identity(event)
    # 持久化
    _save_event_to_history(thread_id, event)
    # 推送到 WS 队列
    with _lock:
        q = _queues.get(thread_id)
    if q is not None:
        q.put(event)
