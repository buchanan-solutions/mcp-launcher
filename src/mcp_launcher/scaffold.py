# ./src/mcp_launcher/scaffold.py
"""Install the bundled example configuration without replacing an existing file."""

from __future__ import annotations

import os
from collections.abc import Callable
from enum import Enum
from importlib.resources import files
from pathlib import Path

from mcp_launcher.errors import LaunchError


class InstallStatus(Enum):
    """Outcome of offering the example configuration."""

    CREATED = "created"
    EXISTS = "exists"
    DECLINED = "declined"


def example_config_text() -> str:
    """Return the bundled example configuration."""
    resource = files("mcp_launcher").joinpath("templates/config.example.yaml")
    return resource.read_text(encoding="utf-8")


def install_example_config(
    destination: Path,
    *,
    assume_yes: bool,
    confirm: Callable[[str], bool],
) -> InstallStatus:
    """Create ``destination`` from the example when the user accepts.

    An existing file, directory, or symlink is left unchanged. The write uses
    exclusive create, so a file that appears after the check is not replaced.
    """
    path = destination.expanduser()
    if _occupied(path):
        return InstallStatus.EXISTS
    if not assume_yes and not confirm(f"Install the example configuration to {path}?"):
        return InstallStatus.DECLINED
    if _occupied(path):
        return InstallStatus.EXISTS
    try:
        _create_exclusive(path, example_config_text())
    except FileExistsError:
        return InstallStatus.EXISTS
    return InstallStatus.CREATED


def _occupied(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _create_exclusive(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise LaunchError(f"could not create {path.parent}: {exc.strerror}") from None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError:
        raise
    except OSError as exc:
        raise LaunchError(f"could not create {path}: {exc.strerror}") from None
    try:
        os.write(descriptor, text.encode("utf-8"))
    except OSError as exc:
        os.close(descriptor)
        path.unlink(missing_ok=True)
        raise LaunchError(f"could not write {path}: {exc.strerror}") from None
    os.close(descriptor)
