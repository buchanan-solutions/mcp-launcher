# ./src/mcp_launcher/config.py
"""Load and validate the launcher configuration file."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from mcp_launcher.errors import LaunchError


def _string_env(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("must be a mapping of strings")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or key == "":
            raise ValueError("environment variable names must be non-empty strings")
        if not isinstance(item, str):
            raise ValueError(
                f"{key} must be a string; quote YAML values that would be booleans or numbers"
            )
        if "\x00" in key or "\x00" in item:
            raise ValueError("environment entries must not contain null bytes")
        result[key] = item
    return result


def _command_argv(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str) or not isinstance(value, list):
        raise ValueError("must be a list of strings")
    if len(value) == 0:
        return None
    argv: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("must be a list of strings")
        argv.append(item)
    if argv[0] == "":
        raise ValueError("executable must not be empty")
    return argv


EnvMap = Annotated[dict[str, str], BeforeValidator(_string_env)]
CommandArgv = Annotated[list[str] | None, BeforeValidator(_command_argv)]


class SecretRef(BaseModel):
    """Attributes passed to ``secret-tool lookup``."""

    model_config = ConfigDict(extra="forbid")

    service: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    key: str = Field(min_length=1)


class ProfileConfig(BaseModel):
    """One named environment profile for a server."""

    model_config = ConfigDict(extra="forbid")

    env: EnvMap = Field(default_factory=dict)
    secrets: dict[str, SecretRef] = Field(default_factory=dict)

    @model_validator(mode="after")
    def env_and_secrets_do_not_overlap(self) -> ProfileConfig:
        overlap = sorted(set(self.env) & set(self.secrets))
        if overlap:
            joined = ", ".join(overlap)
            raise ValueError(f"defines {joined} in both env and secrets")
        return self


class ServerConfig(BaseModel):
    """A named server and the profiles that can launch it."""

    model_config = ConfigDict(extra="forbid")

    command: CommandArgv = None
    env: EnvMap = Field(default_factory=dict)
    profiles: dict[str, ProfileConfig]

    @field_validator("profiles")
    @classmethod
    def profile_names_are_present(cls, value: dict[str, ProfileConfig]) -> dict[str, ProfileConfig]:
        if any(name == "" for name in value):
            raise ValueError("profile names must not be empty")
        return value


class AppConfig(BaseModel):
    """Root configuration document. ``version`` is currently fixed at 1."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    env: EnvMap = Field(default_factory=dict)
    servers: dict[str, ServerConfig]

    @field_validator("servers")
    @classmethod
    def server_names_are_present(cls, value: dict[str, ServerConfig]) -> dict[str, ServerConfig]:
        if not value:
            raise ValueError("at least one server is required")
        if any(name == "" for name in value):
            raise ValueError("server names must not be empty")
        return value


def default_config_path(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the default config path, honoring ``XDG_CONFIG_HOME`` when it is set."""
    env = os.environ if environ is None else environ
    xdg = env.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        root = Path(xdg).expanduser()
    else:
        root = (home if home is not None else Path.home()) / ".config"
    return root / "mcp-launcher" / "config.yaml"


def load_config(path: Path) -> AppConfig:
    """Read ``path`` and return a validated configuration."""
    if not path.is_file():
        raise LaunchError(f"configuration file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LaunchError(f"could not read {path}: {exc.strerror}") from None
    except yaml.YAMLError as exc:
        raise LaunchError(f"could not parse {path}: {exc}") from None
    if not isinstance(raw, dict):
        raise LaunchError(f"configuration root must be a mapping: {path}")
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise LaunchError(f"invalid configuration {path}:\n{exc}") from None
