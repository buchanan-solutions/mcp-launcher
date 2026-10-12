# ./tests/test_secrets.py
import json
import stat
from pathlib import Path

import pytest

from mcp_launcher.config import SecretRef
from mcp_launcher.errors import LaunchError
from mcp_launcher.secrets import SecretTool

REF = SecretRef(service="demo", profile="readonly", key="api")
LEAK = "SENTINEL-SHOULD-NOT-LEAK"
SECRET = "super-secret-value"


def _write_tool(directory: Path, stdout: bytes, code: int, stderr: bytes = b"") -> Path:
    script = directory / "secret-tool"
    payload = {
        "stdout_b64": stdout.hex(),
        "stderr": stderr.decode("utf-8", "replace"),
        "code": code,
    }
    blob = directory / "response.json"
    blob.write_text(json.dumps(payload), encoding="utf-8")
    script.write_text(
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
data = json.loads(Path({str(blob)!r}).read_text())
Path({str(directory / "calls.log")!r}).write_text(json.dumps(sys.argv[1:]))
sys.stdout.buffer.write(bytes.fromhex(data["stdout_b64"]))
sys.stderr.write(data["stderr"])
raise SystemExit(data["code"])
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_lookup_returns_exact_bytes(tmp_path: Path) -> None:
    script = _write_tool(tmp_path, SECRET.encode(), 0)
    assert SecretTool(str(script)).lookup("TOKEN", REF) == SECRET
    recorded = json.loads((tmp_path / "calls.log").read_text())
    assert recorded == ["lookup", "service", "demo", "profile", "readonly", "key", "api"]


def test_missing_secret_omits_stderr_and_value(tmp_path: Path) -> None:
    script = _write_tool(tmp_path, SECRET.encode(), 1, stderr=LEAK.encode())
    with pytest.raises(LaunchError, match="was not found") as caught:
        SecretTool(str(script)).lookup("TOKEN", REF)
    message = str(caught.value)
    assert SECRET not in message
    assert LEAK not in message
    assert "service='demo'" in message


def test_invalid_utf8_omits_the_secret_text(tmp_path: Path) -> None:
    script = _write_tool(tmp_path, b"sekret\xff", 0)
    with pytest.raises(LaunchError, match="not valid UTF-8") as caught:
        SecretTool(str(script)).lookup("TOKEN", REF)
    assert "sekret" not in str(caught.value)


def test_missing_executable() -> None:
    with pytest.raises(LaunchError, match="secret-tool was not found"):
        SecretTool("/no/such/secret-tool").lookup("TOKEN", REF)
