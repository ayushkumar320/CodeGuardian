"""Heuristic test-impact analysis.

For each changed non-test source file, look for a co-located or conventionally
named test file. If none exists, emit a ``test`` finding recommending coverage.
"""

from __future__ import annotations

import os

from ..models import (
    Blocking,
    Category,
    DiffFile,
    FileCategory,
    Finding,
    Severity,
)

_CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _candidate_tests(path: str) -> list[str]:
    d, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    out = []
    for suffix in (".test", ".spec"):
        out.append(os.path.join(d, f"{stem}{suffix}{ext}").replace(os.sep, "/"))
        out.append(os.path.join(d, "__tests__", f"{stem}{suffix}{ext}").replace(os.sep, "/"))
    return out


def analyze(repo_root: str, changed: list[DiffFile]) -> list[Finding]:
    findings: list[Finding] = []
    idx = 1
    for f in changed:
        if f.category in (FileCategory.test, FileCategory.docs):
            continue
        if not f.path.endswith(_CODE_EXT):
            continue
        candidates = _candidate_tests(f.path)
        if any(os.path.isfile(os.path.join(repo_root, c)) for c in candidates):
            continue  # has a test
        sev = (
            Severity.high
            if f.category in (FileCategory.backend, FileCategory.database)
            else Severity.medium
        )
        findings.append(
            Finding(
                id=f"CG-TEST-{idx:03d}",
                category=Category.test,
                severity=sev,
                confidence=0.6,
                title=f"No test found for {f.path.replace(os.sep, '/')}",
                summary="Changed source file has no co-located or conventionally named test.",
                evidence_files=[f.path.replace(os.sep, "/")],
                recommended_actions=[
                    f"Add a test next to {f.path} (e.g. {candidates[0]})",
                ],
                blocking=Blocking(guarded=False, strict=sev == Severity.high),
            )
        )
        idx += 1
    return findings
