from codeguardian.models import (
    Blocking,
    Category,
    Finding,
    Mode,
    RiskLevel,
    Severity,
)
from codeguardian.policy import Policy
from codeguardian.scoring import score


def _finding(sev, conf=0.8):
    return Finding(
        id="CG-DEP-001",
        category=Category.dependency,
        severity=sev,
        confidence=conf,
        title="t",
        summary="s",
        evidence_files=["a.ts"],
        blocking=Blocking(guarded=sev in (Severity.high, Severity.critical)),
    )


def test_no_findings_is_low():
    r = score([], Policy())
    assert r.score == 0.0
    assert r.level == RiskLevel.low
    assert r.blocking is False


def test_critical_finding_blocks_in_guarded():
    p = Policy(mode=Mode.guarded)
    r = score([_finding(Severity.critical)], p)
    assert r.level == RiskLevel.critical
    assert r.blocking is True


def test_high_does_not_block_in_advisory():
    r = score([_finding(Severity.high)], Policy(mode=Mode.advisory))
    assert r.level == RiskLevel.high
    assert r.blocking is False


def test_evidence_required():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Finding(
            id="x",
            category=Category.test,
            severity=Severity.low,
            confidence=0.5,
            title="t",
            summary="s",
            evidence_files=[],
        )
