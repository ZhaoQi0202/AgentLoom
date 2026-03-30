import json

import pytest

from agentloom.config.loader import ConfigValidationError, load_all
from agentloom.paths import config_dir


def test_load_empty_manifest_creates_default(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTLOOM_ROOT", str(tmp_path))
    cfg = load_all()
    assert cfg.version == "1"
    assert cfg.mcp_ids == []
    assert cfg.skill_ids == []
    assert cfg.mcps == []
    assert cfg.skills == []
    assert cfg.shell.shell == "cmd"


def test_load_invalid_manifest_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTLOOM_ROOT", str(tmp_path))
    root = config_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text('{"version": 1}', encoding="utf-8")
    with pytest.raises(ConfigValidationError):
        load_all()


def test_load_merges_manifest_and_mcp_files(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTLOOM_ROOT", str(tmp_path))
    root = config_dir()
    mcp_dir = root / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1",
                "mcp_ids": ["a"],
                "skill_ids": ["s1"],
            }
        ),
        encoding="utf-8",
    )
    (mcp_dir / "a.json").write_text(
        json.dumps({"name": "Server A", "command": "npx", "args": ["-y", "mcp"]}),
        encoding="utf-8",
    )
    cfg = load_all()
    assert cfg.mcp_ids == ["a"]
    assert cfg.skill_ids == ["s1"]
    assert len(cfg.mcps) == 1
    assert cfg.mcps[0].id == "a"
    assert cfg.mcps[0].command == "npx"
    assert len(cfg.skills) == 1
    assert cfg.skills[0].id == "s1"
