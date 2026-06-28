"""Shared retry + timeout HTTP helper (Phase 8).

Every outbound network call (GitHub, Groq, HF) goes through ``request`` so it
gets a bounded, jittered exponential backoff and an explicit timeout. Retries
cover only transient failures — connection/timeout errors, HTTP 429, and 5xx —
so a flaky network or a brief rate limit does not turn into a crashed run.
Non-transient responses (e.g. 4xx other than 429) return immediately; callers
still own ``raise_for_status`` semantics.
"""

from __future__ import annotations

import random
import time
from typing import Optional

import requests

from .log import get_logger

DEFAULT_TIMEOUT = 30
_MAX_ATTEMPTS = 3
_BASE_DELAY = 0.5
_MAX_DELAY = 8.0
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _sleep_seconds(attempt: int, retry_after: Optional[str]) -> float:
    if retry_after:
        try:
            return min(float(retry_after), _MAX_DELAY)
        except ValueError:
            pass
    backoff = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
    return backoff * (0.5 + random.random() / 2)  # full-ish jitter


def request(
    method: str,
    url: str,
    *,
    max_attempts: int = _MAX_ATTEMPTS,
    timeout: int = DEFAULT_TIMEOUT,
    sleep=time.sleep,
    **kwargs,
) -> requests.Response:
    """Perform an HTTP request with bounded retries on transient failures.

    Returns the final ``Response`` (the caller decides whether to raise). On
    repeated transport errors the last exception is raised.
    """
    log = get_logger()
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == max_attempts:
                raise
            delay = _sleep_seconds(attempt, None)
            log.debug("HTTP %s %s failed (%s); retry %d/%d in %.2fs",
                      method, url, type(exc).__name__, attempt, max_attempts, delay)
            sleep(delay)
            continue

        if resp.status_code in _RETRY_STATUS and attempt < max_attempts:
            delay = _sleep_seconds(attempt, resp.headers.get("Retry-After"))
            log.debug("HTTP %s %s -> %d; retry %d/%d in %.2fs",
                      method, url, resp.status_code, attempt, max_attempts, delay)
            sleep(delay)
            continue
        return resp

    # Unreachable in practice (loop returns or raises), but keep types happy.
    if last_exc:
        raise last_exc
    raise RuntimeError("request: exhausted attempts without a response")
