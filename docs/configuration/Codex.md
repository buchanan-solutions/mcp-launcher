# Codex and ChatGPT Desktop on Linux

Configure the launcher as an MCP subprocess in `~/.codex/config.toml`:

```toml
[mcp_servers.openproject]
command = "/home/you/.local/bin/mcp-launcher"
args = ["run", "openproject", "--profile", "your-profile"]
env_vars = ["DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"]
enabled = true
```

Use the executable path from `uv tool dir --bin`, your server name, and your profile. `env_vars` names existing host environment variables to forward; it does not contain their values or your API credentials. Restart the client/server after changes.

## Why forward the session environment?

The launcher calls `secret-tool`, which communicates with the login session's Secret Service over D-Bus. `DBUS_SESSION_BUS_ADDRESS` identifies that session bus. `XDG_RUNTIME_DIR` identifies the user's runtime directory, commonly containing the bus socket. A GUI client's subprocess environment may omit the context needed to reach the same keyring that works in a terminal.

In the observed ChatGPT Desktop environment, explicitly forwarding both variables resolved credential lookup failures. The inferred explanation is a difference in the MCP subprocess environment; the exact internal filtering behavior was not established. Forwarding names only works if the client itself inherited valid values from the desktop session. It does not install, start, or unlock a keyring.

Use `mcp-launcher secrets status` in the relevant launch environment to inspect prerequisites. A successful check in a terminal alone does not establish that the GUI subprocess receives the same environment. See the [original Ubuntu investigation](../chatgpt-desktop-ubuntu-mcp-keyring.md) for evidence and limitations.
