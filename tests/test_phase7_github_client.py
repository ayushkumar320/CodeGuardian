from __future__ import annotations

import io
import json
import zipfile

from codeguardian.github.client import GitHubClient


class Resp:
    def __init__(self, payload=None, content: bytes = b"", status_code: int = 200):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _zip_report(pr_number: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("codeguardian-report.json", json.dumps({"pr": {"number": pr_number}}))
    return buf.getvalue()


def test_find_sticky_paginates(monkeypatch):
    calls = []

    def fake_get(method, url, headers=None, params=None, timeout=None):
        calls.append(params["page"])
        if params["page"] == 1:
            return Resp([{"id": 1, "body": "x"} for _ in range(100)])
        return Resp([{"id": 222, "body": "<!-- codeguardian-ai-summary -->\nbody"}])

    monkeypatch.setattr("codeguardian.http.requests.request", fake_get)
    client = GitHubClient(token="t")
    assert client._find_sticky("o", "r", 1) == 222
    assert calls == [1, 2]


def test_already_replied_paginates(monkeypatch):
    calls = []

    def fake_get(method, url, headers=None, params=None, timeout=None):
        calls.append(params["page"])
        if params["page"] == 1:
            return Resp([{"id": 1, "body": "x"} for _ in range(100)])
        return Resp([{"id": 2, "body": "<!-- cg-reply:9 --> reply"}])

    monkeypatch.setattr("codeguardian.http.requests.request", fake_get)
    client = GitHubClient(token="t")
    assert client.already_replied("o", "r", 1, "<!-- cg-reply:9 -->") is True
    assert calls == [1, 2]


def test_latest_reports_scans_multiple_artifact_pages(monkeypatch):
    calls = []

    def fake_get(method, url, headers=None, params=None, timeout=None):
        calls.append((url, params))
        if url.endswith("/actions/artifacts"):
            page = params["page"]
            if page == 1:
                artifacts = [{"id": i, "created_at": "2026-06-27T00:00:00Z"} for i in range(1, 101)]
                return Resp({"artifacts": artifacts})
            return Resp({"artifacts": [{"id": 2, "created_at": "2026-06-28T00:00:00Z"}]})
        if url.endswith("/1/zip"):
            return Resp(content=_zip_report(10))
        if url.endswith("/2/zip"):
            return Resp(content=_zip_report(12))
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("codeguardian.http.requests.request", fake_get)
    client = GitHubClient(token="t")
    reports = client.latest_reports("o", "r", pr_number=12, limit=1, scan=101)
    assert reports == [{"pr": {"number": 12}}]
    artifact_pages = [params["page"] for url, params in calls if url.endswith("/actions/artifacts")]
    assert artifact_pages == [1, 2]
