# ./src/mcp_launcher/process.py
"""Replace the launcher process with the server command."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from mcp_launcher.errors import LaunchError


class ProcessReplacer(Protocol):
    """Start the server in place of the launcher."""

    def replace(
        self,
        argv: Sequence[str],
        env: Mapping[str, str],
        cwd: Path | None,
    ) -> None:
        """Replace the current process. A return means the replacement failed."""


class OsExecReplacer:
    """``chdir`` when requested, then ``execvpe`` so stdio and signals stay attached."""

    def replace(
        self,
        argv: Sequence[str],
        env: Mapping[str, str],
        cwd: Path | None,
    ) -> None:
        if not argv or argv[0] == "":
            raise LaunchError("command executable must not be empty")
        if cwd is not None:
            try:
                os.chdir(cwd)
            except OSError as exc:
                raise LaunchError(
                    f"could not use working directory {cwd}: {exc.strerror}"
                ) from None
        try:
            os.execvpe(argv[0], list(argv), dict(env))
        except OSError as exc:
            raise LaunchError(f"could not execute {argv[0]}: {exc.strerror}") from None
