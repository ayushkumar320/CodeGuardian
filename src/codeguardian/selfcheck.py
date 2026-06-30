"""``--selfcheck`` mode (Phase 8).

Validates the environment, GitHub token reachability/scope, and model-provider
configuration, printing a clear pass/fail line per dependency. Returns a process
exit code: 0 when every required check passes, 1 otherwise. Network checks are
best-effort and never raise — an unreachable dependency is a reported failure,
not a crash.
"""

from __future__ import annotations

import os
import shutil
from typing import Optional

from .http import request as http_request
from .log import get_logger
from .models import Provider
from .providers import select_provider

_API = "https://api.github.com"


class _Check:
    def __init__(self, name: str, ok: bool, detail: str, required: bool = True):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.required = required


def _check_git() -> _Check:
    path = shutil.which("git")
    return _Check("git", path is not None, path or "git not found on PATH")


def _check_repo_env() -> _Check:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    return _Check("GITHUB_REPOSITORY", bool(repo), repo or "unset", required=False)


def _check_github_token(env: Optional[dict] = None) -> _Check:
    env = env if env is not None else os.environ
    token = env.get("GITHUB_TOKEN", "")
    if not token:
        return _Check("GITHUB_TOKEN", False, "unset (no GitHub writes possible)")
    try:
        resp = http_request(
            "GET", f"{_API}/rate_limit",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json"},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        return _Check("GITHUB_TOKEN", False, f"unreachable: {type(exc).__name__}")
    if resp.status_code == 200:
        remaining = resp.headers.get("X-RateLimit-Remaining", "?")
        return _Check("GITHUB_TOKEN", True, f"reachable (rate limit remaining {remaining})")
    return _Check("GITHUB_TOKEN", False, f"auth failed (HTTP {resp.status_code})")


def _check_provider(env: Optional[dict] = None) -> _Check:
    env = env if env is not None else os.environ
    provider = select_provider(env)
    if provider == Provider.deterministic:
        return _Check(
            "model provider", False,
            "no GROQ_API_KEY / HF_TOKEN — a model key is required", required=True,
        )
    return _Check("model provider", True, f"selected: {provider.value}", required=True)


def run_selfcheck(env: Optional[dict] = None) -> int:
    log = get_logger()
    checks = [
        _check_git(),
        _check_repo_env(),
        _check_github_token(env),
        _check_provider(env),
    ]
    print("CodeGuardian self-check:")
    failed_required = False
    for c in checks:
        mark = "PASS" if c.ok else ("FAIL" if c.required else "WARN")
        tag = "" if c.required else " (optional)"
        print(f"  [{mark}] {c.name}{tag}: {c.detail}")
        if c.required and not c.ok:
            failed_required = True
    if failed_required:
        log.debug("self-check found a required-dependency failure")
        print("Result: FAIL")
        return 1
    print("Result: PASS")
    return 0
