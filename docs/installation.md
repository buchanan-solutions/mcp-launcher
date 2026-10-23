# Installation and updates

Linux is the supported platform. Install [uv](https://docs.astral.sh/uv/), and ensure Git is available. Select Python 3.13 explicitly in the examples below.

## Choose a Git reference

```bash
# Latest commit on main at installation time
uv tool install --python 3.13 "git+https://github.com/buchanan-solutions/mcp-launcher.git@main"

# A release tag, once that tag has been published
uv tool install --python 3.13 "git+https://github.com/buchanan-solutions/mcp-launcher.git@v0.1.0"

# An exact commit: replace FULL_COMMIT_SHA with its full hash
uv tool install --python 3.13 "git+https://github.com/buchanan-solutions/mcp-launcher.git@FULL_COMMIT_SHA"
```

Branches can advance. Tags name releases and should be treated as fixed; a full commit SHA identifies an exact source revision. These source pins do not lock every dependency: tool installation resolves dependencies from package metadata rather than using this repository's `uv.lock` as an installation lockfile.

## Update or switch references

Normal upgrades retain the installation's source and constraints:

```bash
uv tool upgrade mcp-launcher
```

To explicitly refresh and reinstall from the latest `main`:

```bash
uv tool install --python 3.13 --reinstall "git+https://github.com/buchanan-solutions/mcp-launcher.git@main"
```

Use the same install command with a different `@TAG` or `@FULL_COMMIT_SHA` to switch references or roll back. Upgrading a fixed reference does not switch to a newer release tag. There is no `uv tool refetch` command. Already-running MCP servers need to be restarted to use an updated installation.

For a local clone, pull the desired revision and rerun `uv tool install --python 3.13 --reinstall .` from that checkout. For development, `uv tool install --python 3.13 --editable .` follows local source edits; reinstall after changing dependency or package metadata.

See [uv tool management](https://docs.astral.sh/uv/concepts/tools/), the [install command reference](https://docs.astral.sh/uv/reference/cli/#uv-tool-install), and [Git reference syntax](https://docs.astral.sh/uv/pip/packages/).

## Keyring prerequisites and current platform behavior

Installation adds the Python tool. It does not install `secret-tool`, install or select a keyring provider, unlock a keyring, or migrate credentials. `mcp-launcher init` creates only an example configuration.

Secret-backed profiles use `secret-tool` to talk to the login session's freedesktop Secret Service. GNOME Keyring is a common provider on Ubuntu desktops. Other providers exposing that interface may work, but are not currently verified by this project. A desktop session may already provide a service; a minimal or headless Linux installation may not.

On Debian/Ubuntu, if `secret-tool` is missing, install its client package yourself:

```bash
sudo apt install libsecret-tools
```

This supplies the client, not a guarantee of a running, unlocked keyring service. Use your desktop's keyring settings or administrator guidance to configure a provider. See [credential setup](usage.md) and [GUI session troubleshooting](chatgpt-desktop-ubuntu-mcp-keyring.md).

Currently, the CLI reads secrets; use `secret-tool store` or a desktop keyring manager to store and update them. Use `mcp-launcher secrets status` for read-only prerequisite diagnostics; see [secrets management](secrets.md).

macOS and Windows are unsupported. Source builds (including editable installs) reject non-Linux systems. The CLI also rejects execution on unsupported systems, covering prebuilt wheels whose installation bypasses source checks. Python packaging does not provide a universal OS install restriction for an already-built pure Python wheel. Native platform integrations are [planned](roadmap.md).
