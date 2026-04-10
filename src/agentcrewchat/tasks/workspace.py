import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from agentcrewchat.bootstrap import ensure_layout
from agentcrewchat.paths import workspaces_dir


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "task"


def run_uv_venv(task_path: Path) -> None:
    subprocess.run(["uv", "venv"], cwd=task_path, check=True)


def save_meta(task_path: Path, name: str) -> None:
    meta = {"name": name}
    (task_path / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def load_meta(task_path: Path) -> dict | None:
    meta_file = task_path / "meta.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text(encoding="utf-8"))
    return None


def create_task(name: str) -> Path:
    ensure_layout()
    slug = _slugify(name)
    ts = int(time.time() * 1000)
    dir_name = f"task_{ts}_{slug}"
    path = workspaces_dir() / dir_name
    path.mkdir(parents=True, exist_ok=False)
    save_meta(path, name.strip())
    run_uv_venv(path)
    return path


def list_tasks() -> list[Path]:
    ensure_layout()
    w = workspaces_dir()
    pat = re.compile(r"task_\d+_.+")
    tasks = [p for p in w.iterdir() if p.is_dir() and pat.fullmatch(p.name)]
    tasks.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return tasks


def delete_task(task_id: str) -> None:
    path = workspaces_dir() / task_id
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Task directory not found: {task_id}")
    # Windows 上 .venv 内文件可能被锁定，需要 onerror 处理只读文件
    def _on_rm_error(_func, _path, _exc_info):
        import stat
        try:
            os.chmod(_path, stat.S_IWRITE)
            os.remove(_path)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_on_rm_error)
