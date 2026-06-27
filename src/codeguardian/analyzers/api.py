"""Basic API-contract analysis (deterministic).

Phase 2 baseline: flag changes to API route files, with higher severity when the
diff removes an exported handler (a likely breaking contract change). Deep
OpenAPI/GraphQL diffing is Phase 4.
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

_HANDLER_RE = re.compile(
    r"(export\s+(default|const|function|async\s+function)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|handler))"
)


def _is_api_route(path: str) -> bool:
    p = path.lower()
    return "/api/" in p or p.endswith(("route.ts", "route.js")) or "/routes/" in p


def _removed_handlers(patch: str | None) -> list[str]:
    if not patch:
        return []
    removed = []
    for line in patch.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            if _HANDLER_RE.search(line):
                removed.append(line[1:].strip())
    return removed


def analyze(repo_root: str, changed: list[DiffFile]) -> list[Finding]:
    findings: list[Finding] = []
    idx = 1
    for f in changed:
        norm = f.path.replace(os.sep, "/")
        if not _is_api_route(norm):
            continue
        removed = _removed_handlers(f.patch)
        if removed:
            sev, conf = Severity.high, 0.78
            title = f"API handler removed/changed in {norm}"
            summary = f"Diff removes exported handler(s): {', '.join(removed[:3])}. May break API consumers."
            action = "Verify no client depends on the removed handler; add a regression test"
        else:
            sev, conf = Severity.medium, 0.6
            title = f"API route changed: {norm}"
            summary = "An API route file changed. Confirm request/response shape is backward compatible."
            action = "Confirm request/response contract is unchanged or versioned"
        findings.append(
            Finding(
                id=f"CG-API-{idx:03d}",
                category=Category.api,
                severity=sev,
                confidence=conf,
                title=title,
                summary=summary,
                evidence_files=[norm],
                recommended_actions=[action],
                blocking=Blocking(guarded=sev == Severity.high, strict=sev == Severity.high),
            )
        )
        idx += 1
    return findings
