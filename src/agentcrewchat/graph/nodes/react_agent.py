"""ReAct Agent 执行器：思考→调用工具→观察→重复，直到任务完成。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from agentcrewchat.graph.event_bus import emit_event
from agentcrewchat.graph.pause_manager import wait_if_paused
from agentcrewchat.llm.factory import get_chat_model

# 连续无进展轮数上限（既没调工具也没产出新内容）
_STALL_LIMIT = 3


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_tool_result(stdout: str) -> str:
    """截断过长的工具输出。"""
    if len(stdout) > 2000:
        return stdout[:1000] + "\n...(输出截断)...\n" + stdout[-500:]
    return stdout


def run_react_agent(
    task_id: str,
    task_name: str,
    task_goal: str,
    acceptance_criteria: list[str],
    tools: list[BaseTool],
    workspace_path: str,
    thread_id: str = "",
    retry_feedback: str | None = None,
    executor_name: str = "",
    executor_color: str = "",
    executor_personality_prompt: str = "",
    checkpoints: list[str] | None = None,
) -> dict[str, Any]:
    """运行一个 ReAct Agent 完成指定任务。

    通过 event_bus 实时推送执行进展到前端。
    无最大迭代上限，由 LLM 自行判断何时完成。

    返回:
        {
            "task_id": str,
            "task_name": str,
            "status": "completed" | "stalled" | "error",
            "output": str,
            "tool_calls_count": int,
            "executor_name": str,
        }
    """
    display_name = executor_name or task_name

    criteria_text = "\n".join(f"  - {c}" for c in acceptance_criteria) if acceptance_criteria else "  - 无特定标准"

    system_prompt = (
        f"你是一个执行专家，正在项目群聊中完成分配给你的任务。\n\n"
        f"## 你的任务\n"
        f"任务名称: {task_name}\n"
        f"任务目标: {task_goal}\n"
        f"验收标准:\n{criteria_text}\n\n"
        f"## 工作目录\n"
        f"{workspace_path}\n\n"
        f"## 工作规则\n"
        f"1. 使用提供的工具来完成任务\n"
        f"2. 每次只做一步操作，观察结果后再决定下一步\n"
        f"3. 完成任务后，用简洁的话总结你做了什么、产出了什么文件或结果\n"
        f"4. 如果遇到问题，先尝试解决，实在不行再说明情况\n"
        f"5. 不要使用 Markdown 标题格式，像在工作群里汇报一样说话\n"
        f"6. 总结时说做了什么和结果，不要罗列工具调用细节\n"
    )

    if checkpoints:
        cp_list = "\n".join(f"  - {cp}" for cp in checkpoints)
        system_prompt += (
            f"\n## 汇报节点\n"
            f"架构师要求你在以下节点完成时在群里汇报进度：\n{cp_list}\n"
            f"到达这些节点时，用一句话说明完成情况。\n"
        )

    if executor_personality_prompt:
        system_prompt += f"\n\n## 你的性格\n{executor_personality_prompt}\n"

    if retry_feedback:
        system_prompt += (
            f"\n## ⚠️ 重要：上一次执行未通过审核\n"
            f"审核反馈：{retry_feedback}\n"
            f"请根据反馈改进你的实现。\n"
        )

    messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请开始执行任务「{task_name}」"),
    ]

    llm = get_chat_model(phase="execute")
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    tool_map = {t.name: t for t in tools}
    total_tool_calls = 0

    # 构建 emit_event 通用字段
    _ev = {"agent_name": display_name, "task_id": task_id}

    # 发送开始事件
    start_msg = (
        f"收到审核反馈，重新修改「{task_name}」🔧" if retry_feedback
        else f"收到任务「{task_name}」，马上开始搞！💪"
    )
    emit_event(thread_id, {
        "type": "agent_output",
        "timestamp": _ts(),
        "phase": "execute",
        "agent_name": display_name,
        "agent_color": executor_color,
        "content": start_msg,
        "metadata": _ev,
    })

    stall_count = 0
    prev_content = ""

    while True:
        # 暂停检查：每轮 ReAct 迭代前检查
        wait_if_paused(thread_id)

        try:
            response = llm_with_tools.invoke(messages)
        except Exception as e:
            emit_event(thread_id, {
                "type": "agent_output",
                "timestamp": _ts(),
                "phase": "execute",
                "agent_name": display_name,
                "agent_color": executor_color,
                "content": f"呃...出了点问题: {e}",
                "metadata": _ev,
            })
            return {
                "task_id": task_id,
                "task_name": task_name,
                "status": "error",
                "output": str(e),
                "tool_calls_count": total_tool_calls,
                "executor_name": display_name,
            }

        messages.append(response)

        # 检查是否有工具调用
        if not hasattr(response, "tool_calls") or not response.tool_calls:
            # Agent 完成了，输出最终回复
            final_output = response.content or "任务完成"

            # 检查是否真的完成了（有新内容），还是在空转
            if final_output == prev_content:
                stall_count += 1
                if stall_count >= _STALL_LIMIT:
                    emit_event(thread_id, {
                        "type": "agent_output",
                        "timestamp": _ts(),
                        "phase": "execute",
                        "agent_name": display_name,
                        "agent_color": executor_color,
                        "content": final_output,
                        "metadata": _ev,
                    })
                    return {
                        "task_id": task_id,
                        "task_name": task_name,
                        "status": "stalled",
                        "output": final_output,
                        "tool_calls_count": total_tool_calls,
                        "executor_name": display_name,
                    }
                continue
            else:
                prev_content = final_output

            emit_event(thread_id, {
                "type": "agent_output",
                "timestamp": _ts(),
                "phase": "execute",
                "agent_name": display_name,
                "agent_color": executor_color,
                "content": final_output,
                "metadata": _ev,
            })
            return {
                "task_id": task_id,
                "task_name": task_name,
                "status": "completed",
                "output": final_output,
                "tool_calls_count": total_tool_calls,
                "executor_name": display_name,
            }

        # 执行工具调用（静默，不推送到群聊）
        stall_count = 0
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            total_tool_calls += 1

            tool_fn = tool_map.get(tool_name)
            if tool_fn:
                try:
                    result = tool_fn.invoke(tool_args)
                    result_str = _format_tool_result(str(result))
                except Exception as e:
                    result_str = f"工具执行失败: {e}"
            else:
                result_str = f"未知工具: {tool_name}"

            messages.append(ToolMessage(
                content=result_str,
                tool_call_id=tool_call["id"],
            ))
