from __future__ import annotations

from pathlib import Path

import codeguardian.__main__ as mainmod
from codeguardian.graph.build import run_analysis
from codeguardian.models import PrContext
from codeguardian.policy import Policy


def test_agent_failure_surfaces_degraded_report(tmp_path, monkeypatch):
    root = str(tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    import subprocess

    def git(*args):
        subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "util.ts").write_text("export const x = 1;\n")
    git("init", "-q")
    git("add", "-A")
    subprocess.run(
        ["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"],
        check=True,
        capture_output=True,
    )
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / "src" / "util.ts").write_text("export const x = 2;\n")
    git("add", "-A")
    subprocess.run(
        ["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "change"],
        check=True,
        capture_output=True,
    )
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    from codeguardian.graph import agents

    monkeypatch.setattr(agents.api_analyzer, "analyze", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("api boom")))
    pr = PrContext(owner="o", repo="r", number=1, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy())
    assert report.degraded is True
    assert any("api:" in e for e in report.errors)


def test_run_handles_uncaught_error_and_returns_zero(tmp_path, monkeypatch):
    event_path = tmp_path / "event.json"
    event_path.write_text(
        '{"number": 2, "pull_request": {"number": 2, "title": "x", "base": {"sha": "a", "repo": {"full_name": "o/r"}}, "head": {"sha": "b", "repo": {"full_name": "o/r"}}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("CODEGUARDIAN_OUT", str(tmp_path))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))

    monkeypatch.setattr(mainmod, "_run_pull_request", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    class FakeClient:
        def publish_check(self, *args, **kwargs):
            return 1

        def upsert_sticky_comment(self, *args, **kwargs):
            return 2

    monkeypatch.setattr(mainmod, "GitHubClient", lambda: FakeClient())

    rc = mainmod.run()
    assert rc == 0
    assert Path(tmp_path / "codeguardian-report.json").is_file()
    assert "degraded" in (tmp_path / "summary.md").read_text(encoding="utf-8").lower()
