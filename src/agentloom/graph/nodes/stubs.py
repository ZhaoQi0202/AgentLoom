from __future__ import annotations

from typing import Any

from agentloom.graph.state import AgentLoomState


def consultant(state: AgentLoomState) -> dict[str, Any]:
    _ = state
    return {
        "phase": "consult",
        "consult_confidence": 1.0,
    }


def architect(state: AgentLoomState) -> dict[str, Any]:
    _ = state
    return {
        "phase": "architect",
        "blueprint": {"steps": [], "acceptance": []},
        "architect_gap_notes": "",
    }


def hitl_blueprint(state: AgentLoomState) -> dict[str, Any]:
    _ = state
    return {"phase": "hitl_blueprint"}


def experts(state: AgentLoomState) -> dict[str, Any]:
    _ = state
    return {
        "phase": "experts",
        "expert_runs": [{"stub": True}],
    }


def reviewer(state: AgentLoomState) -> dict[str, Any]:
    _ = state
    r = int(state.get("review_round", 0))
    return {
        "phase": "review",
        "review_round": r + 1,
        "review_verdict": "pass",
    }
