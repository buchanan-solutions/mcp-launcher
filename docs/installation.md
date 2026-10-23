# Installation and updates

Linux is the supported platform. Install [uv](https://docs.astral.sh/uv/), and ensure Git is available. Select Python 3.13 explicitly in the examples below.

## Ubuntu setup on a new machine

Run these commands on the machine that will execute `mcp-launcher` (SSH into it first for remote execution). The repository is public: Git must be installed, but you do not need a GitHub login or a manually maintained clone.

Install system prerequisites:

```bash
sudo apt update
sudo apt install git curl ca-certificates
```

Install uv using its [official installer](https://docs.astral.sh/uv/getting-started/installation/), if not already available:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
. "$HOME/.local/bin/env"
```

Install both the keyring launcher and optional HTTP-to-stdio proxy directly from GitHub:

```bash
uv tool install --python 3.13 'mcp-launcher[proxy] @ git+https://github.com/buchanan-solutions/mcp-launcher.git@main'
uv tool update-shell
mcp-launcher --help
mcp-launcher proxy --help
uv tool dir --bin
```

Restart your shell if PATH changes are needed. Use the absolute `mcp-launcher` executable path under the directory printed by `uv tool dir --bin` in agent configuration. The GitHub command installs the pushed revision of `main`; uncommitted or unpushed local changes are unavailable there.

uv fetches the source into its cache, builds the package, and installs its declared Python dependencies into an isolated environment. It can download Python 3.13 automatically when unavailable. No separate pip, virtualenv, FastMCP, Node.js, or system Python 3.13 installation is needed for the proxy. The core dependencies are pytools, Pydantic, and PyYAML; the `proxy` extra additionally installs FastMCP (`>=3.4.11,<4`) and its dependencies. Installing the extra includes both commands. Omit the extra for the smaller core launcher. See [uv tool documentation](https://docs.astral.sh/uv/guides/tools/).

### Optional keyring support on Ubuntu

For keyring-backed profiles:

```bash
sudo apt install libsecret-tools
mcp-launcher secrets status
```

An existing Ubuntu desktop login commonly supplies GNOME Keyring and session D-Bus. On a desktop missing the provider or its manager, install:

```bash
sudo apt install gnome-keyring seahorse
```

`seahorse` supplies the Passwords and Keys GUI; it is optional. `busctl` (normally supplied by `systemd` on Ubuntu) is used only by prerequisite diagnostics. Installing these packages does not itself establish an unlocked keyring in an SSH session. A headless/SSH host needs a deliberately configured Secret Service session and unlock mechanism; there is no universal package-install command that completes that setup. Alternatively, use `proxy` directly with a host-supplied environment variable, which needs neither `secret-tool` nor a keyring.

For keyring use, create and edit the configuration, then store the credentials on this machine:

```bash
mcp-launcher init
nano "$(mcp-launcher path)"
```

Install an editor of your choice if `nano` is unavailable. Configuration and secrets are not copied from another computer by installation. See [secrets management](secrets.md) and the [local/live Strapi example](proxy.md). Strapi or another upstream HTTP server must already be running and reachable; the proxy does not install or start it.

On other Linux distributions, install the equivalent Git, curl/CA certificates, and optional libsecret client and Secret Service provider with your distribution's package manager. Linux support does not imply every keyring provider or headless session configuration has been verified.

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
