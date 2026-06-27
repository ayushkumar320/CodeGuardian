"""Test-impact analysis (deterministic).

Beyond filename matching:
- If tests import the changed module (reverse import graph), recommend running
  those impacted tests (an `impacted suite` signal, not a missing-coverage one).
- If a changed source file has neither a co-located test nor any importing test,
  flag missing coverage.
- Policy `test_suite_mappings` add suite-run recommendations by path glob.
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
from ..globs import glob_match
from ..policy import TestSuite
from .imports import build_reverse_imports

_CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_TEST_MARKERS = (".test.", ".spec.", "__tests__/", "/tests/", "/test/")


def _is_test_path(path: str) -> bool:
    p = path.lower()
    return any(m in p for m in _TEST_MARKERS)


def _candidate_tests(path: str) -> list[str]:
    d, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    out = []
    for suffix in (".test", ".spec"):
        out.append(os.path.join(d, f"{stem}{suffix}{ext}").replace(os.sep, "/"))
        out.append(os.path.join(d, "__tests__", f"{stem}{suffix}{ext}").replace(os.sep, "/"))
    return out


def analyze(repo_root: str, changed: list[DiffFile],
            suite_mappings: list[TestSuite] | None = None) -> list[Finding]:
    suite_mappings = suite_mappings or []
    reverse = build_reverse_imports(repo_root)
    findings: list[Finding] = []
    idx = 1

    for f in changed:
        if f.category in (FileCategory.test, FileCategory.docs):
            continue
        if not f.path.endswith(_CODE_EXT):
            continue
        norm = f.path.replace(os.sep, "/")

        importing_tests = sorted(t for t in reverse.get(norm, set()) if _is_test_path(t))
        has_colocated = any(
            os.path.isfile(os.path.join(repo_root, c)) for c in _candidate_tests(f.path)
        )
        suites = [m.suite for m in suite_mappings if glob_match(norm, m.paths)]

        if importing_tests:
            actions = [f"Run impacted tests: {', '.join(importing_tests[:5])}"]
            actions += [f"Run suite: {s}" for s in suites]
            findings.append(
                Finding(
                    id=f"CG-TEST-{idx:03d}",
                    category=Category.test,
                    severity=Severity.medium,
                    confidence=0.7,
                    title=f"{len(importing_tests)} test(s) impacted by {norm}",
                    summary="Tests that import this module should run before merge.",
                    evidence_files=[norm] + importing_tests[:10],
                    recommended_actions=actions,
                    blocking=Blocking(),
                )
            )
            idx += 1
        elif not has_colocated:
            sev = (
                Severity.high
                if f.category in (FileCategory.backend, FileCategory.database)
                else Severity.medium
            )
            actions = [f"Add a test next to {norm} (e.g. {_candidate_tests(f.path)[0]})"]
            actions += [f"Run suite: {s}" for s in suites]
            findings.append(
                Finding(
                    id=f"CG-TEST-{idx:03d}",
                    category=Category.test,
                    severity=sev,
                    confidence=0.6,
                    title=f"No test found for {norm}",
                    summary="Changed source file has no co-located test and no test imports it.",
                    evidence_files=[norm],
                    recommended_actions=actions,
                    blocking=Blocking(guarded=False, strict=sev == Severity.high),
                )
            )
            idx += 1
    return findings
