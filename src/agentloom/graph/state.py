from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentLoomState(TypedDict, total=False):
    task_id: str
    phase: str
    consult_confidence: float
    blueprint: dict[str, Any]
    mounted_tools: list[str]
    expert_runs: Annotated[list[dict[str, Any]], operator.add]
    review_round: int
    review_verdict: str
    gap_decision: str
    architect_gap_notes: str
