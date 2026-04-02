from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentLoomState(TypedDict, total=False):
    task_id: str
    user_request: str       # 用户输入的任务描述
    phase: str
    consult_confidence: float
    consult_summary: str    # Consultant 分析摘要
    blueprint: dict[str, Any]
    mounted_tools: list[str]
    expert_runs: Annotated[list[dict[str, Any]], operator.add]
    review_round: int
    review_verdict: str
    gap_decision: str
    architect_gap_notes: str
    message: str            # 当前节点输出给对话流的消息
    _thread_id: str  # 内部：event_bus 路由用
