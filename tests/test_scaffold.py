# ./tests/test_scaffold.py
from pathlib import Path

from mcp_launcher.scaffold import InstallStatus, example_config_text, install_example_config

EXAMPLE = Path(__file__).parents[1] / "examples" / "config.yaml"


def test_packaged_example_matches_repository_example() -> None:
    assert example_config_text() == EXAMPLE.read_text(encoding="utf-8")


def test_install_writes_the_example_when_accepted(tmp_path: Path) -> None:
    destination = tmp_path / "mcp-launcher" / "config.yaml"
    status = install_example_config(
        destination,
        assume_yes=False,
        confirm=lambda question: question == f"Install the example configuration to {destination}?",
    )
    assert status is InstallStatus.CREATED
    assert destination.read_text(encoding="utf-8") == example_config_text()


def test_install_with_yes_does_not_ask(tmp_path: Path) -> None:
    destination = tmp_path / "config.yaml"

    def refuse(question: str) -> bool:
        raise AssertionError(question)

    status = install_example_config(destination, assume_yes=True, confirm=refuse)
    assert status is InstallStatus.CREATED
    assert destination.read_text(encoding="utf-8") == example_config_text()


def test_declined_install_creates_nothing(tmp_path: Path) -> None:
    destination = tmp_path / "config.yaml"
    status = install_example_config(destination, assume_yes=False, confirm=lambda _question: False)
    assert status is InstallStatus.DECLINED
    assert not destination.exists()


def test_existing_file_is_not_overwritten(tmp_path: Path) -> None:
    destination = tmp_path / "config.yaml"
    destination.write_text("mine: true\n", encoding="utf-8")
    status = install_example_config(destination, assume_yes=True, confirm=lambda _question: True)
    assert status is InstallStatus.EXISTS
    assert destination.read_text(encoding="utf-8") == "mine: true\n"


def test_existing_symlink_is_not_replaced(tmp_path: Path) -> None:
    target = tmp_path / "real.yaml"
    target.write_text("mine: true\n", encoding="utf-8")
    destination = tmp_path / "config.yaml"
    destination.symlink_to(target)
    status = install_example_config(destination, assume_yes=True, confirm=lambda _question: True)
    assert status is InstallStatus.EXISTS
    assert destination.is_symlink()
    assert target.read_text(encoding="utf-8") == "mine: true\n"
