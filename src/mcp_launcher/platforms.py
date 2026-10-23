"""Supported execution platforms."""

import sys

UNSUPPORTED = (
    "mcp-launcher currently supports Linux only. macOS and Windows support is on the "
    "roadmap: https://github.com/buchanan-solutions/mcp-launcher/blob/main/docs/roadmap.md. "
    "Contributions via pull request are welcome."
)


def require_linux() -> None:
    if sys.platform != "linux":
        raise RuntimeError(UNSUPPORTED)
