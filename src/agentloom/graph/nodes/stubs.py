from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agentloom.graph.state import AgentLoomState
from agentloom.llm.factory import get_chat_model


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
    """需求分析师：分析用户需求，输出简短摘要。"""
    user_request = state.get("user_request", "未提供任务描述")

    system = (
        "你是需求分析师。在一个项目群聊中，你的职责是快速分析用户需求并给出简短总结。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格回复，不要使用 Markdown 标题格式\n"
        "- 直接说重点：需求概要、关键风险、明确度评估\n"
        "- 像在工作群里给同事发消息一样说话\n"
    )
    user = f"请分析这个需求：{user_request}"

    message = _call_llm(system, user)

    return {
        "phase": "consult",
        "consult_confidence": 0.9,
        "consult_summary": message,
        "message": message,
    }


def architect(state: AgentLoomState) -> dict[str, Any]:
    """架构设计师：基于需求分析设计技术方案。"""
    user_request = state.get("user_request", "")
    consult_summary = state.get("consult_summary", "")

    system = (
        "你是架构设计师。在一个项目群聊中，你的职责是给出简洁的技术方案。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格，不要使用 Markdown 标题格式\n"
        "- 直接说：技术选型 + 核心步骤（3-5步，每步一句话）\n"
        "- 像在工作群里给同事发消息一样说话\n"
    )
    user = f"需求：{user_request}\n分析：{consult_summary}\n请给出技术方案。"

    message = _call_llm(system, user)

    return {
        "phase": "architect",
        "blueprint": {"raw": message},
        "architect_gap_notes": "",
        "message": message,
    }


def hitl_blueprint(state: AgentLoomState) -> dict[str, Any]:
    """方案审核员：等待人工审核蓝图。"""
    return {
        "phase": "hitl_blueprint",
        "message": "方案已提交，请审核上面架构设计师的方案。确认无误回复「继续」，需要调整请说明修改意见。",
    }


def experts(state: AgentLoomState) -> dict[str, Any]:
    """执行专家组：根据蓝图执行任务。"""
    user_request = state.get("user_request", "")
    blueprint = state.get("blueprint", {})
    blueprint_text = blueprint.get("raw", "") if isinstance(blueprint, dict) else str(blueprint)

    system = (
        "你是执行专家组。在一个项目群聊中，你的职责是汇报执行进展。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格，不要使用 Markdown 标题格式\n"
        "- 直接说：做了什么、关键结果、有无问题\n"
        "- 像在工作群里给同事发进度汇报一样说话\n"
    )
    user = f"需求：{user_request}\n蓝图：{blueprint_text}\n请汇报执行结果。"

    message = _call_llm(system, user)

    return {
        "phase": "experts",
        "expert_runs": [{"swarm_output": message}],
        "message": message,
    }


def reviewer(state: AgentLoomState) -> dict[str, Any]:
    """质量审查员：审查执行结果。"""
    user_request = state.get("user_request", "")
    blueprint = state.get("blueprint", {})
    blueprint_text = blueprint.get("raw", "") if isinstance(blueprint, dict) else str(blueprint)
    expert_runs = state.get("expert_runs", [])
    expert_text = ""
    for run in expert_runs:
        if isinstance(run, dict):
            expert_text += run.get("swarm_output", str(run)) + "\n"

    r = int(state.get("review_round", 0))

    system = (
        "你是质量审查员。在一个项目群聊中，你的职责是快速给出审查结论。\n"
        "要求：\n"
        "- 回复必须控制在100-200个字符以内\n"
        "- 用简洁的群聊对话风格，不要使用 Markdown 标题格式\n"
        "- 直接说：审查结论（通过/需修改）、关键问题\n"
        "- 最后必须包含 PASS 或 NEEDS_REVISION\n"
        "- 像在工作群里给同事发审查意见一样说话\n"
    )
    user = (
        f"需求：{user_request}\n蓝图：{blueprint_text}\n"
        f"执行结果：{expert_text}\n第{r + 1}轮审查，请给出结论。"
    )

    message = _call_llm(system, user)

    verdict = "pass" if "PASS" in message.upper() and "NEEDS_REVISION" not in message.upper() else "needs_revision"

    return {
        "phase": "review",
        "review_round": r + 1,
        "review_verdict": verdict,
        "message": message,
    }
