from pathlib import Path

from agentloom.tools.tool_registry import create_tools_for_task


def test_create_builtin_tools(tmp_path: Path):
    """shell 和 python 工具应该被正确创建。"""
    tools = create_tools_for_task(["shell", "python"], tmp_path)
    assert len(tools) == 2
    names = {t.name for t in tools}
    assert "shell_execute" in names
    assert "python_execute" in names


def test_unknown_tool_ignored(tmp_path: Path):
    """未知工具 ID 应被忽略。"""
    tools = create_tools_for_task(["shell", "unknown_tool", "python"], tmp_path)
    assert len(tools) == 2


def test_dedup_tool_ids(tmp_path: Path):
    """重复的工具 ID 不应创建多个实例。"""
    tools = create_tools_for_task(["shell", "shell"], tmp_path)
    assert len(tools) == 1


def test_empty_tool_ids(tmp_path: Path):
    """空工具列表应返回空列表。"""
    tools = create_tools_for_task([], tmp_path)
    assert tools == []
