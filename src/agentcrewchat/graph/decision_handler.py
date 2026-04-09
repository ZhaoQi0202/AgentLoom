"""审核超限用户决策处理器。"""
from __future__ import annotations

import threading
from typing import Any

from agentcrewchat.graph.event_bus import emit_event
from agentcrewchat.llm.factory import get_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

REVIEW_OVER_LIMIT_PROMPT = """\
你是铁口，一位毒舌但细致的审核员。某个任务已经尝试了 3 次仍未通过审核。
你需要用自然语言向用户说明情况，并在话术中自然引导用户做出选择。

## 你的话术中必须包含以下三个选项的引导（用自然语言，不要用编号列表）：
1. 让我们跳过这个任务继续推进
2. 交还架构师明哲重新规划这个任务点
3. 终止整个执行流程

语气要像在工作群里跟同事说正事，简短有力。
"""


def generate_review_limit_message(
    task_name: str,
    task_goal: str,
    review_msg: str,
) -> str:
    """让 LLM 生成铁口的超限说明消息。"""
    user_prompt = (
        f"任务名称: {task_name}\n"
        f"任务目标: {task_goal}\n"
        f"审核意见: {review_msg}\n\n"
        f"请用自然语言向用户说明情况。"
    )
    llm = get_chat_model(phase="review")
    resp = llm.invoke([
        SystemMessage(content=REVIEW_OVER_LIMIT_PROMPT),
        HumanMessage(content=user_prompt),
    ])
    return resp.content


# ── 决策信号 ──
_decision_signals: dict[str, str] = {}
_decision_events: dict[str, threading.Event] = {}
_lock = threading.Lock()


def wait_for_decision(thread_id: str, timeout: float = 600) -> str:
    """阻塞等待用户决策，返回 "skip" / "reroute" / "terminate"。"""
    evt = threading.Event()
    with _lock:
        _decision_events[thread_id] = evt
    evt.wait(timeout=timeout)
    with _lock:
        _decision_events.pop(thread_id, None)
        decision = _decision_signals.pop(thread_id, "skip")
    return decision


def submit_decision(thread_id: str, decision: str) -> None:
    """提交用户决策。"""
    with _lock:
        _decision_signals[thread_id] = decision
        evt = _decision_events.get(thread_id)
    if evt:
        evt.set()


def classify_user_input(text: str, can_reroute: bool) -> str:
    """将用户自由文本归类为 skip/reroute/terminate。"""
    t = (text or "").strip().lower()

    terminate_kw = ["终止", "停止", "结束", "放弃", "不做了", "算了"]
    reroute_kw = ["重做", "重新规划", "重新设计", "交给明哲", "交还明哲", "reroute"]
    skip_kw = ["跳过", "继续", "忽略", "跳过继续", "算了继续", "先跳过", "skip"]

    for kw in terminate_kw:
        if kw in t:
            return "terminate"
    if can_reroute:
        for kw in reroute_kw:
            if kw in t:
                return "reroute"
    for kw in skip_kw:
        if kw in t:
            return "skip"
    # 默认跳过
    return "skip"
