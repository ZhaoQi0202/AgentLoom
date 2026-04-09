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
