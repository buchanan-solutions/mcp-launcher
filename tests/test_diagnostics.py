import json
import subprocess

import pytest
from typer.testing import CliRunner

from mcp_launcher import diagnostics, platforms
from mcp_launcher.cli.main import app


def test_path_no_creation(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config space"))
    result = CliRunner().invoke(app, ["path"])
    assert result.exit_code == 0
    assert result.stdout == f"{tmp_path / 'config space/mcp-launcher/config.yaml'}\n"
    assert not (tmp_path / "config space").exists()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    for value in ["~/custom.yaml", "custom.yaml"]:
        result = CliRunner().invoke(app, ["path", "--config", value])
        assert result.stdout == f"{tmp_path / 'custom.yaml'}\n"


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_platform_gate(platform, monkeypatch):
    monkeypatch.setattr(platforms.sys, "platform", platform)
    result = CliRunner().invoke(app, ["path"])
    assert result.exit_code == 1
    assert "Linux only" in result.stderr
    assert "pull request" in result.stderr
    assert CliRunner().invoke(app, ["--help"]).exit_code == 0


def test_missing_tools_guidance(monkeypatch):
    monkeypatch.setattr(diagnostics.shutil, "which", lambda name: None)
    lines, ready = diagnostics.secrets_status()
    assert not ready
    assert "sudo apt install libsecret-tools" in "\n".join(lines)
    assert "unknown" in "\n".join(lines)


@pytest.mark.parametrize(
    ("responses", "ready", "message"),
    [
        ([[True], ["/collection"], False], True, "1 unlocked"),
        ([[True], ["/collection"], True], False, "1 locked"),
        ([[False]], False, "no running provider"),
        ([[True], []], False, "Collections: none"),
        ([[True], ["/c"] * 17], False, "bounded diagnostic stopped"),
        ([[True], ["/collection"], "bad"], False, "unknown"),
    ],
)
def test_metadata_branches(monkeypatch, responses, ready, message):
    monkeypatch.setattr(diagnostics.shutil, "which", lambda name: f"/bin/{name}")
    values = iter(responses)
    calls = []

    def probe(*args):
        calls.append(args)
        return next(values)

    monkeypatch.setattr(diagnostics, "_bus", probe)
    lines, result = diagnostics.secrets_status()
    assert result == ready
    assert message in "\n".join(lines)
    assert all("GetSecret" not in call and "Unlock" not in call for call in calls)


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("busctl", 3), OSError()])
def test_probe_failure_is_bounded_and_redacted(monkeypatch, failure):
    def run(*args, **kwargs):
        assert "--auto-start=no" in args[0]
        assert kwargs["timeout"] == 3
        raise failure

    monkeypatch.setattr(diagnostics.subprocess, "run", run)
    with pytest.raises(diagnostics.ProbeError):
        diagnostics._bus("call", "metadata")


@pytest.mark.parametrize("data", [False, ["/collection"]])
def test_busctl_property_json_shape(monkeypatch, data):
    monkeypatch.setattr(
        diagnostics.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, json.dumps({"data": [data]})),
    )
    assert diagnostics._bus("get-property", "metadata") == data


def test_secrets_help_and_status_exit(monkeypatch):
    result = CliRunner().invoke(app, ["secrets", "--help"])
    assert result.exit_code == 0
    assert "secret-tool store" in result.stdout
    monkeypatch.setattr("mcp_launcher.cli.main.secrets_status", lambda: (["unknown"], False))
    assert CliRunner().invoke(app, ["secrets", "status"]).exit_code == 1


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_source_build_gate(platform, monkeypatch):
    import runpy
    from pathlib import Path

    monkeypatch.setattr(platforms.sys, "platform", platform)
    with pytest.raises(RuntimeError, match="Linux only"):
        runpy.run_path(str(Path(__file__).parents[1] / "setup.py"))


def test_unreachable_bus_reports_unknown(monkeypatch):
    monkeypatch.setattr(diagnostics.shutil, "which", lambda name: f"/bin/{name}")

    def probe(*args):
        raise diagnostics.ProbeError

    monkeypatch.setattr(diagnostics, "_bus", probe)
    lines, ready = diagnostics.secrets_status()
    assert not ready
    assert "DBUS_SESSION_BUS_ADDRESS" in "\n".join(lines)
