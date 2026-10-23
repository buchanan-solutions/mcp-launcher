# Streamable HTTP through stdio

The optional proxy exposes one Streamable HTTP MCP endpoint as a stdio MCP server. FastMCP manages the upstream client; your agent manages the stdio subprocess. It does not start Strapi or manage a shared daemon.

## Install

From a checkout:

```bash
uv tool install --python 3.13 '.[proxy]'
```

From GitHub after this change is published:

```bash
uv tool install --python 3.13 'mcp-launcher[proxy] @ git+https://github.com/buchanan-solutions/mcp-launcher.git@main'
```

For development, use `uv sync --extra proxy`. The base install remains usable without FastMCP; only the `proxy` command requires the extra. Linux remains the supported platform.

## Use without the keyring launcher

Have the host supply the named environment variable to its stdio subprocess, then run:

```bash
mcp-launcher proxy --url http://127.0.0.1:1337/mcp \
  --bearer-token-env STRAPI_MCP_ADMIN_TOKEN
```

The option accepts an environment variable name, never the credential value. An absent, empty, or invalid credential fails before serving. Omit the option for an unauthenticated endpoint. URLs must use HTTP or HTTPS, without embedded user information or fragments. Use HTTPS for a live endpoint.

Only MCP traffic goes to stdout. Diagnostics go to stderr. Upstream discovery errors are reported rather than silently producing an empty tool list. Upstream connections are lazy: process startup alone does not prove credentials or server availability. Token changes require restarting the proxy.

## Separate local and live Strapi servers with keyring credentials

These examples assume Strapi expects `Authorization: Bearer <credential>`. If you call this credential a session ID, first confirm that it is accepted as a bearer token. An MCP `Mcp-Session-Id` transport header is different and is managed by FastMCP; do not store it as this bearer credential.

Store two independent credentials (the values are entered at the prompt):

```bash
secret-tool store --label="Strapi local MCP" service strapi profile local key api
secret-tool store --label="Strapi live MCP" service strapi profile live key api
```

Add these entries to your launcher configuration, replacing the executable paths and fictional live URL:

```yaml
version: 1
servers:
  strapi-local:
    command:
      - /home/you/.local/bin/mcp-launcher
      - proxy
      - --url
      - http://127.0.0.1:1337/mcp
      - --bearer-token-env
      - STRAPI_MCP_ADMIN_TOKEN
    profiles:
      local:
        secrets:
          STRAPI_MCP_ADMIN_TOKEN:
            service: strapi
            profile: local
            key: api
  strapi-live:
    command:
      - /home/you/.local/bin/mcp-launcher
      - proxy
      - --url
      - https://cms.example.test/mcp
      - --bearer-token-env
      - STRAPI_MCP_ADMIN_TOKEN
    profiles:
      live:
        secrets:
          STRAPI_MCP_ADMIN_TOKEN:
            service: strapi
            profile: live
            key: api
```

Each server process gets its own credential despite using the same environment variable name. `run` resolves the keyring entry and replaces itself with `proxy`; there is no persistent outer launcher process.

For Codex, define both stdio servers:

```toml
[mcp_servers.strapi-local]
command = "/home/you/.local/bin/mcp-launcher"
args = ["run", "strapi-local", "--profile", "local"]
env_vars = ["DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"]
enabled = true

[mcp_servers.strapi-live]
command = "/home/you/.local/bin/mcp-launcher"
args = ["run", "strapi-live", "--profile", "live"]
env_vars = ["DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"]
enabled = false
```

Enable local alone when rehearsing changes against test data. Enable live alone when changing production data. You can enable both for comparisons, naming `strapi-local` or `strapi-live` explicitly in your request. An enabled flag controls availability; credential permissions determine what each server can change. Restart the affected MCP connections after configuration changes.

For Cursor, use the same `command` and `args` in two `mcpServers` entries and toggle each entry in Cursor's MCP settings. See [client setup](usage.md) for the JSON structure.

For remote SSH execution, install the proxy extra on the machine running the subprocess. `127.0.0.1` means that machine. Configure the host's remote stdio execution separately, and ensure the remote launcher can reach its own unlocked keyring. Forwarding local D-Bus paths does not make a remote keyring accessible.

## Scope and verification

The bridge delegates discovery, calls, and MCP transport behavior to FastMCP. It adds a dependency and an extra protocol hop compared with native HTTP. No custom protocol implementation, credential cache, OAuth login flow, or automatic keyring unlock is added.

Run `uv run --extra proxy pytest` to include authenticated HTTP-to-stdio integration tests. Without the extra, those integration tests skip; core CLI validation still runs.
