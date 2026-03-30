import json
from pathlib import Path

from pydantic import ValidationError

from agentloom.paths import config_dir

from .models import ConfigValidationError, ManifestRecord


def manifest_path(config_root: Path | None = None) -> Path:
    base = config_dir() if config_root is None else config_root
    return base / "manifest.json"


def read_manifest_dict(config_root: Path | None = None) -> dict | None:
    path = manifest_path(config_root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest_dict(data: dict, config_root: Path | None = None) -> None:
    path = manifest_path(config_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(config_root: Path | None = None) -> ManifestRecord:
    raw = read_manifest_dict(config_root)
    if raw is None:
        return ManifestRecord()
    try:
        return ManifestRecord.model_validate(raw)
    except ValidationError as e:
        raise ConfigValidationError(str(e)) from e
