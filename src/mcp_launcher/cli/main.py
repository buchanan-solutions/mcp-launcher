# ./src/mcp_launcher/cli/main.py
"""Console-script entry for ``mcp-launcher``."""

from __future__ import annotations

from pathlib import Path

import typer
from pytools.logging.one_shot import one_shot

from mcp_launcher.config import default_config_path, load_config
from mcp_launcher.diagnostics import secrets_status
from mcp_launcher.errors import LaunchError
from mcp_launcher.launch import Launcher
from mcp_launcher.listing import render_listing
from mcp_launcher.platforms import require_linux
from mcp_launcher.scaffold import InstallStatus, install_example_config
from mcp_launcher.secrets import SecretTool

app = typer.Typer(
    name="mcp-launcher",
    help="Launch an MCP server command with a named keyring profile.",
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)


@app.callback()
def check_platform() -> None:
    """Require Linux for command execution (help remains available)."""
    try:
        require_linux()
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None


secrets_app = typer.Typer(
    help=(
        "Inspect Linux keyring prerequisites. Manage credentials with secret-tool.\n\n"
        "Store or replace an Outline personal API credential:\n\n"
        "\b\n"
        '  secret-tool store --label="Outline personal API" \\\n'
        "    service outline profile personal key api\n\n"
        "Press Enter, then enter the secret at the hidden prompt.\n\n"
        "Match the YAML attributes: service=outline, profile=personal, key=api. "
        "The label is descriptive; the environment variable name belongs in YAML.\n\n"
        "Inspect configured secret variable names (no keyring access):\n\n"
        "\b\n"
        "  mcp-launcher list outline\n\n"
        "There is no secrets list command. Browse stored entries with your desktop "
        "keyring manager (Ubuntu/GNOME: Passwords and Keys). "
        "Status checks prerequisites, not stored credentials. See docs/secrets.md."
    ),
    no_args_is_help=True,
)
app.add_typer(secrets_app, name="secrets")


@secrets_app.command("status")
def status() -> None:
    """Check metadata only; never read secrets, unlock, install, or start a provider.

    Exit 0 means prerequisites were observed ready; exit 1 means missing, locked,
    or unknown. This does not verify that any configured credential exists.
    """
    lines, ready = secrets_status()
    typer.echo("\n".join(lines))
    if not ready:
        raise typer.Exit(code=1)


@app.command("path")
def config_path(
    config: Path | None = typer.Option(None, "--config", help="Use an explicit config path."),
) -> None:
    """Print the absolute config path, even before it exists.

    Honors XDG_CONFIG_HOME. Edit with: nano "$(mcp-launcher path)".
    """
    destination = (config if config is not None else default_config_path()).expanduser()
    typer.echo(str(destination.absolute()))


@app.command("proxy")
def proxy_command(
    url: str | None = typer.Option(None, "--url", help="Upstream Streamable HTTP MCP URL."),
    url_env: str | None = typer.Option(
        None, "--url-env", help="Environment variable containing the URL."
    ),
    bearer_token: str | None = typer.Option(
        None, "--bearer-token", help="Literal bearer token (visible in process arguments)."
    ),
    bearer_token_env: str | None = typer.Option(
        None, "--bearer-token-env", help="Environment variable containing the bearer token."
    ),
) -> None:
    """Expose an HTTP MCP server over stdio (requires the proxy extra)."""
    from mcp_launcher.proxy import serve_proxy

    one_shot(root_level="WARNING", rich=False)
    try:
        serve_proxy(url, bearer_token_env, url_env=url_env, bearer_token=bearer_token)
    except LaunchError as exc:
        typer.echo(f"mcp-launcher: {exc}", err=True)
        raise typer.Exit(code=1) from None
    except Exception:
        typer.echo(
            "mcp-launcher: proxy failed; check upstream connectivity and authentication", err=True
        )
        raise typer.Exit(code=1) from None


@app.command("run", no_args_is_help=True)
def run(
    server: str = typer.Argument(
        metavar="SERVER",
        help="Server name from the configuration file.",
    ),
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Profile to apply. A profile is required; there is no default.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        help=(
            "Configuration file. Defaults to $XDG_CONFIG_HOME/mcp-launcher/config.yaml "
            "or ~/.config/mcp-launcher/config.yaml."
        ),
    ),
    cwd: Path | None = typer.Option(
        None,
        "--cwd",
        help="Working directory for the server. Defaults to the caller's working directory.",
    ),
    command: list[str] | None = typer.Argument(
        None,
        help="Replacement command. Everything after -- is passed through unchanged.",
        metavar="[COMMAND]...",
    ),
) -> None:
    """Launch a configured command with one named environment profile.

    The launcher is Python. The command it starts can be any executable.
    Retrieved secrets are placed in the child environment and are never printed.
    """
    # rich=False keeps pytools on a stderr stream handler. Rich's console
    # defaults to stdout, which would corrupt stdio MCP traffic.
    one_shot(root_level="WARNING", rich=False)
    try:
        _launch(server=server, profile=profile, config=config, cwd=cwd, command=command)
    except LaunchError as exc:
        typer.echo(f"mcp-launcher: {exc}", err=True)
        raise typer.Exit(code=1) from None


@app.command("list")
def list_servers(
    server: str | None = typer.Argument(
        None,
        metavar="[SERVER]",
        help="Server to describe. Omit to print every server name.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        help=(
            "Configuration file. Defaults to $XDG_CONFIG_HOME/mcp-launcher/config.yaml "
            "or ~/.config/mcp-launcher/config.yaml."
        ),
    ),
) -> None:
    """Show configured commands and environment names. Secret values stay hidden."""
    config_path = (config if config is not None else default_config_path()).expanduser()
    try:
        loaded = load_config(config_path)
        listing = render_listing(loaded, server)
    except LaunchError as exc:
        typer.echo(f"mcp-launcher: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(listing, nl=False)


@app.command("init")
def init(
    config: Path | None = typer.Option(
        None,
        "--config",
        help=(
            "Where to write the example. Defaults to $XDG_CONFIG_HOME/mcp-launcher/config.yaml "
            "or ~/.config/mcp-launcher/config.yaml."
        ),
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Write the example without asking. An existing file is still left unchanged.",
    ),
) -> None:
    """Install the example configuration when that file is not already present."""
    destination = (config if config is not None else default_config_path()).expanduser()
    try:
        status = install_example_config(
            destination,
            assume_yes=yes,
            confirm=_confirm,
        )
    except typer.Abort:
        typer.echo(
            "mcp-launcher: pass --yes to install the example configuration without a prompt",
            err=True,
        )
        raise typer.Exit(code=1) from None
    except LaunchError as exc:
        typer.echo(f"mcp-launcher: {exc}", err=True)
        raise typer.Exit(code=1) from None
    if status is InstallStatus.EXISTS:
        typer.echo(
            f"mcp-launcher: configuration already exists at {destination}; "
            "not overwriting with defaults",
            err=True,
        )
        return
    if status is InstallStatus.DECLINED:
        typer.echo("Not installed.")
        return
    typer.echo(f"Installed example configuration at {destination}")


def _confirm(question: str) -> bool:
    return typer.confirm(question, default=False)


def _launch(
    *,
    server: str,
    profile: str,
    config: Path | None,
    cwd: Path | None,
    command: list[str] | None,
) -> None:
    config_path = (config if config is not None else default_config_path()).expanduser()
    loaded = load_config(config_path)
    Launcher(SecretTool()).run(
        config=loaded,
        server_name=server,
        profile_name=profile,
        command_override=command,
        cwd=cwd,
    )


def main() -> None:
    app()
