# ./src/mcp_launcher/listing.py
"""Render configuration for inspection without reading the keyring."""

from __future__ import annotations

from collections.abc import Mapping

from mcp_launcher.config import AppConfig, ProfileConfig
from mcp_launcher.errors import LaunchError


def render_listing(config: AppConfig, server_name: str | None) -> str:
    """Return a text listing of every server, or one server's launch details.

    Secret entries contribute only the environment variable name. Keyring
    attributes and secret values are omitted, and no lookup is performed.
    """
    if server_name is None:
        return "".join(f"{name}\n" for name in config.servers)
    return _render_server(config, server_name)


def _render_server(config: AppConfig, server_name: str) -> str:
    try:
        server = config.servers[server_name]
    except KeyError:
        raise LaunchError(f"server {server_name!r} is not in the configuration") from None
    lines: list[str] = []
    if config.env:
        lines.append("env:")
        lines.extend(_env_lines(config.env, indent=2))
    lines.append(server_name)
    lines.append("  command:")
    if server.command:
        lines.extend(f"    {argument}" for argument in server.command)
    else:
        lines.append("    (not set)")
    if server.env:
        lines.append("  env:")
        lines.extend(_env_lines(server.env, indent=4))
    lines.append("  profiles:")
    for profile_name, profile in server.profiles.items():
        lines.extend(_profile_lines(profile_name, profile))
    return "\n".join(lines) + "\n"


def _profile_lines(name: str, profile: ProfileConfig) -> list[str]:
    lines = [f"    {name}:"]
    if profile.env:
        lines.append("      env:")
        lines.extend(_env_lines(profile.env, indent=8))
    if profile.secrets:
        lines.append("      secrets:")
        lines.extend(f"        {variable}" for variable in profile.secrets)
    if not profile.env and not profile.secrets:
        lines.append("      (empty)")
    return lines


def _env_lines(env: Mapping[str, str], indent: int) -> list[str]:
    padding = " " * indent
    return [f"{padding}{name}={value}" for name, value in env.items()]
