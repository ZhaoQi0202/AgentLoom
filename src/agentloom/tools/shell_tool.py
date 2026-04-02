"""Shell 命令执行工具，供 ReAct Agent 使用。"""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from agentloom.config.loader import load_all
from agentloom.runtime.shell_runner import ShellRunner


def create_shell_tool(workspace: Path):
    """创建绑定到特定 workspace 的 Shell 执行工具。"""
    cfg = load_all()
    runner = ShellRunner(cfg.shell)

    @tool
    def shell_execute(command: str) -> str:
        """在项目工作目录中执行 shell 命令。用于安装依赖、运行构建、创建文件等操作。"""
        if runner.hit_high_risk(command):
            return f"[拒绝] 命令被安全策略阻止: {command}"
        try:
            returncode, stdout, stderr = runner.run(
                command,
                workspace,
                timeout=120,
                max_stdout_bytes=8192,
                max_stderr_bytes=4096,
            )
            parts = []
            if stdout.strip():
                parts.append(f"stdout:\n{stdout.strip()}")
            if stderr.strip():
                parts.append(f"stderr:\n{stderr.strip()}")
            parts.append(f"exit_code: {returncode}")
            return "\n".join(parts) or f"exit_code: {returncode}"
        except Exception as e:
            return f"[错误] {e}"

    return shell_execute
