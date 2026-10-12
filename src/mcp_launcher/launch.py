# ./src/mcp_launcher/launch.py
"""Choose the command and environment, then hand off to the server process."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pytools.logging.loggable import Loggable

from mcp_launcher.config import AppConfig, ProfileConfig, SecretRef, ServerConfig
from mcp_launcher.errors import LaunchError
from mcp_launcher.process import OsExecReplacer, ProcessReplacer
from mcp_launcher.secrets import SecretSource, format_secret_ref


@dataclass(frozen=True)
class LaunchPlan:
    """The process image that will replace the launcher."""

    argv: tuple[str, ...]
    env: dict[str, str]
    cwd: Path | None


class Launcher(Loggable):
    """Build a launch plan and replace this process with the server."""

    def __init__(
        self,
        secrets: SecretSource,
        replacer: ProcessReplacer | None = None,
    ) -> None:
        self._secrets = secrets
        self._replacer = replacer if replacer is not None else OsExecReplacer()

    def run(
        self,
        config: AppConfig,
        server_name: str,
        profile_name: str,
        command_override: Sequence[str] | None,
        cwd: Path | None,
        base_env: Mapping[str, str] | None = None,
    ) -> None:
        plan = self.prepare(
            config=config,
            server_name=server_name,
            profile_name=profile_name,
            command_override=command_override,
            cwd=cwd,
            base_env=base_env,
        )
        self._replacer.replace(plan.argv, plan.env, plan.cwd)

    def prepare(
        self,
        config: AppConfig,
        server_name: str,
        profile_name: str,
        command_override: Sequence[str] | None,
        cwd: Path | None,
        base_env: Mapping[str, str] | None = None,
    ) -> LaunchPlan:
        """Resolve argv, cwd, and env. Secret lookup happens only after those checks."""
        server = _require_server(config, server_name)
        profile = _require_profile(server, server_name, profile_name)
        argv = select_command(server.command, command_override, server_name)
        resolved_cwd = resolve_cwd(cwd)
        self.log.debug(
            "Launching server %s with profile %s via %s",
            server_name,
            profile_name,
            argv[0],
        )
        env = merge_env(
            base_env if base_env is not None else os.environ,
            config.env,
            server.env,
            profile.env,
        )
        env.update(self._resolve_secrets(profile.secrets))
        return LaunchPlan(argv=tuple(argv), env=env, cwd=resolved_cwd)

    def _resolve_secrets(self, secrets: Mapping[str, SecretRef]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for name, ref in secrets.items():
            self.log.debug("Looking up %s (%s)", name, format_secret_ref(ref))
            value = self._secrets.lookup(name, ref)
            if value == "":
                raise LaunchError(f"secret {name} is empty ({format_secret_ref(ref)})")
            if "\x00" in value:
                raise LaunchError(f"secret {name} contains a null byte ({format_secret_ref(ref)})")
            resolved[name] = value
        return resolved


def select_command(
    configured: Sequence[str] | None,
    override: Sequence[str] | None,
    server_name: str,
) -> list[str]:
    """Use the override after ``--`` when present; otherwise the configured argv."""
    if override:
        if override[0] == "":
            raise LaunchError("command executable must not be empty")
        return list(override)
    if configured:
        return list(configured)
    raise LaunchError(
        f"no command for server {server_name!r}; set the server command or pass a command after --"
    )


def resolve_cwd(cwd: Path | None) -> Path | None:
    """Keep the caller's working directory unless ``cwd`` names an existing directory."""
    if cwd is None:
        return None
    resolved = cwd.expanduser().resolve()
    if not resolved.is_dir():
        raise LaunchError(f"working directory does not exist: {resolved}")
    return resolved


def merge_env(*layers: Mapping[str, str]) -> dict[str, str]:
    """Apply environment layers from broadest to narrowest without mutating them."""
    merged: dict[str, str] = {}
    for layer in layers:
        merged.update(layer)
    return merged


def _require_server(config: AppConfig, name: str) -> ServerConfig:
    try:
        return config.servers[name]
    except KeyError:
        raise LaunchError(f"server {name!r} is not in the configuration") from None


def _require_profile(server: ServerConfig, server_name: str, profile_name: str) -> ProfileConfig:
    try:
        return server.profiles[profile_name]
    except KeyError:
        raise LaunchError(
            f"profile {profile_name!r} is not defined for server {server_name!r}"
        ) from None
