"""Python 脚本执行工具，在 workspace 的 venv 中运行。"""
from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.tools import tool

from agentloom.runtime.process_runner import run_process


def _find_venv_python(workspace: Path) -> str:
    """找到 workspace 中 venv 的 python 可执行文件路径。"""
    if sys.platform == "win32":
        python = workspace / ".venv" / "Scripts" / "python.exe"
    else:
        python = workspace / ".venv" / "bin" / "python"
    if python.exists():
        return str(python)
    return sys.executable  # fallback 到系统 python


def create_python_tool(workspace: Path):
    """创建绑定到特定 workspace 的 Python 脚本执行工具。"""
    venv_python = _find_venv_python(workspace)

    @tool
    def python_execute(script: str) -> str:
        """在项目虚拟环境中执行 Python 脚本。传入完整的 Python 代码字符串。"""
        script_file = workspace / "_temp_script.py"
        try:
            script_file.write_text(script, encoding="utf-8")
            returncode, stdout, stderr = run_process(
                [venv_python, str(script_file)],
                cwd=workspace,
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
        finally:
            script_file.unlink(missing_ok=True)

    return python_execute
