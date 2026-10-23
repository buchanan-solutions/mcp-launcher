"""CLI validation and real authenticated HTTP-to-stdio round trips."""

import asyncio
import os
import socket
import subprocess
import sys
import time

import pytest
from typer.testing import CliRunner

from mcp_launcher.cli.main import app


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/server.py",
        "ftp://example.test",
        "http://",
        "http://user:secret@example.test",
        "http://localhost:bad",
    ],
)
def test_rejects_invalid_urls(url):
    result = CliRunner().invoke(app, ["proxy", "--url", url])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "HTTP(S)" in result.stderr
    assert url not in result.stderr


def test_missing_token(monkeypatch):
    monkeypatch.delenv("MCP_TEST_TOKEN", raising=False)
    result = CliRunner().invoke(
        app, ["proxy", "--url", "http://localhost/mcp", "--bearer-token-env", "MCP_TEST_TOKEN"]
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "missing, empty, or invalid" in result.stderr


def test_optional_dependency_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "fastmcp.client.transports", None)
    result = CliRunner().invoke(app, ["proxy", "--url", "http://localhost/mcp"])
    assert result.exit_code == 1
    assert "mcp-launcher[proxy]" in result.stderr


@pytest.mark.parametrize(
    ("token", "wrapped"),
    [("fixture-secret", False), ("wrong-secret", False), ("fixture-secret", True)],
)
def test_authenticated_round_trip(tmp_path, token, wrapped):
    pytest.importorskip("fastmcp")
    import yaml
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    from mcp.shared.exceptions import McpError
    from mcp.types import TextContent

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    fixture = tmp_path / "upstream.py"
    fixture.write_text(
        """from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier
mcp = FastMCP("fixture", auth=StaticTokenVerifier(tokens={"fixture-secret": {"client_id": "test", "scopes": []}}))
@mcp.tool
def echo(value: str) -> str:
    return value
mcp.run(transport="http", host="127.0.0.1", port="""
        + str(port)
        + """, show_banner=False)
"""
    )
    with open(tmp_path / "server.log", "w") as log:
        server = subprocess.Popen([sys.executable, str(fixture)], stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    if server.poll() is not None or time.monotonic() > deadline:
                        pytest.fail("upstream failed to start")
                    time.sleep(0.1)

            args = [
                "-m",
                "mcp_launcher",
                "proxy",
                "--url",
                f"http://127.0.0.1:{port}/mcp",
                "--bearer-token-env",
                "MCP_TEST_TOKEN",
            ]
            env = {"PYTHONPATH": os.path.abspath("src")}
            if wrapped:
                secret_tool = tmp_path / "secret-tool"
                secret_tool.write_text("#!/bin/sh\nprintf fixture-secret")
                secret_tool.chmod(0o700)
                config = tmp_path / "config.yaml"
                config.write_text(
                    yaml.safe_dump(
                        {
                            "version": 1,
                            "servers": {
                                "fixture": {
                                    "command": [sys.executable, *args],
                                    "profiles": {
                                        "test": {
                                            "secrets": {
                                                "MCP_TEST_TOKEN": {
                                                    "service": "fixture",
                                                    "profile": "test",
                                                    "key": "api",
                                                }
                                            }
                                        }
                                    },
                                }
                            },
                        }
                    )
                )
                args = [
                    "-m",
                    "mcp_launcher",
                    "run",
                    "fixture",
                    "--profile",
                    "test",
                    "--config",
                    str(config),
                ]
                env["PATH"] = f"{tmp_path}:{os.environ.get('PATH', '')}"
            else:
                env["MCP_TEST_TOKEN"] = token

            async def exercise():
                transport = StdioTransport(command=sys.executable, args=args, env=env)
                async with Client(transport, timeout=10) as client:
                    tools = await client.list_tools()
                    assert [tool.name for tool in tools] == ["echo"]
                    result = await client.call_tool("echo", {"value": "round-trip"})
                    assert isinstance(result.content[0], TextContent)
                    assert result.content[0].text == "round-trip"

            if token == "fixture-secret":
                asyncio.run(exercise())
            else:
                with pytest.raises(McpError):
                    asyncio.run(exercise())
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
