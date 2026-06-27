"""Deterministic risk scoring.

The score is a confidence-weighted aggregate of finding severities. The LLM
never sets or overrides this number (strict rule #2). Level and blocking are
derived from the score and the policy mode.
"""

from __future__ import annotations

from .models import Finding, Mode, Risk, RiskLevel, Severity
from .policy import Policy

# Severity -> base contribution (0..10 scale before confidence weighting).
_SEVERITY_WEIGHT = {
    Severity.low: 2.0,
    Severity.medium: 4.5,
    Severity.high: 7.5,
    Severity.critical: 9.5,
}


def score(findings: list[Finding], policy: Policy) -> Risk:
    active = [f for f in findings if f.suppressed is None]
    if not active:
        return Risk(score=0.0, level=RiskLevel.low, confidence=1.0, blocking=False)

    # Weighted peak: the worst finding dominates, others nudge it upward.
    # Confidence modulates but never halves severity (0.6 floor), so a
    # high-confidence critical stays critical.
    contributions = sorted(
        (_SEVERITY_WEIGHT[f.severity] * (0.6 + 0.4 * f.confidence) for f in active),
        reverse=True,
    )
    peak = contributions[0]
    secondary = sum(contributions[1:]) * 0.15
    raw = min(10.0, peak + secondary)

    confidence = sum(f.confidence for f in active) / len(active)
    level = _level(raw, policy)
    blocking = _blocking(level, policy.mode)
    return Risk(score=round(raw, 1), level=level, confidence=round(confidence, 2), blocking=blocking)


def _level(raw: float, policy: Policy) -> RiskLevel:
    t = policy.thresholds
    if raw >= t.critical:
        return RiskLevel.critical
    if raw >= t.high:
        return RiskLevel.high
    if raw >= t.medium:
        return RiskLevel.medium
    return RiskLevel.low


def _blocking(level: RiskLevel, mode: Mode) -> bool:
    if mode == Mode.advisory:
        return False
    # guarded + strict block on high and critical
    return level in (RiskLevel.high, RiskLevel.critical)
