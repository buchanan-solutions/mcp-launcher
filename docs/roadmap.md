# Roadmap

This document distinguishes available capabilities from proposed work. The project will keep its focus on predictable local MCP process launching. Contributions are welcome; macOS and Windows support are future work.

## Available now

- Linux source-build and CLI execution checks; help remains available on unsupported systems. A prebuilt pure Python wheel can still be installed elsewhere, but execution is rejected.
- `mcp-launcher secrets status`: bounded, read-only checks of client availability, session D-Bus, running Secret Service, and collection lock state. See [secrets management](secrets.md).
- `mcp-launcher path`: an absolute config path for `nano "$(mcp-launcher path)"`, honoring XDG configuration and `--config`.

## Diagnostic improvements

Expand verified providers beyond the initial Ubuntu/GNOME target and improve unknown-state guidance based on real reports. Keep diagnostics read-only and avoid automatic provider installation or selection.

## Configuration editing

A possible `edit` command could honor `$VISUAL` and `$EDITOR`, with a documented fallback.

## Optional credential management

Consider a CLI command to store or replace a profile's credential through the existing provider. Prompt for values without echoing them or putting them in command arguments. This is lower priority than diagnostics and clear instructions for `secret-tool store` and desktop keyring managers.

## Additional platforms

Add native macOS Keychain and Windows Credential Manager integrations, platform-appropriate configuration paths, and verified process behavior before declaring support. Revisit installation restrictions as each platform becomes supported.
