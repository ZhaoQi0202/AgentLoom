from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigValidationError(Exception):
    pass


class ShellPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shell: Literal["cmd", "powershell"] = "cmd"
    high_risk_prefixes: list[str] = Field(default_factory=list)


class McpEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)


class SkillEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str | None = None


class ManifestRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = "1"
    mcp_ids: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    shell: ShellPolicy | None = None


class LoadedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    mcp_ids: list[str]
    skill_ids: list[str]
    mcps: list[McpEntry]
    skills: list[SkillEntry]
    shell: ShellPolicy
