"""Lightweight JS/TS dependency / blast-radius analysis.

Builds a reverse-import map across the repo so we can estimate which files
depend on a changed module. Produces deterministic ``dependency`` findings with
the impacted files as evidence. Also flags high-risk path edits.
"""

from __future__ import annotations

import os
import re

from ..models import (
    Blocking,
    Category,
    DiffFile,
    FileCategory,
    Finding,
    Severity,
)
from ..pr.classify import matches_any

_IMPORT_RE = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*|require\(\s*|export\s[^'"]*?from\s*)['"]([^'"]+)['"]"""
)
_CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_RESOLVE_EXT = ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]


def _iter_code_files(repo_root: str) -> list[str]:
    out: list[str] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "dist", "build", ".next")]
        for f in files:
            if f.endswith(_CODE_EXT):
                out.append(os.path.relpath(os.path.join(root, f), repo_root))
    return out


def _resolve(importer: str, spec: str, all_files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None  # package import, not a local file
    base = os.path.normpath(os.path.join(os.path.dirname(importer), spec))
    for ext in _RESOLVE_EXT:
        cand = (base + ext).replace(os.sep, "/")
        if cand in all_files:
            return cand
    return None


def build_reverse_imports(repo_root: str) -> dict[str, set[str]]:
    """Map each file -> set of files that import it."""
    files = _iter_code_files(repo_root)
    fileset = set(f.replace(os.sep, "/") for f in files)
    reverse: dict[str, set[str]] = {f: set() for f in fileset}
    for f in files:
        try:
            with open(os.path.join(repo_root, f), "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        importer = f.replace(os.sep, "/")
        for spec in _IMPORT_RE.findall(text):
            target = _resolve(importer, spec, fileset)
            if target:
                reverse[target].add(importer)
    return reverse


def build_forward_imports(repo_root: str) -> dict[str, set[str]]:
    """Map each file -> set of local files it imports."""
    files = _iter_code_files(repo_root)
    fileset = set(f.replace(os.sep, "/") for f in files)
    forward: dict[str, set[str]] = {f: set() for f in fileset}
    for f in files:
        try:
            with open(os.path.join(repo_root, f), "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        importer = f.replace(os.sep, "/")
        for spec in _IMPORT_RE.findall(text):
            target = _resolve(importer, spec, fileset)
            if target:
                forward[importer].add(target)
    return forward


def analyze(
    repo_root: str, changed: list[DiffFile], high_risk_paths: list[str]
) -> list[Finding]:
    reverse = build_reverse_imports(repo_root)
    findings: list[Finding] = []
    idx = 1

    for f in changed:
        norm = f.path.replace(os.sep, "/")
        dependents = sorted(reverse.get(norm, set()))
        is_high_risk = matches_any(norm, high_risk_paths)

        if not dependents and not is_high_risk:
            continue

        n = len(dependents)
        severity, confidence = _grade(n, is_high_risk, f.category)
        evidence = [norm] + dependents[:10]
        blast = f"{n} file(s) import this module" if n else "high-risk path edit"
        findings.append(
            Finding(
                id=f"CG-DEP-{idx:03d}",
                category=Category.dependency,
                severity=severity,
                confidence=confidence,
                title=f"Change in {norm} affects {n} dependent file(s)"
                if n
                else f"High-risk path changed: {norm}",
                summary=f"{norm} was {f.status.value}. {blast}.",
                evidence_files=evidence,
                recommended_actions=_actions(norm, dependents, is_high_risk),
                blocking=Blocking(
                    guarded=severity in (Severity.high, Severity.critical),
                    strict=severity in (Severity.high, Severity.critical),
                ),
            )
        )
        idx += 1
    return findings


def _grade(n: int, high_risk: bool, category: FileCategory) -> tuple[Severity, float]:
    if high_risk and n >= 5:
        return Severity.critical, 0.8
    if high_risk or n >= 8:
        return Severity.high, 0.75
    if n >= 3:
        return Severity.medium, 0.65
    return Severity.low, 0.55


def _actions(path: str, dependents: list[str], high_risk: bool) -> list[str]:
    actions = []
    if dependents:
        actions.append(f"Review the {len(dependents)} file(s) importing {path}")
    if high_risk:
        actions.append("Confirm backward compatibility for this high-risk path")
    if not actions:
        actions.append("No action required")
    return actions
