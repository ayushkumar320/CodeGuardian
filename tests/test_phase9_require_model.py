"""Opt-in require_model policy: a repo can demand the LLM summary ran, and have
a missing token surfaced loudly (and optionally block) — without making a token
a hard dependency of the default zero-key product (strict rule #3)."""

from __future__ import annotations

import yaml

from codeguardian.graph.agents import recommendation_agent
from codeguardian.models import PrContext, Provider, Report
from codeguardian.policy import Policy
from codeguardian.scoring import score


def _state(policy: Policy) -> dict:
    pr = PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b")
    report = Report(pr=pr, mode=policy.mode, provider=Provider.deterministic, risk=score([], policy))
    return {"policy": policy, "report": report, "errors": []}


def test_default_is_zero_key_no_warning(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    out = recommendation_agent(_state(Policy()))
    report = out["report"]
    assert report.provider == Provider.deterministic
    # Deterministic fallback is normal here — not an error, not blocking.
    assert report.errors == []
    assert report.risk.blocking is False


def test_require_model_warns_when_token_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    policy = Policy.model_validate(yaml.safe_load("model:\n  require_model: true\n"))
    out = recommendation_agent(_state(policy))
    report = out["report"]
    assert report.degraded is True
    assert any("require_model" in e for e in report.errors)
    assert report.risk.blocking is False  # warn only, not block


def test_require_model_can_block_when_configured(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    policy = Policy.model_validate(
        yaml.safe_load("model:\n  require_model: true\n  block_when_missing: true\n")
    )
    out = recommendation_agent(_state(policy))
    assert out["report"].risk.blocking is True
