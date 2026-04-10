"""DAG Orchestrator：按依赖关系调度多个 ReAct Agent 执行任务。"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentcrewchat.graph.decision_handler import (
    generate_review_limit_message,
    wait_for_decision,
)
from agentcrewchat.graph.event_bus import emit_event
from agentcrewchat.graph.executor_identity import ExecutorIdentity, create_executor_identity
from agentcrewchat.graph.nodes.react_agent import run_react_agent
from agentcrewchat.graph.nodes.reviewer_agent import review_task
from agentcrewchat.graph.pause_manager import wait_if_paused
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
        ready = [tid for tid in remaining if in_degree[tid] == 0]
        if not ready:
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


def _reroute_task(
    task: dict,
    review_msg: str,
    result: dict,
    workspace: Path,
    thread_id: str,
) -> dict | None:
    """让架构师为失败任务生成替代方案。"""
    from agentcrewchat.graph.nodes.architect_agent import generate_blueprint

    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "execute",
        "agent": "architect",
        "content": f"收到，「{task.get('name')}」没跑通，我来看看怎么调整方案 🔧",
    })

    reroute_requirement = {
        "core_goal": task.get("goal", ""),
        "failure_context": {
            "original_task": task,
            "execution_output": result.get("output", ""),
            "review_feedback": review_msg,
            "guidance": "请为这个任务设计替代方案，更换工具或思路，保持 task_id 不变。",
        },
    }

    _, blueprint = generate_blueprint(reroute_requirement, workspace)
    if blueprint and blueprint.get("tasks"):
        new_task = blueprint["tasks"][0]
        new_task["id"] = task.get("id")
        return new_task
    return None


def _execute_single_task(
    task: dict,
    identity: ExecutorIdentity,
    blueprint: dict,
    workspace: Path,
    thread_id: str,
    completed_tasks: dict[str, dict],
) -> dict:
    """执行单个任务（含审核+重试循环）。线程安全。"""
    task_id = task["id"]
    task_name = task.get("name", task_id)
    task_goal = task.get("goal", "")
    criteria = task.get("acceptance_criteria", [])
    checkpoints = task.get("checkpoints", [])
    tool_ids = task.get("tools", [])
    deps = task.get("depends_on", [])

    # 暂停检查
    wait_if_paused(thread_id)

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
                "phase": "execute",
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
    review_msg = ""

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
            checkpoints=checkpoints,
        )
        final_result = result

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

        if attempt < MAX_AGENT_RETRY:
            retry_feedback = review_msg
            emit_event(thread_id, {
                "type": "agent_output",
                "timestamp": _ts(),
                "phase": "execute",
                "agent_name": identity.name,
                "agent_color": identity.color,
                "content": f"🔄 任务「{task_name}」审核未通过（第 {attempt + 1}/{MAX_AGENT_RETRY} 次），根据反馈重新执行...",
                "metadata": {"agent_name": identity.name, "task_id": task_id},
            })

    # 记录最终结果
    final_result["review_passed"] = review_passed
    final_result["retry_count"] = min(attempt, MAX_AGENT_RETRY) if final_result["status"] != "error" else 0
    final_result["executor_name"] = identity.name

    # 审核结果处理
    if review_passed:
        emit_event(thread_id, {
            "type": "agent_output",
            "timestamp": _ts(),
            "phase": "execute",
            "agent_name": identity.name,
            "agent_color": identity.color,
            "content": f"✅ 任务「{task_name}」执行完毕并通过审核！",
            "metadata": {"agent_name": identity.name, "task_id": task_id},
        })
    elif task.get("_rerouted"):
        can_reroute = False
        limit_msg = generate_review_limit_message(task_name, task_goal, review_msg or "")
        emit_event(thread_id, {
            "type": "agent_output",
            "timestamp": _ts(),
            "phase": "review",
            "agent": "reviewer",
            "content": f"🔍 @{identity.name} 重规划后仍未通过：\n{limit_msg}",
            "metadata": {
                "task_id": task_id,
                "verdict": "over_limit",
                "quick_replies": ["跳过继续", "终止执行"],
            },
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
        if decision == "terminate":
            final_result["_terminate"] = True
    else:
        limit_msg = generate_review_limit_message(task_name, task_goal, review_msg or "")
        emit_event(thread_id, {
            "type": "agent_output",
            "timestamp": _ts(),
            "phase": "review",
            "agent": "reviewer",
            "content": f"🔍 @{identity.name} 审核未通过（{MAX_AGENT_RETRY} 次上限）：\n{limit_msg}",
            "metadata": {
                "task_id": task_id,
                "verdict": "over_limit",
                "quick_replies": ["跳过继续", "交还明哲", "终止执行"],
            },
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
        if decision == "terminate":
            final_result["_terminate"] = True
        elif decision == "reroute":
            task["_rerouted"] = True
            new_task = _reroute_task(
                task=task,
                review_msg=review_msg or "",
                result=final_result,
                workspace=workspace,
                thread_id=thread_id,
            )
            if new_task:
                for i, t in enumerate(blueprint["tasks"]):
                    if t["id"] == task_id:
                        blueprint["tasks"][i] = new_task
                        break
                rerouted_result = run_react_agent(
                    task_id=task_id,
                    task_name=new_task.get("name", task_name),
                    task_goal=new_task.get("goal", task_goal),
                    acceptance_criteria=new_task.get("acceptance_criteria", criteria),
                    tools=create_tools_for_task(new_task.get("tools", tool_ids), workspace, task_id=task_id),
                    workspace_path=str(workspace),
                    thread_id=thread_id,
                    retry_feedback=review_msg,
                    executor_name=identity.name,
                    executor_color=identity.color,
                    executor_personality_prompt=identity.personality_prompt,
                )
                final_result = rerouted_result
                final_result["executor_name"] = identity.name

                if rerouted_result["status"] != "error":
                    rerouted_passed, rerouted_msg = review_task(
                        task_id=task_id,
                        task_name=new_task.get("name", task_name),
                        task_goal=new_task.get("goal", task_goal),
                        acceptance_criteria=new_task.get("acceptance_criteria", criteria),
                        agent_output=rerouted_result["output"],
                        thread_id=thread_id,
                    )
                    if rerouted_passed:
                        final_result["review_passed"] = True
                        emit_event(thread_id, {
                            "type": "agent_output",
                            "timestamp": _ts(),
                            "phase": "execute",
                            "agent_name": identity.name,
                            "agent_color": identity.color,
                            "content": f"✅ 任务「{task_name}」重规划后执行完毕并通过审核！",
                            "metadata": {"agent_name": identity.name, "task_id": task_id},
                        })
                    else:
                        final_result["review_passed"] = False
                else:
                    final_result["review_passed"] = False
            else:
                emit_event(thread_id, {
                    "type": "agent_output",
                    "timestamp": _ts(),
                    "phase": "execute",
                    "agent_name": identity.name,
                    "agent_color": identity.color,
                    "content": f"⚠️ 架构师未能为「{task_name}」生成替代方案，跳过继续",
                    "metadata": {"agent_name": identity.name, "task_id": task_id},
                })

    return final_result


def run_orchestration(
    blueprint: dict,
    workspace: Path,
    thread_id: str = "",
) -> list[dict[str, Any]]:
    """按 DAG 依赖关系执行所有任务。"""
    tasks = blueprint.get("tasks", [])
    if not tasks:
        return []

    layers = _topological_sort(tasks)
    all_results: list[dict] = []
    completed_tasks: dict[str, dict] = {}
    used_names: set[str] = set()
    used_colors: set[str] = set()

    # 预创建所有执行 Agent 身份
    task_identities: dict[str, ExecutorIdentity] = {}
    for task in tasks:
        task_identities[task["id"]] = create_executor_identity(task["id"], used_names, used_colors)

    # 批量入群：所有执行 Agent 同时加入
    for task in tasks:
        ident = task_identities[task["id"]]
        emit_event(thread_id, {
            "type": "agent_join",
            "timestamp": _ts(),
            "phase": "execute",
            "agent_name": ident.name,
            "agent_color": ident.color,
            "metadata": {"task_id": task["id"], "task_name": task.get("name", task["id"])},
        })

    # 明哲发任务分配消息：@每个小某分配任务和汇报节点
    assignment_lines = []
    for task in tasks:
        ident = task_identities[task["id"]]
        task_name = task.get("name", task["id"])
        checkpoints = task.get("checkpoints", [])
        cp_text = ""
        if checkpoints:
            cp_items = "、".join(f"「{cp}」" for cp in checkpoints)
            cp_text = f"，到这些节点时在群里汇报：{cp_items}"
        assignment_lines.append(f"@{ident.name} 你负责「{task_name}」{cp_text}")
    assignment_msg = "任务分配如下，各位开始吧！💪\n\n" + "\n".join(assignment_lines)
    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "execute",
        "agent": "architect",
        "content": assignment_msg,
    })

    # 按层执行
    for layer_idx, layer in enumerate(layers):
        if len(layer) == 1:
            # 单任务，直接执行
            task = layer[0]
            identity = task_identities[task["id"]]
            result = _execute_single_task(
                task, identity, blueprint, workspace, thread_id, completed_tasks,
            )
            completed_tasks[task["id"]] = result
            all_results.append(result)
            _save_task_output(workspace, task["id"], result)
            if result.get("_terminate"):
                return all_results
        else:
            # 同层并行执行
            with ThreadPoolExecutor(max_workers=len(layer)) as pool:
                futures = {}
                for task in layer:
                    identity = task_identities[task["id"]]
                    f = pool.submit(
                        _execute_single_task,
                        task, identity, blueprint, workspace, thread_id, completed_tasks,
                    )
                    futures[f] = task
                for f in as_completed(futures):
                    task = futures[f]
                    result = f.result()
                    completed_tasks[task["id"]] = result
                    all_results.append(result)
                    _save_task_output(workspace, task["id"], result)
                    if result.get("_terminate"):
                        # 取消其他 futures
                        for other_f in futures:
                            other_f.cancel()
                        return all_results

    # 汇总
    passed_count = sum(1 for r in all_results if r.get("review_passed"))
    total = len(all_results)
    # 找第一个 agent 来发汇总消息
    first_ident = task_identities[tasks[0]["id"]]
    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "execute",
        "agent_name": first_ident.name,
        "agent_color": first_ident.color,
        "content": f"🎯 所有任务执行完毕！{passed_count}/{total} 个任务通过审核",
    })

    return all_results
