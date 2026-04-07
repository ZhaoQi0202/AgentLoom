from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agentloom.graph.nodes.architect_agent import generate_blueprint, format_blueprint_message
from agentloom.graph.orchestrator import run_orchestration
from agentloom.graph.state import AgentLoomState
from agentloom.llm.factory import get_chat_model
from agentloom.paths import workspaces_dir
from agentloom.tasks.blueprint import load_blueprint, save_blueprint
from agentloom.tasks.requirement import load_requirement


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM 获取回复。"""
    llm = get_chat_model()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    resp = llm.invoke(messages)
    return resp.content


def consultant(state: AgentLoomState) -> dict[str, Any]:
    """需求分析师：传递已收集的需求摘要（实际对话在 WebSocket collect 阶段完成）。"""
    summary = state.get("user_request", "未提供任务描述")
    return {
        "phase": "consult",
        "consult_confidence": 1.0,
        "consult_summary": summary,
        "message": summary,
    }


def architect(state: AgentLoomState) -> dict[str, Any]:
    """架构设计师：读取需求和可用工具，生成 DAG 任务规划。"""
    task_id = state.get("task_id", "")
    task_path = workspaces_dir() / task_id if task_id else None

    # 读取结构化需求
    requirement = None
    if task_path and task_path.exists():
        requirement = load_requirement(task_path)
    if not requirement:
        requirement = {
            "core_goal": state.get("user_request", ""),
            "raw_conversation_summary": state.get("consult_summary", ""),
        }

    # 生成 blueprint
    message, blueprint = generate_blueprint(requirement, task_path)

    # 保存 blueprint.json 到 workspace
    if blueprint and task_path and task_path.exists():
        save_blueprint(task_path, blueprint)

    display_message = format_blueprint_message(message, blueprint)

    return {
        "phase": "architect",
        "blueprint": blueprint or {"raw": message},
        "architect_gap_notes": "",
        "message": display_message,
    }


def hitl_blueprint(state: AgentLoomState) -> dict[str, Any]:
    """方案审核员：展示架构师的任务规划，等待人工审核。"""
    blueprint = state.get("blueprint", {})
    tasks = blueprint.get("tasks", []) if isinstance(blueprint, dict) else []

    if tasks:
        summary_lines = ["架构师的任务规划如下：\n"]
        for t in tasks:
            deps = ", ".join(t.get("depends_on", [])) or "无"
            tools = ", ".join(t.get("tools", []))
            summary_lines.append(
                f"  [{t.get('id', '?')}] {t.get('name', '?')} — {t.get('goal', '')}\n"
                f"    工具: {tools} | 依赖: {deps}"
            )
        summary_lines.append("\n确认没问题回复「继续」，需要调整请说明修改意见。")
        msg = "\n".join(summary_lines)
    else:
        msg = "方案已提交，请审核上面架构设计师的方案。确认无误回复「继续」，需要调整请说明修改意见。"

    return {
        "phase": "hitl_blueprint",
        "message": msg,
    }


def experts(state: AgentLoomState) -> dict[str, Any]:
    """执行专家组：根据蓝图调度多个 ReAct Agent 执行任务。"""
    task_id = state.get("task_id", "")
    thread_id = state.get("_thread_id", "")
    blueprint = state.get("blueprint", {})
    workspace = workspaces_dir() / task_id if task_id else None

    # 如果 blueprint 没有 tasks 字段，尝试从 workspace 加载
    if not blueprint.get("tasks") and workspace and workspace.exists():
        loaded = load_blueprint(workspace)
        if loaded:
            blueprint = loaded

    if not blueprint.get("tasks"):
        return {
            "phase": "experts",
            "expert_runs": [{"swarm_output": "蓝图中没有可执行的任务"}],
            "message": "蓝图中没有可执行的任务",
        }

    # 运行 DAG Orchestrator
    results = run_orchestration(
        blueprint=blueprint,
        workspace=workspace,
        thread_id=thread_id,
    )

    # 汇总结果
    expert_runs = []
    summary_lines = []
    for r in results:
        expert_runs.append({
            "task_id": r["task_id"],
            "task_name": r["task_name"],
            "status": r["status"],
            "swarm_output": r["output"],
            "tool_calls_count": r["tool_calls_count"],
        })
        status_emoji = "✅" if r["status"] == "completed" else "⚠️"
        summary_lines.append(f"{status_emoji} {r['task_name']}: {r['status']}")

    completed = sum(1 for r in results if r["status"] == "completed")
    message = f"执行完毕！{completed}/{len(results)} 个任务完成\n" + "\n".join(summary_lines)

    return {
        "phase": "experts",
        "expert_runs": expert_runs,
        "message": message,
    }


def reviewer(state: AgentLoomState) -> dict[str, Any]:
    """质量审查员：最终汇总审核，处理失败任务的降级决策。"""
    expert_runs = state.get("expert_runs", [])
    r = int(state.get("review_round", 0))

    passed_tasks = []
    failed_tasks = []
    for run in expert_runs:
        if isinstance(run, dict):
            name = run.get("task_name", run.get("task_id", "?"))
            if run.get("review_passed"):
                passed_tasks.append(name)
            else:
                failed_tasks.append(name)

    total = len(passed_tasks) + len(failed_tasks)

    if not failed_tasks:
        # 全部通过
        message = (
            f"🎉 全部 {total} 个任务都通过审核了！交付质量没问题，"
            f"可以收工了~ PASS"
        )
        verdict = "pass"
    else:
        # 有失败任务
        failed_list = "、".join(failed_tasks)
        passed_list = "、".join(passed_tasks) if passed_tasks else "无"
        message = (
            f"📊 最终审核报告：\n"
            f"  通过（{len(passed_tasks)}）: {passed_list}\n"
            f"  未通过（{len(failed_tasks)}）: {failed_list}\n\n"
            f"有 {len(failed_tasks)} 个任务未通过审核，"
            f"你可以选择：\n"
            f"  1. 回复「接受」— 接受当前结果继续\n"
            f"  2. 回复「重做」— 让架构师重新设计失败的任务点\n"
            f"NEEDS_REVISION"
        )
        verdict = "needs_revision"

    return {
        "phase": "review",
        "review_round": r + 1,
        "review_verdict": verdict,
        "message": message,
    }
