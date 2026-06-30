"""Thin GitHub REST client (requests-based).

Only the calls Phase 1 needs: create/update check runs, find/create/update the
sticky comment. Uses GITHUB_TOKEN from the Action environment. All methods are
idempotent-friendly and degrade to no-ops when no token is present (e.g. local
dry runs), so the deterministic path never hard-fails on GitHub I/O.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from math import ceil
from typing import Optional

import requests

from ..http import request as http_request
from ..log import get_logger
from ..security import find_secrets, safe_output

_log = get_logger()


def _scrub(text: str) -> str:
    """Egress secret-scan: redact any secret-shaped content before posting and
    log (redacted) if something fired, as a defense-in-depth signal (Phase 9)."""
    if find_secrets(text):
        _log.warning("egress secret-scan redacted secret-shaped content before posting")
    return safe_output(text)

from .. import CHECK_NAME, SUMMARY_ANCHOR

_API = "https://api.github.com"
_TIMEOUT = 30
_REPORT_ARTIFACT = "codeguardian-report"
_REPORT_JSON = "codeguardian-report.json"


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
        annotations: Optional[list[dict]] = None,
    ) -> Optional[int]:
        if not self.enabled:
            return None
        output = {"title": _scrub(title), "summary": _scrub(summary)[:65000]}
        if annotations:
            # GitHub accepts up to 50 annotations per request; scrub each message
            # since patch-derived text can contain anything (defense in depth).
            output["annotations"] = [self._scrub_annotation(a) for a in annotations[:50]]
        body = {
            "name": CHECK_NAME,
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": output,
        }
        existing = self._find_check_run(owner, repo, head_sha)
        if existing is not None:
            url = f"{self.api_url}/repos/{owner}/{repo}/check-runs/{existing}"
            resp = http_request("PATCH", url, headers=self._headers(), json=body, timeout=_TIMEOUT)
        else:
            url = f"{self.api_url}/repos/{owner}/{repo}/check-runs"
            resp = http_request("POST", url, headers=self._headers(), json=body, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("id")

    @staticmethod
    def _scrub_annotation(a: dict) -> dict:
        scrubbed = dict(a)
        for key in ("title", "message"):
            if scrubbed.get(key):
                scrubbed[key] = _scrub(scrubbed[key])
        return scrubbed

    def _find_check_run(self, owner: str, repo: str, head_sha: str) -> Optional[int]:
        url = f"{self.api_url}/repos/{owner}/{repo}/commits/{head_sha}/check-runs"
        resp = http_request("GET", 
            url,
            headers=self._headers(),
            params={"check_name": CHECK_NAME, "per_page": 100},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        runs = resp.json().get("check_runs", [])
        for run in runs:
            if run.get("name") == CHECK_NAME:
                return run.get("id")
        return None

    # --- Sticky comment ---------------------------------------------------
    def upsert_sticky_comment(
        self, owner: str, repo: str, number: int, body: str
    ) -> Optional[int]:
        if not self.enabled:
            return None
        body = _scrub(body)
        existing = self._find_sticky(owner, repo, number)
        if existing:
            url = f"{self.api_url}/repos/{owner}/{repo}/issues/comments/{existing}"
            resp = http_request("PATCH", url, headers=self._headers(), json={"body": body}, timeout=_TIMEOUT)
        else:
            url = f"{self.api_url}/repos/{owner}/{repo}/issues/{number}/comments"
            resp = http_request("POST", url, headers=self._headers(), json={"body": body}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("id")

    def _find_sticky(self, owner: str, repo: str, number: int) -> Optional[int]:
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{number}/comments"
        page = 1
        while True:
            resp = http_request("GET", 
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
        resp = http_request("POST", url, headers=self._headers(), json={"body": _scrub(body)}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("id")

    def already_replied(self, owner: str, repo: str, number: int, marker: str) -> bool:
        """Idempotency: true if a prior reply carrying ``marker`` already exists."""
        if not self.enabled:
            return False
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/{number}/comments"
        page = 1
        while True:
            resp = http_request("GET", 
                url, headers=self._headers(),
                params={"per_page": 100, "page": page}, timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            items = resp.json()
            if any(marker in (c.get("body") or "") for c in items):
                return True
            if len(items) < 100:
                return False
            page += 1

    # --- Reactions (feedback signal, P1-3) --------------------------------
    def list_comment_reactions(self, owner: str, repo: str, comment_id: int) -> list[dict]:
        """Read reactions on an issue comment (the sticky comment). Best-effort:
        returns [] on any error so a feedback-tally step never breaks a run."""
        if not self.enabled:
            return []
        url = f"{self.api_url}/repos/{owner}/{repo}/issues/comments/{comment_id}/reactions"
        out: list[dict] = []
        page = 1
        try:
            while True:
                resp = http_request("GET",
                    url, headers=self._headers(),
                    params={"per_page": 100, "page": page}, timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                items = resp.json()
                if not items:
                    break
                out.extend(items)
                if len(items) < 100:
                    break
                page += 1
        except (requests.RequestException, ValueError):
            return []
        return out

    # --- Pull request info ------------------------------------------------
    def get_pull(self, owner: str, repo: str, number: int) -> Optional[dict]:
        if not self.enabled:
            return None
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{number}"
        resp = http_request("GET", url, headers=self._headers(), timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # --- Report artifacts (memory) ----------------------------------------
    def latest_reports(self, owner: str, repo: str, pr_number: int, limit: int = 2,
                       scan: int = 30) -> list[dict]:
        """Download recent `codeguardian-report` artifacts, parse their JSON, and
        return up to `limit` reports for this PR, newest first. Best-effort: any
        download/parse error is skipped so a read-only command still degrades.
        """
        if not self.enabled:
            return []
        artifacts = self._list_artifacts(owner, repo, scan)
        if not artifacts:
            return []

        out: list[dict] = []
        for art in sorted(artifacts, key=lambda a: a.get("created_at", ""), reverse=True):
            if art.get("expired"):
                continue
            data = self._download_report_json(art.get("id"))
            if data and data.get("pr", {}).get("number") == pr_number:
                out.append(data)
                if len(out) >= limit:
                    break
        return out

    def _list_artifacts(self, owner: str, repo: str, scan: int) -> list[dict]:
        url = f"{self.api_url}/repos/{owner}/{repo}/actions/artifacts"
        per_page = 100
        pages = max(1, ceil(scan / per_page))
        out: list[dict] = []
        try:
            for page in range(1, pages + 1):
                resp = http_request("GET", 
                    url,
                    headers=self._headers(),
                    params={"name": _REPORT_ARTIFACT, "per_page": per_page, "page": page},
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                items = resp.json().get("artifacts", [])
                if not items:
                    break
                out.extend(items)
                if len(items) < per_page or len(out) >= scan:
                    break
        except (requests.RequestException, ValueError):
            return []
        return out[:scan]

    def _download_report_json(self, artifact_id: Optional[int]) -> Optional[dict]:
        if artifact_id is None:
            return None
        full = os.environ.get("GITHUB_REPOSITORY", "/")
        owner, _, repo = full.partition("/")
        zip_url = f"{self.api_url}/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"
        try:
            resp = http_request("GET", zip_url, headers=self._headers(), timeout=_TIMEOUT)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                with zf.open(_REPORT_JSON) as fh:
                    return json.load(fh)
        except (requests.RequestException, KeyError, ValueError, zipfile.BadZipFile):
            return None
