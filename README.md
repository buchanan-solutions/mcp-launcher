# mcp-launcher

One place to define how your coding agents launch MCP servers, with named environment profiles and secrets from your Linux keyring.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/), Git, and Linux. These commands select Python 3.13. Secret-backed profiles also require `secret-tool` (`libsecret-tools` on Debian/Ubuntu) and an unlocked Secret Service keyring, such as GNOME Keyring.

Install directly from GitHub:

```bash
uv tool install --python 3.13 "git+https://github.com/buchanan-solutions/mcp-launcher.git@main"
```

Or install from a local clone:

```bash
git clone https://github.com/buchanan-solutions/mcp-launcher.git
cd mcp-launcher
uv tool install --python 3.13 .
```

Create the example configuration:

```bash
mcp-launcher init
nano "$(mcp-launcher path)"
mcp-launcher secrets status
```

Edit the configuration with your server commands, environments, and keyring references. Install the MCP servers separately.

Store the example profile's API credential, matching its `service`, `profile`, and `key` values:

```bash
secret-tool store --label="OpenProject manufacturing API" \
  service openproject profile manufacturing-readonly key api
```

Press Enter, then enter the credential at the hidden prompt. For other profiles and browsing stored entries, see [secrets management](docs/secrets.md).

Launch:

```bash
mcp-launcher run openproject --profile manufacturing-readonly
```

The example uses fictional settings. Follow the [configuration and client setup guide](docs/usage.md) for a complete setup. If your shell cannot find the command, run `uv tool update-shell` and restart the shell. GUI clients may need the absolute executable path under `uv tool dir --bin`.

### Update

For the latest code from `main`, refresh and reinstall:

```bash
uv tool install --python 3.13 --reinstall "git+https://github.com/buchanan-solutions/mcp-launcher.git@main"
```

For normal upgrades using the existing installation source, use `uv tool upgrade mcp-launcher`. A tag or commit pin stays on that reference. See [pinning and updates](docs/installation.md) and [uv tool management](https://docs.astral.sh/uv/concepts/tools/). Updates leave your configuration and keyring entries in place.

## Why this exists

Using the same MCP servers across several coding agents can mean repeated command definitions and API keys scattered through client configuration files. `mcp-launcher` keeps launch details in one local configuration and credential values in the system keyring. Each client needs only a server name and a profile.

The goal is a small, predictable handoff: resolve the profile, retrieve its secrets, and replace the launcher process with the server. It can start Python, Node, `uvx`, binaries, or any other executable. Each client owns its own server process.

## Design choices

- **Shared configuration, explicit profiles.** Reuse server definitions across Cursor, Codex, and other clients that launch MCP subprocesses. Every launch names its profile.
- **Credentials outside client files.** YAML holds keyring references. Secret values are retrieved at launch and passed in the server environment; the launcher does not print them.
- **Direct execution.** Arguments pass through without a shell or variable expansion. Process replacement keeps standard streams and signals attached to the server.
- **A narrow scope.** No daemon, protocol proxy, shared server pool, or credential cache. The launcher does not speak MCP.

The keyring reduces plaintext credential duplication; it is not a sandbox or an access-control boundary. The server receives its profile's secrets and inherits the caller's environment. A profile named `readonly` only has the permissions of its underlying credentials. Configuration and keyring entries must be set up on each device.

## Documentation

- [Configuration, credentials, and client setup](docs/usage.md)
- [Installation, version pinning, and updates](docs/installation.md)
- [Secrets management and diagnostics](docs/secrets.md)
- [Codex / ChatGPT Desktop setup](docs/configuration/Codex.md)
- [Roadmap](docs/roadmap.md)
- [Example configuration](examples/config.yaml)
- [Ubuntu / ChatGPT Desktop keyring troubleshooting](docs/chatgpt-desktop-ubuntu-mcp-keyring.md) — observations and a verified workaround from a specific environment.

## Development and contributions

```bash
uv sync --group dev
uv run mcp-launcher --help
uv run poe test-unit
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

To follow local edits, use `uv tool install --python 3.13 --editable .`. Optional commit hooks: `uv run pre-commit install`.

Small, focused contributions are welcome. Explain the problem, give an example of the intended behavior, and include tests for behavior changes. Keep stdout available for MCP traffic, avoid logging credential values, and use fictional endpoints and secrets in examples and reports.

Logging uses [buchanan-solutions/pytools](https://github.com/buchanan-solutions/pytools) and goes to stderr. `.env.pytools_logging` in the launch directory can adjust logging; keep the `mcp_launcher` logger at `WARNING` for normal stdio use.

## License

[MIT](LICENSE) © 2026 Alex Buchanan.
