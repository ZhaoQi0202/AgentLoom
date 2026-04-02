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
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Command

from agentloom.graph.nodes.consultant_agent import (
    CONSULTANT_SYSTEM_PROMPT,
    build_initial_greeting,
    consult_turn,
    extract_requirement,
    strip_summary_block,
)
from agentloom.paths import workspaces_dir
from agentloom.tasks.requirement import save_requirement

router = APIRouter(tags=["graph"])

_sessions: dict[str, dict[str, Any]] = {}

_SENTINEL = object()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iter_graph_events(graph: Any, input_obj: Any, cfg: dict) -> Iterator[dict[str, Any]]:
    for chunk in graph.stream(input_obj, cfg, stream_mode="updates"):
        parts, has_interrupt = split_stream_chunk(chunk)
        for node, upd in parts:
            phase = upd.get("phase", node)
            yield {
                "type": "phase_start",
                "timestamp": _ts(),
                "phase": phase,
                "agent": node,
                "content": f"阶段: {node}",
            }
            content = upd.get("message") or json.dumps(upd, ensure_ascii=False, default=str)
            yield {
                "type": "agent_output",
                "timestamp": _ts(),
                "phase": phase,
                "agent": node,
                "content": content,
            }
        if has_interrupt:
            st = graph.get_state(cfg)
            nxt = st.next[0] if st.next else ""
            interrupt_msg = f"图谱在 {nxt} 阶段中断，等待人工输入"
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
        "content": "任务完成",
    }


async def _pump_graph_to_ws(
    websocket: WebSocket, graph: Any, input_obj: Any, cfg: dict
) -> None:
    q: queue.Queue[Any] = queue.Queue()
    thread_id = cfg.get("configurable", {}).get("thread_id", "")

    from agentloom.graph.event_bus import register_queue, unregister_queue
    register_queue(thread_id, q)

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
            unregister_queue(thread_id)
            q.put(_SENTINEL)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = await asyncio.to_thread(q.get)
        if item is _SENTINEL:
            break
        await websocket.send_json(item)


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
                    "content": "已收到任务，正在运行图谱…",
                })

                await _pump_graph_to_ws(
                    websocket,
                    graph,
                    {"task_id": task_id, "user_request": user_request, "_thread_id": thread_id},
                    cfg,
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

                await _pump_graph_to_ws(websocket, graph, resume_input, cfg)

            elif action == "collect":
                task_id = msg.get("task_id", "api-task")
                user_msg = msg.get("message", "")

                if session_id not in _sessions:
                    _sessions[session_id] = {
                        "graph": None,
                        "cfg": {},
                        "consultant_history": [
                            SystemMessage(content=CONSULTANT_SYSTEM_PROMPT)
                        ],
                        "consultant_ready": False,
                        "task_id": task_id,
                    }

                session = _sessions[session_id]
                history = session["consultant_history"]

                if not user_msg:
                    greeting = build_initial_greeting()
                    history.append(AIMessage(content=greeting))
                    await websocket.send_json({
                        "type": "phase_start",
                        "timestamp": _ts(),
                        "phase": "consult",
                        "agent": "consultant",
                        "content": "需求收集阶段",
                    })
                    await websocket.send_json({
                        "type": "agent_output",
                        "timestamp": _ts(),
                        "phase": "consult",
                        "agent": "consultant",
                        "content": greeting,
                    })
                else:
                    history.append(HumanMessage(content=user_msg))

                    await websocket.send_json({
                        "type": "agent_thinking",
                        "timestamp": _ts(),
                        "phase": "consult",
                        "agent": "consultant",
                    })

                    text, is_ready, summary = await asyncio.to_thread(
                        consult_turn, list(history)
                    )

                    history.append(AIMessage(content=text))
                    session["consultant_ready"] = is_ready

                    metadata = {}
                    if is_ready:
                        metadata["consultant_ready"] = True
                        if summary:
                            session["consultant_summary"] = summary

                    # 剥离 JSON 块，展示友好格式
                    display_text = strip_summary_block(text, summary) if is_ready else text

                    await websocket.send_json({
                        "type": "agent_output",
                        "timestamp": _ts(),
                        "phase": "consult",
                        "agent": "consultant",
                        "content": display_text,
                        "metadata": metadata,
                    })

            elif action == "confirm_start":
                session = _sessions.get(session_id)
                if session is None:
                    await websocket.send_json({
                        "type": "error",
                        "timestamp": _ts(),
                        "content": "会话不存在",
                    })
                    continue

                task_id = session["task_id"]
                history = session.get("consultant_history", [])

                requirement = await asyncio.to_thread(
                    extract_requirement, list(history)
                )

                task_path = workspaces_dir() / task_id
                if task_path.exists():
                    save_requirement(task_path, requirement)

                await websocket.send_json({
                    "type": "phase_complete",
                    "timestamp": _ts(),
                    "phase": "consult",
                    "agent": "consultant",
                    "content": "需求收集完成",
                })

                user_request = requirement.get(
                    "raw_conversation_summary",
                    requirement.get("core_goal", task_id),
                )
                thread_id = str(uuid.uuid4())
                cfg = {"configurable": {"thread_id": thread_id}}
                graph = build_graph()

                session["graph"] = graph
                session["cfg"] = cfg

                await websocket.send_json({
                    "type": "phase_start",
                    "timestamp": _ts(),
                    "phase": "pending",
                    "content": "需求已确认，正在启动流水线...",
                })

                await _pump_graph_to_ws(
                    websocket,
                    graph,
                    {"task_id": task_id, "user_request": user_request, "_thread_id": thread_id},
                    cfg,
                )

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
