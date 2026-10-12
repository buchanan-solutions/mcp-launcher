# ./tests/test_cli.py
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from mcp_launcher.cli.main import app

CONFIG = """
version: 1
env:
  LOG_LEVEL: warning
  FROM_ROOT: root
servers:
  demo:
    command:
      - configured-binary
      - configured-arg
    env:
      FROM_ROOT: server
      TOKEN: from-server
    profiles:
      readonly:
        env:
          LOG_LEVEL: info
        secrets:
          TOKEN:
            service: demo
            profile: readonly
            key: api
      plain: {}
"""

SECRET = "super-secret-value"
LEAK = "SENTINEL-SHOULD-NOT-LEAK"


def _script() -> Path:
    return Path(sys.executable).with_name("mcp-launcher")


def _env(extra_path: Path | None = None) -> dict[str, str]:
    path = os.environ.get("PATH", "")
    if extra_path is not None:
        path = f"{extra_path}{os.pathsep}{path}"
    return {
        "PATH": path,
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "CALLER_ONLY": "from-caller",
    }


def _write_config(directory: Path, text: str = CONFIG) -> Path:
    path = directory / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _write_secret_tool(directory: Path, *, found: bool) -> Path:
    log = directory / "calls.log"
    script = directory / "secret-tool"
    script.write_text(
        f"""#!{sys.executable}
import pathlib
import sys
pathlib.Path({str(log)!r}).write_text("called")
sys.stderr.write({LEAK!r})
if not {found}:
    raise SystemExit(1)
sys.stdout.write({SECRET!r})
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return log


def _run(
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_script()), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_lists_commands() -> None:
    completed = _run(["--help"], env=_env())
    assert completed.returncode == 0
    assert "run" in completed.stdout
    assert "list" in completed.stdout
    assert "init" in completed.stdout


def test_run_help_lists_profile() -> None:
    completed = _run(["run", "--help"], env=_env())
    assert completed.returncode == 0
    assert "--profile" in completed.stdout
    assert "COMMAND" in completed.stdout


def test_launch_replaces_process_and_keeps_stdio_clean(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_secret_tool(bin_dir, found=True)
    work = tmp_path / "work"
    work.mkdir()
    report = tmp_path / "report.json"
    code = (
        "import json, os, sys, pathlib; "
        "pathlib.Path(sys.argv[1]).write_text(json.dumps({"
        "'argv': sys.argv[2:], 'cwd': os.getcwd(), "
        "'token': os.environ.get('TOKEN'), 'level': os.environ.get('LOG_LEVEL'), "
        "'from_root': os.environ.get('FROM_ROOT'), 'caller': os.environ.get('CALLER_ONLY')"
        "}))"
    )
    completed = _run(
        [
            "run",
            "demo",
            "--profile",
            "readonly",
            "--config",
            str(config),
            "--cwd",
            str(work),
            "--",
            sys.executable,
            "-c",
            code,
            str(report),
            "a b",
            "$HOME",
            "*",
            "--stdio",
        ],
        env=_env(bin_dir),
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert SECRET not in completed.stderr
    assert LEAK not in completed.stderr
    payload = json.loads(report.read_text())
    assert payload["argv"] == ["a b", "$HOME", "*", "--stdio"]
    assert payload["cwd"] == str(work.resolve())
    assert payload["token"] == SECRET
    assert payload["level"] == "info"
    assert payload["from_root"] == "server"
    assert payload["caller"] == "from-caller"


def test_configured_command_is_used_when_no_override(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "ran.txt"
    configured = bin_dir / "configured-binary"
    configured.write_text(
        f"""#!{sys.executable}
import pathlib, sys
pathlib.Path({str(marker)!r}).write_text(repr(sys.argv[1:]))
""",
        encoding="utf-8",
    )
    configured.chmod(configured.stat().st_mode | stat.S_IEXEC)
    _write_secret_tool(bin_dir, found=True)
    completed = _run(
        ["run", "demo", "--profile", "readonly", "--config", str(config)],
        env=_env(bin_dir),
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    assert SECRET not in completed.stderr
    assert marker.read_text() == "['configured-arg']"


def test_missing_command_fails_before_secret_lookup(tmp_path: Path) -> None:
    text = CONFIG.replace(
        """    command:
      - configured-binary
      - configured-arg
""",
        "    command: null\n",
    )
    config = _write_config(tmp_path, text)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = _write_secret_tool(bin_dir, found=True)
    completed = _run(
        ["run", "demo", "--profile", "readonly", "--config", str(config)],
        env=_env(bin_dir),
    )
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "no command" in completed.stderr
    assert SECRET not in completed.stderr
    assert LEAK not in completed.stderr
    assert not calls.exists()


def test_failed_lookup_stays_on_stderr(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_secret_tool(bin_dir, found=False)
    completed = _run(
        ["run", "demo", "--profile", "readonly", "--config", str(config), "--", "true"],
        env=_env(bin_dir),
    )
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "was not found" in completed.stderr
    assert SECRET not in completed.stderr
    assert LEAK not in completed.stderr


def test_default_config_path_honors_xdg(tmp_path: Path) -> None:
    config_home = tmp_path / "xdg"
    config = config_home / "mcp-launcher" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(CONFIG, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_secret_tool(bin_dir, found=True)
    marker = tmp_path / "xdg-ran.txt"
    binary = bin_dir / "configured-binary"
    binary.write_text(
        f"""#!{sys.executable}
import pathlib
pathlib.Path({str(marker)!r}).write_text("ok")
""",
        encoding="utf-8",
    )
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    env = _env(bin_dir)
    env["XDG_CONFIG_HOME"] = str(config_home)
    completed = _run(["run", "demo", "--profile", "readonly"], env=env)
    assert completed.returncode == 0, completed.stderr
    assert marker.read_text() == "ok"
    assert completed.stdout == ""


def test_server_name_is_not_an_implicit_command(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    completed = _run(
        ["demo", "--profile", "readonly", "--config", str(config)],
        env=_env(),
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "demo" in completed.stderr.lower()


def test_init_yes_installs_example(tmp_path: Path) -> None:
    destination = tmp_path / "mcp-launcher" / "config.yaml"
    result = CliRunner().invoke(app, ["init", "--yes", "--config", str(destination)])
    assert result.exit_code == 0, result.output
    assert f"Installed example configuration at {destination}" in result.output
    assert destination.is_file()


def test_init_prompt_can_decline(tmp_path: Path) -> None:
    destination = tmp_path / "config.yaml"
    result = CliRunner().invoke(app, ["init", "--config", str(destination)], input="n\n")
    assert result.exit_code == 0, result.output
    assert "Not installed." in result.output
    assert not destination.exists()


def test_init_leaves_an_existing_file_unchanged(tmp_path: Path) -> None:
    destination = tmp_path / "config.yaml"
    destination.write_text("mine: true\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["init", "--yes", "--config", str(destination)])
    assert result.exit_code == 0, result.output
    assert "not overwriting with defaults" in result.output
    assert destination.read_text(encoding="utf-8") == "mine: true\n"


def test_init_without_a_prompt_asks_for_yes(tmp_path: Path) -> None:
    destination = tmp_path / "config.yaml"
    result = CliRunner().invoke(app, ["init", "--config", str(destination)])
    assert result.exit_code == 1
    assert "--yes" in result.output
    assert not destination.exists()


def test_missing_profile_writes_only_stderr(tmp_path: Path) -> None:
    config = _write_config(tmp_path)
    completed = _run(
        ["run", "demo", "--config", str(config)],
        env=_env(),
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "profile" in completed.stderr.lower()
