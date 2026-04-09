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

from agentcrewchat.graph.builder import build_graph
from agentcrewchat.graph.stream_util import split_stream_chunk
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Command

from agentcrewchat.graph.nodes.consultant_agent import (
    CONSULTANT_SYSTEM_PROMPT,
    build_initial_greeting,
    consult_turn,
    extract_requirement,
    strip_summary_block,
)
from agentcrewchat.graph.nodes.user_confirmation import is_user_confirmation
from agentcrewchat.paths import workspaces_dir
from agentcrewchat.tasks.requirement import save_requirement

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
                "type": "agent_join",
                "timestamp": _ts(),
                "phase": phase,
                "agent": node,
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

    from agentcrewchat.graph.event_bus import register_queue, register_thread_task, unregister_queue
    from agentcrewchat.graph.pause_manager import cleanup as pause_cleanup, create_pause_signal
    register_queue(thread_id, q)

    # 关联 thread_id → task_id 用于聊天历史持久化
    task_id = input_obj.get("task_id", "") if isinstance(input_obj, dict) else ""
    if task_id:
        register_thread_task(thread_id, task_id)

    # 创建暂停信号
    create_pause_signal(thread_id)

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
            pause_cleanup(thread_id)
            q.put(_SENTINEL)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = await asyncio.to_thread(q.get)
        if item is _SENTINEL:
            break
        await websocket.send_json(item)


async def _run_pipeline_after_confirm(
    websocket: WebSocket, session: dict[str, Any]
) -> None:
    task_id = session["task_id"]
    history = session.get("consultant_history", [])

    requirement = await asyncio.to_thread(extract_requirement, list(history))

    task_path = workspaces_dir() / task_id
    if task_path.exists():
        save_requirement(task_path, requirement)

    user_request = requirement.get(
        "raw_conversation_summary",
        requirement.get("core_goal", task_id),
    )
    thread_id_new = str(uuid.uuid4())
    cfg_new = {"configurable": {"thread_id": thread_id_new}}
    graph_new = build_graph()

    session["graph"] = graph_new
    session["cfg"] = cfg_new
    session["thread_id"] = thread_id_new
    session["consultant_ready"] = False

    summary_dict = session.get("consultant_summary")

    if summary_dict and isinstance(summary_dict, dict):
        project_name = summary_dict.get("project_name") or "本项目"
        core_goal = summary_dict.get("core_goal", "")
        features = summary_dict.get("features", [])
        constraints = summary_dict.get("constraints", {}) or {}
        tech_stack = constraints.get("tech_stack", []) if isinstance(constraints, dict) else []

        lines = [f"@架构设计师 需求分析完成，把「{project_name}」的设计工作交给你了！"]
        if core_goal:
            lines.append(f"核心目标：{core_goal}")
        if features:
            priority_map = {"must": "必须", "should": "应该", "nice_to_have": "可选"}
            feature_parts = []
            for f in features:
                if isinstance(f, dict):
                    name = f.get("name", "")
                    p = priority_map.get(f.get("priority", ""), "")
                    feature_parts.append(f"{name}（{p}）" if p else name)
            if feature_parts:
                lines.append(f"功能点：{'、'.join(feature_parts)}")
        if tech_stack:
            lines.append(f"技术栈：{'、'.join(tech_stack)}")
        lines.append("辛苦了～有啥问题随时说 🎯")
        handoff = "\n".join(lines)
    else:
        handoff = "@架构设计师 需求确认完成，转交给你推进设计了！辛苦～ 🎯"

    await websocket.send_json({
        "type": "agent_join",
        "timestamp": _ts(),
        "phase": "architect",
        "agent": "architect",
    })
    await websocket.send_json({
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "consult",
        "agent": "consultant",
        "content": handoff,
    })

    await _pump_graph_to_ws(
        websocket,
        graph_new,
        {"task_id": task_id, "user_request": user_request, "_thread_id": thread_id_new},
        cfg_new,
    )


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

                _sessions[session_id] = {"graph": graph, "cfg": cfg, "thread_id": thread_id}

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
                        "type": "agent_join",
                        "timestamp": _ts(),
                        "phase": "consult",
                        "agent": "consultant",
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

                    if session.get("consultant_ready") and is_user_confirmation(user_msg):
                        await _run_pipeline_after_confirm(websocket, session)
                        continue

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

                    if is_ready and summary:
                        session["consultant_summary"] = summary

                    display_text = strip_summary_block(text, summary)

                    await websocket.send_json({
                        "type": "agent_output",
                        "timestamp": _ts(),
                        "phase": "consult",
                        "agent": "consultant",
                        "content": display_text,
                    })

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

            elif action == "resume_pause":
                from agentcrewchat.graph.pause_manager import resume as pm_resume
                session = _sessions.get(session_id)
                if session and session.get("thread_id"):
                    pm_resume(session["thread_id"])

            elif action == "decision":
                from agentcrewchat.graph.decision_handler import submit_decision, classify_user_input
                session = _sessions.get(session_id)
                decision_type = msg.get("decision", "")
                user_text = msg.get("message", "")
                thread_id = session.get("thread_id", "") if session else ""

                if decision_type in ("skip", "reroute", "terminate"):
                    submit_decision(thread_id, decision_type)
                elif user_text:
                    can_reroute = not session.get("_can_rerouted", False) if session else True
                    decision_type = classify_user_input(user_text, can_reroute)
                    submit_decision(thread_id, decision_type)

            elif action == "confirm_start":
                session = _sessions.get(session_id)
                if session is None:
                    await websocket.send_json({
                        "type": "error",
                        "timestamp": _ts(),
                        "content": "会话不存在",
                    })
                    continue

                await _run_pipeline_after_confirm(websocket, session)

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
