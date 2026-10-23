# Configuration and usage

Install the bundled example, then edit it:

```bash
mcp-launcher init
nano "$(mcp-launcher path)"
```

The prompt names the destination. The default is `$XDG_CONFIG_HOME/mcp-launcher/config.yaml`, or `~/.config/mcp-launcher/config.yaml` when `XDG_CONFIG_HOME` is unset. `--config PATH` selects another file for both `init` and `run`. `--yes` skips the question.

`init` is safe to repeat. If that file, directory, or symlink already exists, it is left unchanged.

```text
mcp-launcher: configuration already exists at ~/.config/mcp-launcher/config.yaml; not overwriting with defaults
```

```yaml
version: 1

env:
  LOG_LEVEL: warning

servers:
  openproject:
    command:
      - /opt/openproject-mcp/bin/openproject-mcp

    env:
      OPENPROJECT_URL: https://projects.example.test

    profiles:
      manufacturing-readonly:
        secrets:
          OPENPROJECT_API_KEY:
            service: openproject
            profile: manufacturing-readonly
            key: api
```

The same fictional file is [`examples/config.yaml`](../examples/config.yaml). `init` installs the copy bundled with the package.

Environment layers are applied in order: the caller's environment, then root `env`, server `env`, and profile `env`. Profile `secrets` are read last and override earlier values of the same name. A profile cannot define the same variable in both `env` and `secrets`.

`command` is optional. It is an argument list, not a shell string. A profile name is required on every launch; there is no implicit profile.

Store a secret with the same attributes the profile names:

```bash
secret-tool store --label='OpenProject manufacturing' \
  service openproject profile manufacturing-readonly key api
```

To confirm the entry exists, use the same attribute list with `lookup`. A hit prints the value to stdout; a miss exits non-zero and prints nothing. Redirect stdout if you only want to test presence:

```bash
secret-tool lookup service openproject profile manufacturing-readonly key api
secret-tool lookup service openproject profile manufacturing-readonly key api >/dev/null
```

The launcher stops if a secret is missing or empty. Error text names the variable and the attributes. It does not print the secret.

## Inspect

`list` reads the configuration and does not contact the keyring. With no server name it prints one server name per line. With a server name it prints that server's command, plain environment values, and the names of variables each profile loads from the keyring. Keyring attributes (`service`, `profile`, `key`) and secret values are omitted.

```bash
mcp-launcher list
mcp-launcher list openproject
```

## Launch

Use the configured command:

```bash
mcp-launcher run openproject --profile manufacturing-readonly
```

Or replace that command entirely. Everything after `--` becomes the argument vector:

```bash
mcp-launcher run openproject --profile manufacturing-readonly -- \
  uv run python tools/openproject_mcp.py
```

```bash
mcp-launcher run openproject --profile manufacturing-readonly -- \
  node server.js --stdio
```

`--cwd PATH` sets the server's working directory. Without it, the caller's directory is kept.

Launcher errors go to stderr so stdio MCP traffic on stdout stays intact. On success the launcher process is replaced, and stdin, stdout, stderr, and signals belong to the server.

## Cursor and Codex

Both clients should run `mcp-launcher run` and pass the server name, profile, and any command override as arguments.

Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "openproject": {
      "command": "mcp-launcher",
      "args": ["run", "openproject", "--profile", "manufacturing-readonly"]
    }
  }
}
```

Codex `~/.codex/config.toml`:

```toml
[mcp_servers.openproject]
command = "mcp-launcher"
args = ["run", "openproject", "--profile", "manufacturing-readonly"]
```

On Linux, ChatGPT Desktop's embedded Codex backend may not forward the session environment that GNOME Keyring needs. If secrets work in a terminal but Codex reports `secret … was not found`, add `env_vars` so D-Bus can reach the keyring (paths and profiles are yours):

```toml
[mcp_servers.openproject]
command = "/home/you/.local/bin/mcp-launcher"
args = ["run", "openproject", "--profile", "your-profile"]
env_vars = ["DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"]
enabled = true
```

Full write-up (diagnostics, SQLite logs, limitations): [docs/chatgpt-desktop-ubuntu-mcp-keyring.md](chatgpt-desktop-ubuntu-mcp-keyring.md).

A project-local server command:

```json
{
  "mcpServers": {
    "openproject": {
      "command": "mcp-launcher",
      "args": [
        "run",
        "openproject",
        "--profile",
        "manufacturing-readonly",
        "--",
        "uv",
        "run",
        "python",
        "tools/openproject_mcp.py"
      ]
    }
  }
}
```

If `mcp-launcher` is not on the client's `PATH`, set `command` to the absolute path from `uv tool dir --bin`.

For prerequisite diagnostics and credential attribute syntax, see [secrets management](secrets.md). For GUI session forwarding, see [Codex setup](configuration/Codex.md).
