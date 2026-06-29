"""Language-agnostic PR-shape analyzer.

These findings fire on *any* repo regardless of language, because they read only
the diff's structural properties — file count, additions/deletions — not the
code. They're the baseline signal CodeGuardian gives a Go/Rust/Ruby repo that
otherwise has no deep analyzer support.

Strict rule #2 still applies: this analyzer owns the evidence (it's the diff
itself), and findings carry explicit per-file evidence.
"""

from __future__ import annotations

from ..models import Blocking, Category, DiffFile, Finding, Severity
from ..policy import PrShape


def analyze(changed: list[DiffFile], cfg: PrShape) -> list[Finding]:
    if not cfg.enabled or not changed:
        return []

    findings: list[Finding] = []

    # 1. Oversized PR — many files touched.
    n_files = len(changed)
    if n_files >= cfg.large_pr_files:
        # Severity bumps with size; cap at high so we never gratuitously block.
        if n_files >= cfg.large_pr_files * 4:
            sev, conf = Severity.high, 0.75
        elif n_files >= cfg.large_pr_files * 2:
            sev, conf = Severity.medium, 0.7
        else:
            sev, conf = Severity.low, 0.65
        evidence = [f.path for f in changed[:10]]
        findings.append(Finding(
            id="CG-PR-001",
            category=Category.pr_shape,
            severity=sev,
            confidence=conf,
            title=f"Large PR: {n_files} files changed",
            summary=(
                f"This PR touches {n_files} files (threshold {cfg.large_pr_files}). "
                f"Large PRs are harder to review and tend to mask risky edits."
            ),
            evidence_files=evidence,
            recommended_actions=["Consider splitting this PR into smaller, focused changes"],
            blocking=Blocking(),  # advisory; never blocks
        ))

    # 2. Deletion-heavy PR — net code removal is a refactor/cleanup signal that
    # often deserves explicit review.
    additions = sum(f.additions for f in changed)
    deletions = sum(f.deletions for f in changed)
    net_removed = deletions - additions
    if net_removed >= cfg.deletion_heavy_min_net_removed:
        evidence = sorted(
            (f.path for f in changed if f.deletions > f.additions),
            key=lambda p: -next(
                (df.deletions - df.additions for df in changed if df.path == p), 0
            ),
        )[:10] or [f.path for f in changed[:5]]
        findings.append(Finding(
            id="CG-PR-002",
            category=Category.pr_shape,
            severity=Severity.medium,
            confidence=0.65,
            title=f"Deletion-heavy PR: net {net_removed} lines removed",
            summary=(
                f"{deletions} deletions vs {additions} additions (net -{net_removed}). "
                f"Confirm removed code paths are truly unused and any callers are updated."
            ),
            evidence_files=evidence,
            recommended_actions=[
                "Verify removed code has no remaining callers (search the repo / staging logs)",
                "Add a regression test for behavior the removed code was responsible for",
            ],
            blocking=Blocking(),
        ))

    return findings
