# ChatGPT Desktop on Ubuntu — MCP Secret Service Environment

## Environment

- **OS:** Ubuntu 26.04.1 LTS
- **Client:** ChatGPT Desktop for Linux (Electron)
- **Embedded backend:** Codex CLI 0.160.1
- **MCP transport:** stdio
- **Launcher:** `mcp-launcher` (Python, installed with `uv tool`)
- **Credential storage:** GNOME Keyring via `secret-tool` / D-Bus Secret Service
- **Configuration:** `~/.codex/config.toml`
- **Diagnostics:** `~/.codex/logs_2.sqlite`
- **Observed:** October 12, 2026

## Problem

ChatGPT Desktop successfully loaded MCP server definitions from `~/.codex/config.toml`, but OpenProject and Outline MCP servers failed to initialize.

The Desktop application displayed:

```text
Unable to sync imports
```

Both servers worked correctly from an interactive terminal and Cursor using the same `mcp-launcher` profiles.

The embedded Codex backend recognized both servers as enabled, but their tools were unavailable.

## Root Cause

ChatGPT Desktop's embedded Codex backend did not reliably propagate the Linux session environment required for GNOME Keyring access into MCP subprocesses.

`mcp-launcher` retrieves credentials using `secret-tool lookup`. When launched by Codex without explicit environment forwarding, both credential lookups failed:

```text
mcp-launcher: secret OPENPROJECT_API_KEY was not found
mcp-launcher: secret OUTLINE_API_KEY was not found
```

The launcher exited before the MCP initialization handshake could complete.

Codex subsequently reported:

```text
MCP server startup failed
handshaking with MCP server failed:
connection closed: initialize response
```

**The credentials were present in GNOME Keyring.** The issue was subprocess environment propagation, not missing credentials or incorrect keyring attributes.

The exact internal environment-filtering behavior of Codex was not established.

## Resolution

Explicitly forward Linux session environment variables using the MCP server's `env_vars` configuration.

Recommended configuration:

```toml
[mcp_servers.openproject]
command = "/home/alex/.local/bin/mcp-launcher"
args = ["run", "openproject", "--profile", "alex-rw"]
env_vars = [
  "DBUS_SESSION_BUS_ADDRESS",
  "XDG_RUNTIME_DIR"
]
enabled = true

[mcp_servers.outline]
command = "/home/alex/.local/bin/mcp-launcher"
args = ["run", "outline", "--profile", "alex-rw"]
env_vars = [
  "DBUS_SESSION_BUS_ADDRESS",
  "XDG_RUNTIME_DIR"
]
enabled = true
```

The executable paths and profiles are installation-specific.

Neither API keys nor other credential values need to be added to `config.toml`.

### Minimal configuration experiments

Two independent configurations were tested successfully after restarting ChatGPT Desktop:

| MCP server | Explicit `env_vars` | Result |
|---|---|---|
| OpenProject | `["DBUS_SESSION_BUS_ADDRESS"]` | Success |
| Outline | `["XDG_RUNTIME_DIR"]` | Success |

This indicates that either variable was sufficient in the tested environment, although the tests involved different MCP servers.

`DBUS_SESSION_BUS_ADDRESS` directly identifies the D-Bus session bus.

`XDG_RUNTIME_DIR` identifies the user's runtime directory, normally containing the session bus socket at `$XDG_RUNTIME_DIR/bus`.

For durable configuration, forward both.

## Diagnostic Procedure

### 1. Identify the embedded Codex backend

ChatGPT Desktop installed its backend at:

```text
/usr/lib/chatgpt/resources/codex
```

The standalone `codex` command was not installed on the system.

Inspect registered MCP servers:

```bash
/usr/lib/chatgpt/resources/codex mcp list
```

A server appearing as `enabled` does not establish that its process initialized or that its tools are available.

### 2. Inspect structured Codex logs

The embedded backend stored diagnostic records in:

```text
~/.codex/logs_2.sqlite
```

Relevant SQLite table:

```text
logs
  ts
  ts_nanos
  level
  target
  feedback_log_body
```

Query MCP startup failures:

```bash
python3 - <<'PY'
import sqlite3
from pathlib import Path

p = Path.home() / ".codex/logs_2.sqlite"
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)

rows = con.execute("""
    SELECT level, target, feedback_log_body
    FROM logs
    WHERE feedback_log_body LIKE '%MCP server startup failed%'
       OR feedback_log_body LIKE '%secret%not found%'
    ORDER BY ts DESC, ts_nanos DESC
    LIMIT 30
""")

for level, target, body in rows:
    print(f"[{level}] {target}: {body}")

con.close()
PY
```

Review output for sensitive information before sharing.

### 3. Compare Desktop and terminal environments

Inspect the running backend's environment through `/proc/<pid>/environ`.

In the observed case:

| Variable | Terminal | Embedded Codex |
|---|---|---|
| `DBUS_SESSION_BUS_ADDRESS` | Set | Set |
| `XDG_RUNTIME_DIR` | Set | Set |
| `GNOME_KEYRING_CONTROL` | Set | Missing |
| `HOME` | Set | Set |
| `XDG_CONFIG_HOME` | Missing | Missing |

Despite both D-Bus variables being present in the embedded backend, credential lookup failed in its MCP subprocesses.

### 4. Verify credential lookup independently

Both credentials were successfully retrieved using `secret-tool` with the embedded Codex process's captured environment.

The complete `mcp-launcher run` command also succeeded when executed with that environment.

This isolated the discrepancy to the actual MCP subprocess launch path, rather than the launcher, credentials, or embedded backend's parent environment.

### 5. Verify MCP initialization

Both servers successfully responded to JSON-RPC `initialize` requests outside ChatGPT Desktop, negotiating MCP protocol version `2025-03-26`.

This confirmed that the MCP servers themselves were operational.

## Implementation Guidance for mcp-launcher

The launcher does not need to change its credential injection architecture.

- Continue resolving secrets through the system keyring at process startup.
- Continue using `exec` to replace the launcher with the configured MCP server.
- Keep credentials out of MCP client configuration files.
- Document `env_vars` as a client-specific requirement for ChatGPT Desktop/Codex on Linux.
- Consider distinguishing missing credentials from unavailable Secret Service access in launcher diagnostics.

### Troubleshooting rule

When `mcp-launcher` successfully retrieves credentials from a terminal but reports missing secrets inside a GUI-hosted MCP client, verify the child process's D-Bus session environment before modifying credentials.

Explicitly forwarding `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` is the confirmed workaround for the environment tested here.

## Limitations

The following remain unverified:

- Whether the behavior affects other Ubuntu releases or ChatGPT Desktop versions.
- Whether either variable alone works consistently across different desktop sessions.
- Whether Codex intentionally filters these variables or the behavior is a defect.
- Whether the generic “Unable to sync imports” notification was directly caused by the MCP failures.

The observed MCP startup failures and their resolution are confirmed; the broader Desktop import-sync behavior was not independently isolated.
