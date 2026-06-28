"""Leveled, secret-safe logging for the Action (Phase 8).

A thin wrapper over stdlib ``logging`` that:
- writes to stderr so it never pollutes stdout report paths,
- defaults to INFO and flips to DEBUG when ``CODEGUARDIAN_DEBUG`` is truthy,
- redacts secret-shaped substrings from every message before emitting, so a
  token or key can never reach the log at any level (strict rule #6).

Never log full source; callers pass short, structured messages.
"""

from __future__ import annotations

import logging
import os
import sys

from .security import redact

_LOGGER_NAME = "codeguardian"
_TRUTHY = {"1", "true", "yes", "on", "debug"}
_configured = False


def debug_enabled(env: dict | None = None) -> bool:
    env = env if env is not None else os.environ
    return env.get("CODEGUARDIAN_DEBUG", "").strip().lower() in _TRUTHY


class _RedactFilter(logging.Filter):
    """Redact secret-shaped text from the rendered message."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:  # noqa: BLE001 - logging must never raise
            pass
        return True


def get_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("CodeGuardian %(levelname)s: %(message)s"))
        handler.addFilter(_RedactFilter())
        logger.addHandler(handler)
        logger.propagate = False
        _configured = True
    logger.setLevel(logging.DEBUG if debug_enabled() else logging.INFO)
    return logger
