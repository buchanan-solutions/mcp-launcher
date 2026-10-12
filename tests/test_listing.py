# ./tests/test_listing.py
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mcp_launcher.cli.main import app
from mcp_launcher.config import load_config
from mcp_launcher.errors import LaunchError
from mcp_launcher.listing import render_listing
from mcp_launcher.secrets import SecretTool

EXAMPLE = Path(__file__).parents[1] / "examples" / "config.yaml"

HIDDEN = """
version: 1
env:
  LOG_LEVEL: warning
servers:
  demo:
    command:
      - /usr/bin/demo
      - --stdio
    env:
      PUBLIC_URL: https://demo.example.test
    profiles:
      readonly:
        secrets:
          API_TOKEN:
            service: hidden-service
            profile: hidden-profile
            key: hidden-key
      plain: {}
"""


def test_list_names_servers() -> None:
    text = render_listing(load_config(EXAMPLE), None)
    assert text == "openproject\n"


def test_server_listing_shows_command_env_and_secret_names() -> None:
    text = render_listing(load_config(EXAMPLE), "openproject")
    assert text == (
        "env:\n"
        "  LOG_LEVEL=warning\n"
        "openproject\n"
        "  command:\n"
        "    /opt/openproject-mcp/bin/openproject-mcp\n"
        "  env:\n"
        "    OPENPROJECT_URL=https://projects.example.test\n"
        "  profiles:\n"
        "    manufacturing-readonly:\n"
        "      secrets:\n"
        "        OPENPROJECT_API_KEY\n"
        "    personal:\n"
        "      env:\n"
        "        LOG_LEVEL=info\n"
        "      secrets:\n"
        "        OPENPROJECT_URL\n"
        "        OPENPROJECT_API_KEY\n"
    )


def test_listing_omits_keyring_attributes(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(HIDDEN, encoding="utf-8")
    text = render_listing(load_config(path), "demo")
    assert "API_TOKEN" in text
    assert "PUBLIC_URL=https://demo.example.test" in text
    assert "/usr/bin/demo" in text
    assert "--stdio" in text
    assert "hidden-service" not in text
    assert "hidden-profile" not in text
    assert "hidden-key" not in text
    assert "plain:\n      (empty)\n" in text


def test_missing_command_is_marked(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        HIDDEN.replace(
            "    command:\n      - /usr/bin/demo\n      - --stdio\n", "    command: null\n"
        ),
        encoding="utf-8",
    )
    text = render_listing(load_config(path), "demo")
    assert "    (not set)\n" in text


def test_unknown_server(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(HIDDEN, encoding="utf-8")
    with pytest.raises(LaunchError, match="server 'missing'"):
        render_listing(load_config(path), "missing")


def test_cli_list_does_not_call_secret_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(HIDDEN, encoding="utf-8")

    def fail(self: SecretTool, variable: str, ref: object) -> str:
        raise AssertionError(f"lookup of {variable}")

    monkeypatch.setattr(SecretTool, "lookup", fail)
    result = CliRunner().invoke(app, ["list", "demo", "--config", str(path)])
    assert result.exit_code == 0, result.output
    assert "API_TOKEN" in result.output
    assert "hidden-service" not in result.output
    assert result.stderr == "" or "hidden-" not in result.stderr


def test_cli_unknown_server_stays_on_stderr(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(HIDDEN, encoding="utf-8")
    result = CliRunner().invoke(app, ["list", "missing", "--config", str(path)])
    assert result.exit_code == 1
    assert "server 'missing'" in result.output
