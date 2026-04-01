from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agentloom.graph.builder import build_graph
from agentloom.graph.stream_util import split_stream_chunk
from langgraph.types import Command

router = APIRouter(tags=["graph"])

_sessions: dict[str, dict[str, Any]] = {}

_SENTINEL = object()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


_AGENT_LABELS: dict[str, str] = {
    "consultant": "需求分析师",
    "architect": "架构设计师",
    "hitl_blueprint": "方案审核员",
    "experts": "执行专家组",
    "reviewer": "质量审查员",
}


def _iter_graph_events(graph: Any, input_obj: Any, cfg: dict) -> Iterator[dict[str, Any]]:
    # Before starting stream, predict the first node and send thinking
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
        pass  # First start has no state yet

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
            # After each node completes, check for next node and send thinking
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


async def _pump_graph_to_ws(
    websocket: WebSocket, graph: Any, input_obj: Any, cfg: dict,
    session_id: str = "",
) -> bool:
    """Returns True if completed normally, False if paused."""
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


@router.websocket("/ws/graph/{session_id}")
async def graph_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()

    graph = None
    cfg: dict[str, Any] = {}
    thread_id = ""

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            action = msg.get("action")

            if action == "start":
                task_id = msg.get("task_id", "api-task")
                user_request = msg.get("user_request", task_id)
                thread_id = str(uuid.uuid4())
                cfg = {"configurable": {"thread_id": thread_id}}
                graph = build_graph()

                await websocket.send_json({
                    "type": "phase_start",
                    "timestamp": _ts(),
                    "phase": "pending",
                    "content": "项目已启动，Agent 正在就位…",
                })

                await _pump_graph_to_ws(
                    websocket,
                    graph,
                    {"task_id": task_id, "user_request": user_request},
                    cfg,
                    session_id=session_id,
                )

                _sessions[session_id] = {"graph": graph, "cfg": cfg}

            elif action == "resume":
                feedback = msg.get("feedback", {})
                session = _sessions.get(session_id)
                if session is None or session["graph"] is None:
                    await websocket.send_json({
                        "type": "error",
                        "timestamp": _ts(),
                        "content": "会话不存在或已结束",
                    })
                    continue

                graph = session["graph"]
                cfg = session["cfg"]
                resume_input = Command(resume=feedback if feedback else {})

                session["paused"] = False
                await _pump_graph_to_ws(websocket, graph, resume_input, cfg, session_id=session_id)

            elif action == "pause":
                session = _sessions.get(session_id)
                if session:
                    session["paused"] = True
                await websocket.send_json({
                    "type": "phase_complete",
                    "timestamp": _ts(),
                    "content": "项目已暂停",
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "timestamp": _ts(),
                    "content": f"未知操作: {action}",
                })

    except WebSocketDisconnect:
        _sessions.pop(session_id, None)
    except Exception as exc:
        try:
            await websocket.send_json({
                "type": "error",
                "timestamp": _ts(),
                "content": str(exc),
            })
        except Exception:
            pass
        _sessions.pop(session_id, None)
