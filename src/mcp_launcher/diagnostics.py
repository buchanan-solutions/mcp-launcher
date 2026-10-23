"""Bounded, read-only Secret Service metadata checks; never retrieve credentials."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


class ProbeError(Exception):
    """A metadata probe could not establish a result."""


def _bus(*args: str) -> object:
    try:
        result = subprocess.run(
            ["busctl", "--user", "--auto-start=no", "--timeout=2", "--json=short", *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode:
            raise ProbeError
        data = json.loads(result.stdout)["data"]
        if args[0] == "get-property":
            if not isinstance(data, list) or len(data) != 1:
                raise ProbeError
            return data[0]
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as exc:
        raise ProbeError from exc


def _apt_hint() -> str:
    try:
        release = Path("/etc/os-release").read_text()
    except OSError:
        release = ""
    if any(word in release.lower() for word in ("ubuntu", "debian")):
        return "On Debian/Ubuntu: sudo apt install libsecret-tools."
    return "Install secret-tool with your package manager (Debian/Ubuntu: sudo apt install libsecret-tools)."


def secrets_status() -> tuple[list[str], bool]:
    lines = [f"OS: {sys.platform}"]
    if sys.platform != "linux":
        return [*lines, "Unsupported: Linux only; see docs/roadmap.md."], False
    tool = shutil.which("secret-tool")
    if tool:
        lines.append("secret-tool: available")
    else:
        lines.extend(["secret-tool: missing", _apt_hint()])
    lines.append("The client package does not install or configure a keyring provider.")
    if not shutil.which("busctl"):
        return [*lines, "Session D-Bus / Secret Service: unknown (busctl unavailable)."], False
    try:
        owned = _bus(
            "call",
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            "s",
            "org.freedesktop.secrets",
        )
    except ProbeError:
        return [
            *lines,
            "Session D-Bus: unreachable or probe unavailable. Run in your desktop login session; for Codex, forward DBUS_SESSION_BUS_ADDRESS and XDG_RUNTIME_DIR (docs/configuration/Codex.md).",
        ], False
    lines.append("Session D-Bus: reachable")
    if owned != [True]:
        return [
            *lines,
            "Secret Service: no running provider. Open/configure your desktop keyring provider; this check does not start one.",
        ], False
    lines.append("Secret Service: running provider (org.freedesktop.secrets)")
    try:
        collections = _bus(
            "get-property",
            "org.freedesktop.secrets",
            "/org/freedesktop/secrets",
            "org.freedesktop.Secret.Service",
            "Collections",
        )
        if not isinstance(collections, list) or not all(isinstance(p, str) for p in collections):
            raise ProbeError
        if not collections:
            return [
                *lines,
                "Collections: none. Configure a collection with your desktop keyring manager.",
            ], False
        # Bound total probe time even if a provider exposes many collections.
        if len(collections) > 16:
            return [
                *lines,
                "Collections: unknown (more than 16; bounded diagnostic stopped).",
            ], False
        locked = 0
        for path in collections:
            state = _bus(
                "get-property",
                "org.freedesktop.secrets",
                path,
                "org.freedesktop.Secret.Collection",
                "Locked",
            )
            if not isinstance(state, bool):
                raise ProbeError
            locked += int(state)
    except ProbeError:
        return [*lines, "Collections: unknown (metadata probe failed or timed out)."], False
    lines.append(
        f"Collections: {len(collections)} total, {locked} locked, {len(collections) - locked} unlocked"
    )
    if locked:
        lines.append("Unlock required collections with your desktop keyring manager.")
    lines.append(
        "No credentials read or changed. This does not verify configured credentials or full provider compatibility."
    )
    return lines, bool(tool) and locked == 0
