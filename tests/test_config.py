# ./tests/test_config.py
from pathlib import Path

import pytest

from mcp_launcher.config import default_config_path, load_config
from mcp_launcher.errors import LaunchError

EXAMPLE = Path(__file__).parents[1] / "examples" / "config.yaml"


def test_example_config_is_valid() -> None:
    config = load_config(EXAMPLE)
    assert config.version == 1
    server = config.servers["openproject"]
    assert server.command == ["/opt/openproject-mcp/bin/openproject-mcp"]
    assert "OPENPROJECT_API_KEY" in server.profiles["personal"].secrets


def test_default_config_path_uses_xdg_when_set() -> None:
    path = default_config_path(environ={"XDG_CONFIG_HOME": "/tmp/xdg"}, home=Path("/home/someone"))
    assert path == Path("/tmp/xdg/mcp-launcher/config.yaml")


def test_default_config_path_uses_home_when_xdg_is_blank() -> None:
    path = default_config_path(environ={"XDG_CONFIG_HOME": "  "}, home=Path("/home/someone"))
    assert path == Path("/home/someone/.config/mcp-launcher/config.yaml")


def test_profile_rejects_env_and_secrets_overlap(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 1
servers:
  demo:
    profiles:
      personal:
        env:
          TOKEN: from-env
        secrets:
          TOKEN:
            service: demo
            profile: personal
            key: api
""",
        encoding="utf-8",
    )
    with pytest.raises(LaunchError, match="TOKEN") as caught:
        load_config(path)
    assert "both env and secrets" in str(caught.value)


def test_command_must_be_an_argument_list(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 1
servers:
  demo:
    command: python server.py
    profiles:
      local: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(LaunchError, match="list of strings"):
        load_config(path)


def test_env_values_must_be_strings(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 1
env:
  ENABLED: true
servers:
  demo:
    profiles:
      local: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(LaunchError, match="ENABLED"):
        load_config(path)


def test_unsupported_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
version: 2
servers:
  demo:
    profiles:
      local: {}
""",
        encoding="utf-8",
    )
    with pytest.raises(LaunchError, match="invalid configuration"):
        load_config(path)


def test_missing_file() -> None:
    with pytest.raises(LaunchError, match="not found"):
        load_config(Path("/no/such/mcp-launcher.yaml"))
