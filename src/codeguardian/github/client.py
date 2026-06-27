"""Thin GitHub REST client (requests-based).

Only the calls Phase 1 needs: create/update check runs, find/create/update the
sticky comment. Uses GITHUB_TOKEN from the Action environment. All methods are
idempotent-friendly and degrade to no-ops when no token is present (e.g. local
dry runs), so the deterministic path never hard-fails on GitHub I/O.
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from .. import CHECK_NAME, SUMMARY_ANCHOR

_API = "https://api.github.com"
_TIMEOUT = 30


class GitHubClient:
    def __init__(self, token: Optional[str] = None, api_url: str = _API):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.api_url = api_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # --- Check runs -------------------------------------------------------
    def publish_check(
        self,
        owner: str,
        repo: str,
        head_sha: str,
        conclusion: str,
        title: str,
        summary: str,
    ) -> Optional[int]:
        if not self.enabled:
            return None
        url = f"{self.api_url}/repos/{owner}/{repo}/check-runs"
        body = {
            "name": CHECK_NAME,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {"title": title, "summary": summary[:65000]},
        }
        resp = requests.post(url, headers=self._headers(), json=body, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("id")

    # --- Sticky comment ---------------------------------------------------
    def upsert_sticky_comment(
        self, owner: str, repo: str, number: int, body: str
    ) -> Optional[int]:
        if not self.enabled:
            return None
        existing = self._find_sticky(owner, repo, number)
        if existing:
            url = f"{self.api_url}/repos/{owner}/{repo}/issues/comments/{existing}"
            resp = requests.patch(url, headers=self._headers(), json={"body": body}, timeout=_TIMEOUT)
        else:
            url = f"{self.api_url}/repos/{owner}/{repo}/issues/{number}/comments"
            resp = requests.post(url, headers=self._headers(), json={"body": body}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("id")

    def _find_sticky(self, owner: str, repo: str, number: int) -> Optional[int]:
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{number}/comments"
        page = 1
        while True:
            resp = requests.get(
                url,
                headers=self._headers(),
                params={"per_page": 100, "page": page},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            items = resp.json()
            if not items:
                return None
            for c in items:
                if SUMMARY_ANCHOR in (c.get("body") or ""):
                    return c.get("id")
            if len(items) < 100:
                return None
            page += 1

    def reply(self, owner: str, repo: str, number: int, body: str) -> Optional[int]:
        if not self.enabled:
            return None
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{number}/comments"
        resp = requests.post(url, headers=self._headers(), json={"body": body}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("id")
