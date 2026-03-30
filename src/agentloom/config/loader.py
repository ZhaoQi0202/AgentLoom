import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from agentloom.paths import config_dir

from .manifest import load_manifest
from .models import ConfigValidationError, LoadedConfig, McpEntry, ShellPolicy, SkillEntry


def iter_mcp_files(config_root: Path | None = None) -> Iterator[Path]:
    base = config_dir() if config_root is None else config_root
    mcp_dir = base / "mcp"
    if not mcp_dir.is_dir():
        return
    yield from sorted(mcp_dir.glob("*.json"))


def _load_mcp_entry(path: Path) -> McpEntry:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigValidationError(f"mcp file must be a JSON object: {path}")
    stem_id = path.stem
    if "id" not in raw:
        raw = {**raw, "id": stem_id}
    try:
        return McpEntry.model_validate(raw)
    except ValidationError as e:
        raise ConfigValidationError(str(e)) from e


def load_all(config_root: Path | None = None) -> LoadedConfig:
    base = config_dir() if config_root is None else config_root
    try:
        manifest = load_manifest(base)
    except ConfigValidationError:
        raise
    mcps: list[McpEntry] = []
    for p in iter_mcp_files(base):
        mcps.append(_load_mcp_entry(p))
    skills = [SkillEntry(id=sid) for sid in manifest.skill_ids]
    shell = manifest.shell if manifest.shell is not None else ShellPolicy()
    return LoadedConfig(
        version=manifest.version,
        mcp_ids=list(manifest.mcp_ids),
        skill_ids=list(manifest.skill_ids),
        mcps=mcps,
        skills=skills,
        shell=shell,
    )
