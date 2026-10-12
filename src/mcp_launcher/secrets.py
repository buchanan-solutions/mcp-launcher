# ./src/mcp_launcher/secrets.py
"""Resolve profile secrets through ``secret-tool`` without printing their values."""

from __future__ import annotations

import subprocess
from typing import Protocol

from mcp_launcher.config import SecretRef
from mcp_launcher.errors import LaunchError


def format_secret_ref(ref: SecretRef) -> str:
    """Describe a secret reference using its attributes, never its value."""
    return f"service={ref.service!r}, profile={ref.profile!r}, key={ref.key!r}"


class SecretSource(Protocol):
    """Lookup a single secret value for an environment variable name."""

    def lookup(self, variable: str, ref: SecretRef) -> str:
        """Return the secret. Raise :class:`LaunchError` when it is missing."""
        ...


class SecretTool:
    """Read one secret with ``secret-tool lookup``.

    stdout is captured so a retrieved value never reaches the MCP stdio stream.
    ``secret-tool`` adds a trailing newline only when its stdout is a terminal;
    a pipe receives the stored secret unchanged, so this does not strip bytes.
    """

    def __init__(self, executable: str = "secret-tool") -> None:
        self._executable = executable

    def lookup(self, variable: str, ref: SecretRef) -> str:
        details = format_secret_ref(ref)
        try:
            completed = subprocess.run(
                [
                    self._executable,
                    "lookup",
                    "service",
                    ref.service,
                    "profile",
                    ref.profile,
                    "key",
                    ref.key,
                ],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            raise LaunchError(
                "secret-tool was not found; install it with your system package manager"
            ) from None
        except OSError as exc:
            raise LaunchError(f"could not run secret-tool: {exc.strerror}") from None
        if completed.returncode != 0:
            raise LaunchError(f"secret {variable} was not found ({details})") from None
        try:
            return completed.stdout.decode("utf-8")
        except UnicodeDecodeError:
            raise LaunchError(f"secret {variable} is not valid UTF-8 ({details})") from None
