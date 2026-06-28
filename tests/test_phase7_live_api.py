from __future__ import annotations

import subprocess

import codeguardian.__main__ as mainmod
from codeguardian.github.client import GitHubClient
from codeguardian.github.events import parse_pr_context
from codeguardian.models import (
    Mode,
    PrContext,
    Provider,
    Report,
    Risk,
    RiskLevel,
)
from codeguardian.policy import Policy


def _report(pr: PrContext) -> Report:
    return Report(
        pr=pr,
        mode=Mode.guarded,
        provider=Provider.deterministic,
        risk=Risk(score=7.4, level=RiskLevel.high, confidence=0.8, blocking=True),
    )


def test_parse_pr_context_marks_fork():
    event = {
        "number": 7,
        "pull_request": {
            "number": 7,
            "title": "forked change",
            "base": {
                "sha": "base",
                "repo": {"full_name": "org/repo"},
            },
            "head": {
                "sha": "head",
                "ref": "feature",
                "repo": {
                    "full_name": "contrib/repo",
                    "clone_url": "https://github.com/contrib/repo.git",
                },
            },
        },
    }
    pr = parse_pr_context(event, {"GITHUB_REPOSITORY": "org/repo", "GITHUB_SHA": "head"})
    assert pr is not None
    assert pr.is_fork is True
    assert pr.head_ref == "feature"
    assert pr.head_repo_clone_url.endswith("contrib/repo.git")


def test_publish_check_updates_existing(monkeypatch):
    calls: list[tuple[str, str]] = []

    class Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(("get", url))
        return Resp({"check_runs": [{"id": 42, "name": "CodeGuardian Risk"}]})

    def fake_patch(url, headers=None, json=None, timeout=None):
        calls.append(("patch", url))
        return Resp({"id": 42})

    monkeypatch.setattr("codeguardian.github.client.requests.get", fake_get)
    monkeypatch.setattr("codeguardian.github.client.requests.patch", fake_patch)

    client = GitHubClient(token="t")
    out = client.publish_check("o", "r", "sha", "failure", "title", "summary")
    assert out == 42
    assert calls == [
        ("get", "https://api.github.com/repos/o/r/commits/sha/check-runs"),
        ("patch", "https://api.github.com/repos/o/r/check-runs/42"),
    ]


def test_fork_pr_skips_writes(monkeypatch, tmp_path):
    pr = PrContext(
        owner="o",
        repo="r",
        number=1,
        base_sha="a",
        head_sha="b",
        is_fork=True,
        head_ref="feature",
        head_repo_clone_url="https://github.com/user/repo.git",
    )
    published: list[str] = []

    monkeypatch.setattr(mainmod, "run_analysis", lambda *args, **kwargs: (_report(pr), "narrative"))
    monkeypatch.setattr(mainmod, "_write_artifacts", lambda *args, **kwargs: str(tmp_path / "report.json"))

    class FakeClient:
        def publish_check(self, *args, **kwargs):
            published.append("check")

        def upsert_sticky_comment(self, *args, **kwargs):
            published.append("comment")

    monkeypatch.setattr(mainmod, "GitHubClient", lambda: FakeClient())
    report = mainmod._analyze_and_publish(str(tmp_path), pr, Policy())
    assert report.pr.is_fork is True
    assert published == []


def test_recheck_fetches_head_repo_ref(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(mainmod.subprocess, "run", fake_run)
    monkeypatch.setattr(mainmod, "_analyze_and_publish", lambda *args, **kwargs: None)

    class FakeClient:
        def get_pull(self, owner, repo, number):
            return {
                "title": "recheck",
                "head": {
                    "sha": "headsha",
                    "ref": "feature/ref",
                    "repo": {
                        "full_name": "contrib/repo",
                        "clone_url": "https://github.com/contrib/repo.git",
                    },
                },
                "base": {
                    "sha": "basesha",
                    "repo": {"full_name": "org/repo"},
                },
            }

    mainmod._recheck(FakeClient(), "org", "repo", 7, str(tmp_path), Policy())
    assert any(
        cmd[:6] == [
            "git", "-C", str(tmp_path), "fetch", "--no-tags",
            "https://github.com/contrib/repo.git",
        ]
        for cmd in calls
    )
