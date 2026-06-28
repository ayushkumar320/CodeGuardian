from __future__ import annotations

import logging

import requests

import codeguardian.http as http
from codeguardian.log import debug_enabled, get_logger
from codeguardian.selfcheck import run_selfcheck


class Resp:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


def test_request_retries_on_5xx_then_succeeds(monkeypatch):
    attempts = []

    def fake_request(method, url, timeout=None, **kwargs):
        attempts.append(method)
        return Resp(status_code=500 if len(attempts) < 3 else 200)

    monkeypatch.setattr(http.requests, "request", fake_request)
    resp = http.request("GET", "https://x", sleep=lambda _s: None)
    assert resp.status_code == 200
    assert len(attempts) == 3


def test_request_retries_on_connection_error_then_raises(monkeypatch):
    attempts = []

    def fake_request(method, url, timeout=None, **kwargs):
        attempts.append(method)
        raise requests.ConnectionError("down")

    monkeypatch.setattr(http.requests, "request", fake_request)
    try:
        http.request("GET", "https://x", sleep=lambda _s: None)
        assert False, "expected ConnectionError"
    except requests.ConnectionError:
        pass
    assert len(attempts) == 3  # bounded by max_attempts


def test_request_does_not_retry_4xx(monkeypatch):
    attempts = []

    def fake_request(method, url, timeout=None, **kwargs):
        attempts.append(method)
        return Resp(status_code=404)

    monkeypatch.setattr(http.requests, "request", fake_request)
    resp = http.request("GET", "https://x", sleep=lambda _s: None)
    assert resp.status_code == 404
    assert len(attempts) == 1


def test_request_honors_retry_after_header(monkeypatch):
    slept = []

    def fake_request(method, url, timeout=None, **kwargs):
        return Resp(status_code=429, headers={"Retry-After": "2"}) if not slept else Resp(200)

    monkeypatch.setattr(http.requests, "request", fake_request)
    http.request("GET", "https://x", sleep=slept.append)
    assert slept == [2.0]


def test_logger_redacts_secrets(monkeypatch, caplog):
    logger = get_logger()
    with caplog.at_level(logging.WARNING, logger="codeguardian"):
        logger.warning("token is ghp_%s", "A" * 36)
    rendered = caplog.records[-1].getMessage()
    assert "ghp_AAAA" not in rendered
    assert "REDACTED" in rendered or "***" in rendered or "[redacted]" in rendered.lower()


def test_debug_enabled_reads_env():
    assert debug_enabled({"CODEGUARDIAN_DEBUG": "1"}) is True
    assert debug_enabled({"CODEGUARDIAN_DEBUG": "true"}) is True
    assert debug_enabled({}) is False


def test_selfcheck_passes_with_no_token(monkeypatch, capsys):
    # No GITHUB_TOKEN -> required failure -> exit 1, but never crashes.
    rc = run_selfcheck({})
    out = capsys.readouterr().out
    assert "self-check" in out.lower()
    assert rc == 1
    assert "GITHUB_TOKEN" in out


def test_selfcheck_passes_with_reachable_token(monkeypatch):
    def fake_request(method, url, timeout=None, **kwargs):
        return Resp(status_code=200, headers={"X-RateLimit-Remaining": "4999"})

    monkeypatch.setattr(http.requests, "request", fake_request)
    rc = run_selfcheck({"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r"})
    assert rc == 0


def test_provider_timeout_falls_through_to_deterministic(monkeypatch):
    """Acceptance: a provider timeout degrades to the deterministic summary,
    never crashes the run."""
    from codeguardian.models import PrContext, Provider, Report
    from codeguardian.policy import Policy
    from codeguardian.providers import summarize
    from codeguardian.scoring import score

    def boom(method, url, timeout=None, **kwargs):
        raise requests.Timeout("model slow")

    monkeypatch.setattr(http.requests, "request", boom)
    policy = Policy()
    report = Report(
        pr=PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b"),
        mode=policy.mode,
        provider=Provider.deterministic,
        risk=score([], policy),
    )
    result = summarize(report, env={"GROQ_API_KEY": "k", "HF_TOKEN": "h"})
    assert result.provider == Provider.deterministic
    assert isinstance(result.text, str) and result.text
