"""A model key (Groq or HF) is required to run. On a non-fork PR with no key,
CodeGuardian gates: it publishes a 'needs a key' check + comment and does not
analyze. Fork PRs can't carry secrets and are exempt (degraded deterministic).
"""

from __future__ import annotations

import codeguardian.__main__ as m
from codeguardian import report as report_mod


def _event(head_full="o/r"):
    return {
        "pull_request": {
            "number": 1,
            "title": "t",
            "base": {"sha": "a", "repo": {"full_name": "o/r"}},
            "head": {"sha": "b", "ref": "f", "repo": {"full_name": head_full}},
        },
    }


class _Report:
    risk = type("R", (), {"blocking": False})()


def test_has_model_key():
    assert m._has_model_key({"GROQ_API_KEY": "x"}) is True
    assert m._has_model_key({"HF_TOKEN": "y"}) is True
    assert m._has_model_key({}) is False


def test_pr_run_gated_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)  # client disabled -> publishes no-op
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    called = {"analyze": False}
    monkeypatch.setattr(m, "_analyze_and_publish",
                        lambda *a, **k: called.__setitem__("analyze", True))
    rc = m._run_pull_request(_event(), str(tmp_path))
    assert rc == 1                      # run fails — key required
    assert called["analyze"] is False  # never analyzed without a key


def test_pr_run_proceeds_with_key(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setattr(m, "_analyze_and_publish", lambda *a, **k: _Report())
    rc = m._run_pull_request(_event(), str(tmp_path))
    assert rc == 0


def test_fork_pr_exempt_from_key_gate(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    called = {"analyze": False}

    def fake(*a, **k):
        called["analyze"] = True
        return _Report()

    monkeypatch.setattr(m, "_analyze_and_publish", fake)
    # head repo != base repo -> fork; gate must NOT fire (can't carry secrets).
    rc = m._run_pull_request(_event(head_full="contrib/r"), str(tmp_path))
    assert called["analyze"] is True


def test_key_required_messages_mention_secrets():
    assert "GROQ_API_KEY" in report_mod.key_required_check_summary()
    assert "HF_TOKEN" in report_mod.key_required_check_summary()
    assert report_mod.SUMMARY_ANCHOR in report_mod.key_required_comment()
