"""Phase 9 — security & supply-chain hardening tests.

Covers:
- prompt-injection corpus is rendered inert (fenced + secret-redacted),
- the model layer can never create an evidence-free finding (schema guarantee),
- egress secret-scan scrubs secrets from anything we post,
- fork PRs degrade to read-only (no writes, no secrets).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codeguardian.models import (
    Blocking,
    Category,
    Finding,
    PrContext,
    Severity,
)
from codeguardian.security import find_secrets, safe_output, wrap_untrusted

from injection_corpus import FAKE_SECRET, INJECTION_PAYLOADS


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_untrusted_payload_is_fenced_and_redacted(payload):
    wrapped = wrap_untrusted(payload)
    # Fenced as data, not instructions.
    assert "UNTRUSTED REPOSITORY CONTENT" in wrapped
    # No fake secret survives the redaction step.
    assert FAKE_SECRET not in wrapped


def test_corpus_secrets_are_detected():
    # At least the payloads carrying the fake token must be flagged.
    flagged = [p for p in INJECTION_PAYLOADS if find_secrets(p)]
    assert flagged, "expected secret-bearing payloads to be detected"
    for p in flagged:
        assert FAKE_SECRET not in safe_output(p)


def test_finding_cannot_be_created_without_evidence():
    # Strict rule #4: a fabricated finding with no evidence is rejected at the
    # schema boundary, so an injected 'add a finding' instruction cannot succeed.
    with pytest.raises(ValidationError):
        Finding(
            id="CG-INJECT-001",
            category=Category.architecture,
            severity=Severity.high,
            confidence=0.9,
            title="injected backdoor claim",
            summary="model was told to add this",
            evidence_files=[],  # no evidence -> must fail
            blocking=Blocking(),
        )


def test_egress_scrub_removes_secret_from_posted_text():
    crafted = f"Risk summary. Leaked token {FAKE_SECRET} and api_key=hunter2hunter2hunter2hunter2"
    cleaned = safe_output(crafted)
    assert FAKE_SECRET not in cleaned
    assert "hunter2hunter2" not in cleaned
    assert "[REDACTED]" in cleaned


def test_fork_pr_is_read_only_and_skips_writes(monkeypatch):
    import codeguardian.__main__ as mainmod

    fork_pr = PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b", is_fork=True)
    same_repo_pr = PrContext(owner="o", repo="r", number=2, base_sha="a", head_sha="b")
    assert mainmod._can_publish(fork_pr) is False
    assert mainmod._can_publish(same_repo_pr) is True
