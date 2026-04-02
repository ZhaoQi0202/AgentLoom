"""事件总线：允许 graph 节点内部实时推送事件到 WebSocket。

使用方式：
- graph.py 在 _pump_graph_to_ws 中注册队列
- orchestrator/agent 通过 emit_event 推送事件
- 事件会实时发送到前端
"""
from __future__ import annotations

import queue
import threading

_lock = threading.Lock()
_queues: dict[str, queue.Queue] = {}


def register_queue(thread_id: str, q: queue.Queue) -> None:
    """注册事件队列（由 _pump_graph_to_ws 调用）。"""
    with _lock:
        _queues[thread_id] = q


def unregister_queue(thread_id: str) -> None:
    """注销事件队列。"""
    with _lock:
        _queues.pop(thread_id, None)


def emit_event(thread_id: str, event: dict) -> None:
    """向指定 thread_id 的队列推送事件。线程安全。"""
    with _lock:
        q = _queues.get(thread_id)
    if q is not None:
        q.put(event)
