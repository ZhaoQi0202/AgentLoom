from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentcrewchat.tasks.workspace import create_task, delete_task, list_tasks, load_meta

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskInfo(BaseModel):
    id: str
    name: str
    path: str
    modified_at: str


class TaskCreateRequest(BaseModel):
    name: str


def _parse_task_dir(path) -> TaskInfo:
    """从任务目录名解析信息。格式: task_{timestamp}_{slug}"""
    dir_name = path.name
    m = re.match(r"task_(\d+)_(.+)", dir_name)
    if m:
        ts_ms = int(m.group(1))
        slug = m.group(2)
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    else:
        slug = dir_name
        stat = path.stat()
        dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

    # 优先从 meta.json 读取原始名称
    meta = load_meta(path)
    name = meta["name"] if meta and "name" in meta else slug.replace("-", " ").title()

    return TaskInfo(
        id=dir_name,
        name=name,
        path=str(path),
        modified_at=dt.isoformat(),
    )


@router.get("")
async def get_tasks() -> list[TaskInfo]:
    paths = list_tasks()
    return [_parse_task_dir(p) for p in paths]


@router.post("")
async def new_task(body: TaskCreateRequest) -> TaskInfo:
    try:
        path = create_task(body.name)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    return _parse_task_dir(path)


@router.delete("/{task_id}")
async def remove_task(task_id: str) -> dict:
    try:
        delete_task(task_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Task not found: {task_id}")
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"status": "ok"}


@router.get("/{task_id}/chat-history")
async def get_chat_history(task_id: str) -> list[dict]:
    """获取项目组的聊天历史事件。"""
    from agentcrewchat.paths import workspaces_dir

    history_path = workspaces_dir() / task_id / "chat_history.json"
    if not history_path.is_file():
        return []
    try:
        return json.loads(history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
