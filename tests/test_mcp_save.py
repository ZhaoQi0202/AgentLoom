import json

from agentloom.config.loader import save_mcp_entry, load_all
from agentloom.config.models import McpEntry
from agentloom.paths import config_dir


def test_save_mcp_entry_writes_file_and_updates_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTLOOM_ROOT", str(tmp_path))
    entry = McpEntry(id="srv", command="npx", args=["-y", "mcp"], name="说明")
    save_mcp_entry(entry)
    root = config_dir()
    mcp_file = root / "mcp" / "srv.json"
    assert mcp_file.is_file()
    data = json.loads(mcp_file.read_text(encoding="utf-8"))
    assert data["id"] == "srv"
    assert data["command"] == "npx"
    assert data["args"] == ["-y", "mcp"]
    assert data["name"] == "说明"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mcp_ids"] == ["srv"]
    cfg = load_all()
    assert len(cfg.mcps) == 1
    assert cfg.mcps[0].id == "srv"


def test_save_mcp_entry_idempotent_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTLOOM_ROOT", str(tmp_path))
    entry = McpEntry(id="x", command="cmd")
    save_mcp_entry(entry)
    save_mcp_entry(entry)
    manifest = json.loads((config_dir() / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["mcp_ids"] == ["x"]
