from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from agentloom import paths
from agentloom.bootstrap import ensure_layout
from agentloom.graph.nodes.stubs import (
    architect,
    consultant,
    experts,
    hitl_blueprint,
    reviewer,
)
from agentloom.graph.state import AgentLoomState


def build_graph(install_root: Path | None = None) -> Any:
    prev = os.environ.get("AGENTLOOM_ROOT")
    if install_root is not None:
        os.environ["AGENTLOOM_ROOT"] = str(install_root.resolve())
    try:
        ensure_layout()
        db_path = paths.data_dir() / "checkpoints.sqlite"
    finally:
        if install_root is not None:
            if prev is None:
                os.environ.pop("AGENTLOOM_ROOT", None)
            else:
                os.environ["AGENTLOOM_ROOT"] = prev

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    g = StateGraph(AgentLoomState)
    g.add_node("consultant", consultant)
    g.add_node("architect", architect)
    g.add_node("hitl_blueprint", hitl_blueprint)
    g.add_node("experts", experts)
    g.add_node("reviewer", reviewer)
    g.add_edge(START, "consultant")
    g.add_edge("consultant", "architect")
    g.add_edge("architect", "hitl_blueprint")
    g.add_edge("hitl_blueprint", "experts")
    g.add_edge("experts", "reviewer")
    g.add_edge("reviewer", END)

    return g.compile(
        checkpointer=checkpointer,
        interrupt_before=["architect", "hitl_blueprint", "reviewer"],
    )
