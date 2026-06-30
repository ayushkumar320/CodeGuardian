"""Deterministic confidence calibration from patch context (P2-6).

Analyzer-side confidence (``analyzers/imports._grade`` etc.) is set without
looking at *how surgical* the diff actually is. A whitespace-only or
comment-only change in a file with 200 dependents is graded identically to a
signature rename in the same file. This pass nudges confidence *down* when the
evidence is only trivial edits — genuinely deterministic and explainable, and
it only ever lowers confidence (never invents or inflates a finding).
"""

from __future__ import annotations

import re

from .models import DiffFile, Finding

# A changed line whose payload (after the +/- marker) is blank or a pure
# comment. Covers the common comment leaders across the languages we touch
# (#, //, and C-style /* * */). Conservative on purpose: anything with real
# tokens fails these patterns and is treated as a substantive change.
_TRIVIAL_LINE = re.compile(
    r"""^[+-](?:
        \s*                        # whitespace-only
        |\s*\#.*                   # python / shell / yaml comment
        |\s*//.*                   # js / ts / go comment
        |\s*/\*.*                  # c-style block open
        |\s*\*.*                   # c-style block continuation
        |\s*\*/\s*                 # c-style block close
    )$""",
    re.VERBOSE,
)

_CALIBRATION_PENALTY = 0.2


def _changed_lines(patch: str) -> list[str]:
    out: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            out.append(line)
    return out


def _is_trivial_patch(patch: str) -> bool:
    """True if the patch has at least one changed line and *every* changed
    line is whitespace-only or a comment."""
    changed = _changed_lines(patch)
    if not changed:
        return False
    return all(_TRIVIAL_LINE.match(line) for line in changed)


def calibrate_confidence(findings: list[Finding], diff: list[DiffFile]) -> list[Finding]:
    """Lower confidence by ``_CALIBRATION_PENALTY`` for findings whose evidence
    in the diff is only trivial (whitespace/comment) edits.

    A finding is calibrated down only when **all** of its evidence files that
    actually appear in the diff are trivial-only. Findings with no evidence file
    present in the diff are left untouched (we can't judge surgicality).
    Mutates and returns the same list.
    """
    by_path = {f.path: f for f in diff if f.patch}
    for finding in findings:
        if finding.suppressed is not None:
            continue
        evidence_in_diff = [p for p in finding.evidence_files if p in by_path]
        if not evidence_in_diff:
            continue
        if all(_is_trivial_patch(by_path[p].patch or "") for p in evidence_in_diff):
            new = round(max(0.0, finding.confidence - _CALIBRATION_PENALTY), 2)
            if new != finding.confidence:
                finding.confidence = new
    return findings
