from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agentloom.graph.builder import build_graph
from agentloom.ui.worker import split_stream_chunk
from langgraph.types import Command

router = APIRouter(tags=["graph"])

# 活跃的图谱会话（session_id -> graph + config）
_sessions: dict[str, dict[str, Any]] = {}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_graph_stream(graph: Any, input_obj: Any, cfg: dict) -> list[dict]:
    """同步运行图谱流并收集事件。"""
    events: list[dict] = []
    for chunk in graph.stream(input_obj, cfg, stream_mode="updates"):
        parts, has_interrupt = split_stream_chunk(chunk)
        for node, upd in parts:
            phase = upd.get("phase", node)
            # 先发阶段切换事件
            events.append({
                "type": "phase_start",
                "timestamp": _ts(),
                "phase": phase,
                "agent": node,
                "content": f"阶段: {node}",
            })
            # 优先使用节点返回的 message 字段作为对话内容
            content = upd.get("message") or json.dumps(upd, ensure_ascii=False, default=str)
            events.append({
                "type": "agent_output",
                "timestamp": _ts(),
                "phase": phase,
                "agent": node,
                "content": content,
            })
        if has_interrupt:
            st = graph.get_state(cfg)
            nxt = st.next[0] if st.next else ""
            # 获取最近节点的 message 作为中断说明
            interrupt_msg = f"图谱在 {nxt} 阶段中断，等待人工输入"
            events.append({
                "type": "hitl_interrupt",
                "timestamp": _ts(),
                "phase": nxt,
                "agent": nxt,
                "content": interrupt_msg,
            })
            return events
    events.append({
        "type": "task_complete",
        "timestamp": _ts(),
        "content": "任务完成",
    })
    return events


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
                thread_id = str(uuid.uuid4())
                cfg = {"configurable": {"thread_id": thread_id}}
                graph = build_graph()

                # 在线程池中运行同步的图谱流
                events = await asyncio.to_thread(
                    _run_graph_stream, graph, {"task_id": task_id}, cfg
                )
                for event in events:
                    await websocket.send_json(event)

                # 保存会话供后续 resume
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

                events = await asyncio.to_thread(
                    _run_graph_stream, graph, resume_input, cfg
                )
                for event in events:
                    await websocket.send_json(event)

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
