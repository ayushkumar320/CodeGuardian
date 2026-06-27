"""Shared TypeScript type-change analysis (deterministic).

A removed or renamed exported type/interface/enum in a shared types module is a
likely breaking change for every file that imports it. Severity scales with the
import blast radius.
"""

from __future__ import annotations

import os
import re

from ..models import (
    Blocking,
    Category,
    DiffFile,
    Finding,
    Severity,
)
from .imports import build_reverse_imports

_TYPE_EXPORT_RE = re.compile(
    r"export\s+(?:declare\s+)?(?:type|interface|enum|class)\s+([A-Za-z_]\w*)"
)
_TYPES_MARKERS = (".types.ts", ".d.ts", "/types/", "/types.ts")


def _is_types_file(path: str) -> bool:
    p = path.lower()
    return any(m in p for m in _TYPES_MARKERS)


def _removed_types(patch: str | None) -> list[str]:
    if not patch:
        return []
    names: list[str] = []
    for line in patch.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            m = _TYPE_EXPORT_RE.search(line[1:])
            if m:
                names.append(m.group(1))
    # Keep only names that are not re-added (rename/removal, not reformatting).
    added = {
        _TYPE_EXPORT_RE.search(ln[1:]).group(1)
        for ln in patch.splitlines()
        if ln.startswith("+") and not ln.startswith("+++") and _TYPE_EXPORT_RE.search(ln[1:])
    }
    return [n for n in names if n not in added]


def analyze(repo_root: str, changed: list[DiffFile]) -> list[Finding]:
    targets = [f for f in changed if _is_types_file(f.path)]
    if not targets:
        return []
    reverse = build_reverse_imports(repo_root)
    findings: list[Finding] = []
    idx = 1
    for f in targets:
        norm = f.path.replace(os.sep, "/")
        removed = _removed_types(f.patch)
        if not removed:
            continue
        dependents = sorted(reverse.get(norm, set()))
        n = len(dependents)
        if n >= 3:
            sev, conf = Severity.critical, 0.82
        elif n >= 1:
            sev, conf = Severity.high, 0.78
        else:
            sev, conf = Severity.medium, 0.6
        findings.append(
            Finding(
                id=f"CG-TYPE-{idx:03d}",
                category=Category.dependency,
                severity=sev,
                confidence=conf,
                title=f"Exported type removed/renamed in {norm}: {', '.join(removed[:3])}",
                summary=(
                    f"Type(s) {', '.join(removed[:5])} were removed/renamed. "
                    f"{n} file(s) import this module and may no longer compile."
                ),
                evidence_files=[norm] + dependents[:10],
                recommended_actions=[
                    f"Update the {n} importer(s) or keep a backward-compatible alias",
                ],
                blocking=Blocking(
                    guarded=sev in (Severity.high, Severity.critical),
                    strict=sev in (Severity.high, Severity.critical),
                ),
            )
        )
        idx += 1
    return findings
