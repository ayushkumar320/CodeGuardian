"""Lightweight JS/TS dependency / blast-radius analysis.

Builds a reverse-import map across the repo so we can estimate which files
depend on a changed module. Produces deterministic ``dependency`` findings with
the impacted files as evidence. Also flags high-risk path edits.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from ..models import (
    Blocking,
    Category,
    DiffFile,
    FileCategory,
    Finding,
    Severity,
)
from ..pr.classify import matches_any
from ..walk import DEFAULT_MAX_FILES, DEFAULT_MAX_FILE_BYTES, iter_repo_files

_IMPORT_RE = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*|require\(\s*|export\s[^'"]*?from\s*)['"]([^'"]+)['"]"""
)
_CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_RESOLVE_EXT = ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]


def _iter_code_files(
    repo_root: str,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> list[str]:
    return iter_repo_files(
        repo_root, _CODE_EXT, max_files=max_files, max_file_bytes=max_file_bytes
    )


def _resolve(importer: str, spec: str, all_files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None  # package import, not a local file
    base = os.path.normpath(os.path.join(os.path.dirname(importer), spec))
    for ext in _RESOLVE_EXT:
        cand = (base + ext).replace(os.sep, "/")
        if cand in all_files:
            return cand
    return None


@dataclass
class ImportGraph:
    """Forward + reverse local-import maps, built in a single repo pass.

    ``forward[f]``  = local files that ``f`` imports.
    ``reverse[f]``  = local files that import ``f``.

    Built once per run (Phase 10) and shared across analyzers via graph state, so
    the repo is walked and each file read exactly once instead of 4-5 times.
    """

    forward: dict[str, set[str]] = field(default_factory=dict)
    reverse: dict[str, set[str]] = field(default_factory=dict)


def build_import_graph(
    repo_root: str,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> ImportGraph:
    """Walk the repo once, read each code file once, build forward + reverse maps.

    The walk is bounded (``max_files``) and gitignore-aware via :mod:`walk`.
    """
    files = _iter_code_files(repo_root, max_files, max_file_bytes)
    fileset = set(f.replace(os.sep, "/") for f in files)
    forward: dict[str, set[str]] = {f: set() for f in fileset}
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
                forward[importer].add(target)
                reverse[target].add(importer)
    return ImportGraph(forward=forward, reverse=reverse)


def build_reverse_imports(repo_root: str) -> dict[str, set[str]]:
    """Map each file -> set of files that import it. (Standalone; prefer
    ``build_import_graph`` when both directions are needed.)"""
    return build_import_graph(repo_root).reverse


def build_forward_imports(repo_root: str) -> dict[str, set[str]]:
    """Map each file -> set of local files it imports. (Standalone; prefer
    ``build_import_graph`` when both directions are needed.)"""
    return build_import_graph(repo_root).forward


def analyze(
    repo_root: str,
    changed: list[DiffFile],
    high_risk_paths: list[str],
    graph: ImportGraph | None = None,
) -> list[Finding]:
    reverse = (graph or build_import_graph(repo_root)).reverse
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
