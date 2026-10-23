"""Reject unsupported source builds, including editable installations."""

import sys

if sys.platform != "linux":
    raise RuntimeError(
        "mcp-launcher currently supports Linux only. macOS and Windows support is planned. "
        "See https://github.com/buchanan-solutions/mcp-launcher/blob/main/docs/roadmap.md; "
        "pull requests are welcome."
    )

from setuptools import setup

setup()
