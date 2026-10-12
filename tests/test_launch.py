# ./tests/test_launch.py
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from mcp_launcher.config import AppConfig, SecretRef, load_config
from mcp_launcher.errors import LaunchError
from mcp_launcher.launch import Launcher

CONFIG = """
version: 1
env:
  LOG_LEVEL: warning
  FROM_ROOT: root
servers:
  demo:
    command:
      - configured
      - server-arg
    env:
      FROM_ROOT: server
      FROM_SERVER: server
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
      empty:
        secrets:
          TOKEN:
            service: demo
            profile: empty
            key: api
      plain: {}
"""


class MapSecrets:
    def __init__(self, values: dict[tuple[str, str, str], str]) -> None:
        self.values = values
        self.calls: list[str] = []

    def lookup(self, variable: str, ref: SecretRef) -> str:
        self.calls.append(variable)
        return self.values[(ref.service, ref.profile, ref.key)]


class ForbiddenSecrets:
    def lookup(self, variable: str, ref: SecretRef) -> str:
        raise AssertionError(f"lookup of {variable} should not happen")


class RecordingReplacer:
    def __init__(self) -> None:
        self.argv: tuple[str, ...] | None = None
        self.env: dict[str, str] | None = None
        self.cwd: Path | None = None

    def replace(
        self,
        argv: Sequence[str],
        env: Mapping[str, str],
        cwd: Path | None,
    ) -> None:
        self.argv = tuple(argv)
        self.env = dict(env)
        self.cwd = cwd


def _config(tmp_path: Path, text: str = CONFIG) -> AppConfig:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return load_config(path)


def test_precedence_and_secret_override(tmp_path: Path) -> None:
    secrets = MapSecrets({("demo", "readonly", "api"): "from-secret"})
    replacer = RecordingReplacer()
    base = {"CALLER": "yes", "FROM_ROOT": "caller", "TOKEN": "from-caller"}
    Launcher(secrets, replacer).run(
        config=_config(tmp_path),
        server_name="demo",
        profile_name="readonly",
        command_override=None,
        cwd=tmp_path,
        base_env=base,
    )
    assert replacer.argv == ("configured", "server-arg")
    assert replacer.cwd == tmp_path.resolve()
    assert replacer.env is not None
    assert replacer.env["CALLER"] == "yes"
    assert replacer.env["FROM_ROOT"] == "server"
    assert replacer.env["FROM_SERVER"] == "server"
    assert replacer.env["LOG_LEVEL"] == "info"
    assert replacer.env["TOKEN"] == "from-secret"
    assert base["TOKEN"] == "from-caller"
    assert secrets.calls == ["TOKEN"]


def test_command_after_double_dash_replaces_configured_command(tmp_path: Path) -> None:
    secrets = MapSecrets({("demo", "plain", "api"): "unused"})
    replacer = RecordingReplacer()
    Launcher(secrets, replacer).run(
        config=_config(tmp_path),
        server_name="demo",
        profile_name="plain",
        command_override=["node", "server.js", "--stdio", "a b", "$HOME", "*"],
        cwd=None,
        base_env={},
    )
    assert replacer.argv == ("node", "server.js", "--stdio", "a b", "$HOME", "*")
    assert secrets.calls == []


def test_missing_command_does_not_read_secrets(tmp_path: Path) -> None:
    text = CONFIG.replace(
        "    command:\n      - configured\n      - server-arg\n",
        "    command: null\n",
    )
    config = _config(tmp_path, text)
    with pytest.raises(LaunchError, match="no command"):
        Launcher(ForbiddenSecrets()).prepare(
            config=config,
            server_name="demo",
            profile_name="readonly",
            command_override=None,
            cwd=None,
            base_env={},
        )


def test_missing_cwd_does_not_read_secrets(tmp_path: Path) -> None:
    missing = tmp_path / "gone"
    with pytest.raises(LaunchError, match="working directory"):
        Launcher(ForbiddenSecrets()).prepare(
            config=_config(tmp_path),
            server_name="demo",
            profile_name="readonly",
            command_override=["server"],
            cwd=missing,
            base_env={},
        )


def test_unknown_server_and_profile_do_not_read_secrets(tmp_path: Path) -> None:
    launcher = Launcher(ForbiddenSecrets())
    config = _config(tmp_path)
    with pytest.raises(LaunchError, match="server 'missing'"):
        launcher.prepare(
            config=config,
            server_name="missing",
            profile_name="readonly",
            command_override=["server"],
            cwd=None,
            base_env={},
        )
    with pytest.raises(LaunchError, match="profile 'missing'"):
        launcher.prepare(
            config=config,
            server_name="demo",
            profile_name="missing",
            command_override=["server"],
            cwd=None,
            base_env={},
        )


def test_empty_secret_is_rejected_without_printing_a_value(tmp_path: Path) -> None:
    secrets = MapSecrets({("demo", "empty", "api"): ""})
    with pytest.raises(LaunchError, match="empty") as caught:
        Launcher(secrets).prepare(
            config=_config(tmp_path),
            server_name="demo",
            profile_name="empty",
            command_override=["server"],
            cwd=None,
            base_env={},
        )
    assert "from-secret" not in str(caught.value)


def test_null_byte_in_secret_is_rejected_without_the_value(tmp_path: Path) -> None:
    secrets = MapSecrets({("demo", "readonly", "api"): "hide-me\x00"})
    with pytest.raises(LaunchError, match="null byte") as caught:
        Launcher(secrets).prepare(
            config=_config(tmp_path),
            server_name="demo",
            profile_name="readonly",
            command_override=["server"],
            cwd=None,
            base_env={},
        )
    assert "hide-me" not in str(caught.value)
