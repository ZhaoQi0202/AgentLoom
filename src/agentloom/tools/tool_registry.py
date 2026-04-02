"""工具注册表：根据工具 ID 列表创建 LangChain Tool 实例。"""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import BaseTool

from agentloom.tools.python_tool import create_python_tool
from agentloom.tools.shell_tool import create_shell_tool

# 工具 ID → 创建函数的映射
_BUILTIN_TOOL_FACTORIES: dict[str, callable] = {
    "shell": create_shell_tool,
    "python": create_python_tool,
}


def create_tools_for_task(
    tool_ids: list[str],
    workspace: Path,
) -> list[BaseTool]:
    """根据工具 ID 列表创建绑定到 workspace 的 LangChain Tool 实例。

    目前支持内置工具: shell, python
    未识别的 ID 会被忽略（后续可扩展 skill/MCP 工具）。
    """
    tools = []
    seen = set()
    for tid in tool_ids:
        if tid in seen:
            continue
        seen.add(tid)
        factory = _BUILTIN_TOOL_FACTORIES.get(tid)
        if factory:
            tools.append(factory(workspace))
    return tools
