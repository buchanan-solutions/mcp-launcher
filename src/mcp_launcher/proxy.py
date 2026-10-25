"""Optional stdio-to-Streamable-HTTP bridge backed by FastMCP."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from mcp_launcher.errors import LaunchError


def serve_proxy(
    url: str | None = None,
    bearer_token_env: str | None = None,
    *,
    url_env: str | None = None,
    bearer_token: str | None = None,
) -> None:
    """Resolve explicit options, then serve an HTTP upstream over stdio."""
    if (url is None) == (url_env is None):
        raise LaunchError("provide exactly one of --url or --url-env")
    if bearer_token is not None and bearer_token_env is not None:
        raise LaunchError("provide only one of --bearer-token or --bearer-token-env")
    if url_env is not None:
        url = os.environ.get(url_env)
        if not url:
            raise LaunchError("proxy URL environment variable is missing or empty")
    if url is None:
        raise LaunchError("proxy URL is missing")
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port != 0
    except ValueError:
        valid = False
    if not valid or parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise LaunchError("proxy URL must be HTTP(S), without user info or a fragment")
    headers = {}
    if bearer_token is not None or bearer_token_env is not None:
        token = bearer_token if bearer_token_env is None else os.environ.get(bearer_token_env)
        if not token or any(c in token for c in "\r\n\x00"):
            raise LaunchError("proxy bearer token is missing, empty, or invalid")
        headers["Authorization"] = f"Bearer {token}"
    try:
        from fastmcp.client.transports import StreamableHttpTransport
        from fastmcp.server import create_proxy
    except ImportError:
        raise LaunchError(
            "proxy requires the optional dependency: install mcp-launcher[proxy]"
        ) from None

    transport = StreamableHttpTransport(url=url, headers=headers)
    proxy = create_proxy(
        transport,
        name="mcp-launcher-proxy",
        provider_error_strategy="raise",
        mask_error_details=True,
    )
    # Discovery failures must reach the client instead of silently hiding tools.
    proxy.run(transport="stdio", show_banner=False)
