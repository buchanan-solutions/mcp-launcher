# ./src/mcp_launcher/errors.py
"""User-facing launcher failures.

Messages raised as :class:`LaunchError` must describe the problem without
including a retrieved secret value.
"""


class LaunchError(Exception):
    """A failure the caller can correct. The message must not contain secret values."""
