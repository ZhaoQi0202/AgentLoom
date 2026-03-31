import tempfile
from pathlib import Path

from agentloom.graph import AgentLoomState, build_graph


def test_graph_compiles() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = Path(td)
        g = build_graph(install_root=root)
        assert g is not None


def test_invoke_interrupts_before_architect() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        root = Path(td)
        g = build_graph(install_root=root)
        cfg = {"configurable": {"thread_id": "t1"}}
        out: AgentLoomState = g.invoke({"task_id": "x"}, cfg)
        assert out.get("phase") == "consult"
        assert out.get("consult_confidence") == 1.0
        assert "blueprint" not in out
