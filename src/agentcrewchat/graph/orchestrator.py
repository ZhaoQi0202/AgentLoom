"""DAG Orchestrator：按依赖关系调度多个 ReAct Agent 执行任务。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentcrewchat.graph.event_bus import emit_event
from agentcrewchat.graph.executor_identity import create_executor_identity
from agentcrewchat.graph.nodes.react_agent import run_react_agent
from agentcrewchat.graph.nodes.reviewer_agent import review_task
from agentcrewchat.tools.tool_registry import create_tools_for_task

MAX_AGENT_RETRY = 3


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _topological_sort(tasks: list[dict]) -> list[list[dict]]:
    """将任务按 DAG 依赖关系分层排序。

    返回: [[第一层任务], [第二层任务], ...]
    每层内的任务互相无依赖，可以并行执行。
    """
    task_map = {t["id"]: t for t in tasks}
    in_degree = {t["id"]: 0 for t in tasks}
    dependents: dict[str, list[str]] = {t["id"]: [] for t in tasks}

    for t in tasks:
        for dep in t.get("depends_on", []):
            if dep in task_map:
                in_degree[t["id"]] += 1
                dependents[dep].append(t["id"])

    layers = []
    remaining = set(in_degree.keys())

    while remaining:
        # 找出入度为 0 的任务
        ready = [tid for tid in remaining if in_degree[tid] == 0]
        if not ready:
            # 有循环依赖，把剩余的都放一层
            ready = list(remaining)
        layer = [task_map[tid] for tid in ready]
        layers.append(layer)
        for tid in ready:
            remaining.discard(tid)
            for dep_id in dependents.get(tid, []):
                in_degree[dep_id] -= 1

    return layers


def _save_task_output(workspace: Path, task_id: str, result: dict) -> None:
    """保存单个任务的执行结果到 workspace。"""
    output_dir = workspace / "task_outputs"
    output_dir.mkdir(exist_ok=True)
    fp = output_dir / f"{task_id}.json"
    fp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def run_orchestration(
    blueprint: dict,
    workspace: Path,
    thread_id: str = "",
) -> list[dict[str, Any]]:
    """按 DAG 依赖关系执行所有任务。

    Args:
        blueprint: 架构师生成的任务规划（含 tasks 列表）
        workspace: 项目组工作目录
        thread_id: event_bus 路由 ID

    Returns:
        所有任务的执行结果列表
    """
    tasks = blueprint.get("tasks", [])
    if not tasks:
        emit_event(thread_id, {
            "type": "agent_output",
            "timestamp": _ts(),
            "phase": "experts",
            "agent": "experts",
            "content": "蓝图里没有任务，没啥好干的 🤷",
        })
        return []

    layers = _topological_sort(tasks)
    all_results: list[dict] = []
    completed_tasks: dict[str, dict] = {}
    used_names: set[str] = set()
    used_colors: set[str] = set()

    emit_event(thread_id, {
        "type": "agent_join",
        "timestamp": _ts(),
        "phase": "experts",
        "agent": "experts",
    })
    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "experts",
        "agent": "experts",
        "content": f"开始执行！一共 {len(tasks)} 个任务，分 {len(layers)} 层依次推进",
    })

    for layer_idx, layer in enumerate(layers):
        if len(layer) > 1:
            names = "、".join(t["name"] for t in layer)
            emit_event(thread_id, {
                "type": "agent_output",
                "timestamp": _ts(),
                "phase": "experts",
                "agent": "experts",
                "content": f"📋 第 {layer_idx + 1} 层：{names}（这些任务可以并行，当前逐个执行）",
            })

        for task in layer:
            task_id = task["id"]
            task_name = task.get("name", task_id)
            task_goal = task.get("goal", "")
            criteria = task.get("acceptance_criteria", [])
            tool_ids = task.get("tools", [])
            deps = task.get("depends_on", [])

            # 创建执行 Agent 身份
            identity = create_executor_identity(task_id, used_names, used_colors)

            # @上游 Agent 互动
            if deps:
                dep_executor_names = [
                    completed_tasks[d]["executor_name"]
                    for d in deps if d in completed_tasks and completed_tasks[d].get("executor_name")
                ]
                if dep_executor_names:
                    mentions = "、".join(f"@{n}" for n in dep_executor_names)
                    emit_event(thread_id, {
                        "type": "agent_output",
                        "timestamp": _ts(),
                        "phase": "experts",
                        "agent": "experts",
                        "agent_name": identity.name,
                        "agent_color": identity.color,
                        "content": f"{mentions} 的产出我看到了，接下来轮到我「{task_name}」了！",
                        "metadata": {"agent_name": identity.name, "task_id": task_id},
                    })

            # 创建工具
            tools = create_tools_for_task(tool_ids, workspace, task_id=task_id)

            # 执行 + 审核 + 重试循环
            retry_feedback = None
            final_result = None
            review_passed = False

            for attempt in range(MAX_AGENT_RETRY + 1):
                result = run_react_agent(
                    task_id=task_id,
                    task_name=task_name,
                    task_goal=task_goal,
                    acceptance_criteria=criteria,
                    tools=tools,
                    workspace_path=str(workspace),
                    thread_id=thread_id,
                    retry_feedback=retry_feedback,
                    executor_name=identity.name,
                    executor_color=identity.color,
                    executor_personality_prompt=identity.personality_prompt,
                )
                final_result = result

                # 如果 Agent 本身出错，不审核直接跳过
                if result["status"] == "error":
                    break

                # 审核
                review_passed, review_msg = review_task(
                    task_id=task_id,
                    task_name=task_name,
                    task_goal=task_goal,
                    acceptance_criteria=criteria,
                    agent_output=result["output"],
                    thread_id=thread_id,
                )

                if review_passed:
                    break

                # 审核不通过，检查是否还有重试次数
                if attempt < MAX_AGENT_RETRY:
                    retry_feedback = review_msg
                    emit_event(thread_id, {
                        "type": "agent_output",
                        "timestamp": _ts(),
                        "phase": "experts",
                        "agent": "experts",
                        "agent_name": identity.name,
                        "agent_color": identity.color,
                        "content": f"🔄 任务「{task_name}」审核未通过（第 {attempt + 1}/{MAX_AGENT_RETRY} 次），根据反馈重新执行...",
                        "metadata": {"agent_name": identity.name, "task_id": task_id},
                    })

            # 记录最终结果
            final_result["review_passed"] = review_passed
            final_result["retry_count"] = min(attempt, MAX_AGENT_RETRY) if final_result["status"] != "error" else 0
            final_result["executor_name"] = identity.name
            completed_tasks[task_id] = final_result
            all_results.append(final_result)

            # 保存单个任务结果
            _save_task_output(workspace, task_id, final_result)

            # 通知完成状态
            if review_passed:
                emit_event(thread_id, {
                    "type": "agent_output",
                    "timestamp": _ts(),
                    "phase": "experts",
                    "agent": "experts",
                    "agent_name": identity.name,
                    "agent_color": identity.color,
                    "content": f"✅ 任务「{task_name}」执行完毕并通过审核！（工具调用: {final_result['tool_calls_count']}次）",
                    "metadata": {"agent_name": identity.name, "task_id": task_id},
                })
            else:
                emit_event(thread_id, {
                    "type": "agent_output",
                    "timestamp": _ts(),
                    "phase": "experts",
                    "agent": "experts",
                    "agent_name": identity.name,
                    "agent_color": identity.color,
                    "content": f"⚠️ 任务「{task_name}」经过 {MAX_AGENT_RETRY} 次重试仍未通过审核，先记录结果继续推进",
                    "metadata": {"agent_name": identity.name, "task_id": task_id},
                })

    # 汇总
    passed_count = sum(1 for r in all_results if r.get("review_passed"))
    total = len(all_results)
    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "experts",
        "agent": "experts",
        "content": f"🎯 所有任务执行完毕！{passed_count}/{total} 个任务通过审核",
    })

    return all_results
