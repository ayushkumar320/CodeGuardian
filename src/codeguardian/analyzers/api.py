"""API-contract analysis (deterministic).

- Route files: removed exported handler -> high (breaking); removed response
  object field -> high; other route edits -> medium.
- API spec files (OpenAPI / GraphQL): removed path / type / field -> high drift.

AST-level request/response typing is future work; these heuristics catch the
common breaking shapes from the diff alone.
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
_RESP_FIELD_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*:")  # `field:` in a returned object
_GQL_DEF_RE = re.compile(r"^\s*(type|input|enum|interface|union)\s+([A-Za-z_]\w*)")
_OPENAPI_PATH_RE = re.compile(r"^\s+(/[A-Za-z0-9_{}/-]+)\s*:")


def _is_api_route(path: str) -> bool:
    p = path.lower()
    return "/api/" in p or p.endswith(("route.ts", "route.js")) or "/routes/" in p


def _is_spec(path: str) -> bool:
    p = path.lower()
    return (
        p.endswith((".graphql", ".gql"))
        or "openapi" in p
        or "swagger" in p
        or p.endswith("schema.graphql")
    )


def _removed(patch: str | None) -> list[str]:
    if not patch:
        return []
    return [ln[1:] for ln in patch.splitlines() if ln.startswith("-") and not ln.startswith("---")]


def _added(patch: str | None) -> list[str]:
    if not patch:
        return []
    return [ln[1:] for ln in patch.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def _removed_matches(patch: str | None, regex: re.Pattern, group: int = 0) -> list[str]:
    out: list[str] = []
    added_text = "\n".join(_added(patch))
    for ln in _removed(patch):
        m = regex.search(ln)
        if not m:
            continue
        token = m.group(group)
        if token and token not in added_text:  # ignore reformatting/re-adds
            out.append(token)
    return out


def analyze(repo_root: str, changed: list[DiffFile]) -> list[Finding]:
    findings: list[Finding] = []
    idx = 1
    for f in changed:
        norm = f.path.replace(os.sep, "/")

        if _is_spec(norm):
            removed = _removed_matches(f.patch, _GQL_DEF_RE, 2) + _removed_matches(
                f.patch, _OPENAPI_PATH_RE, 1
            )
            if removed:
                findings.append(_finding(idx, norm, Severity.high, 0.78,
                    f"API spec drift in {norm}",
                    f"Removed definition(s)/path(s): {', '.join(sorted(set(removed))[:5])}.",
                    "Treat as a breaking API change; version it or restore the contract"))
                idx += 1
            continue

        if not _is_api_route(norm):
            continue

        removed_handlers = [ln.strip() for ln in _removed(f.patch) if _HANDLER_RE.search(ln)]
        removed_fields = _removed_matches(f.patch, _RESP_FIELD_RE, 1)
        if removed_handlers:
            findings.append(_finding(idx, norm, Severity.high, 0.78,
                f"API handler removed/changed in {norm}",
                f"Diff removes handler(s): {', '.join(removed_handlers[:3])}. May break consumers.",
                "Verify no client depends on the removed handler; add a regression test"))
            idx += 1
        elif removed_fields:
            findings.append(_finding(idx, norm, Severity.high, 0.7,
                f"API response field removed in {norm}",
                f"Field(s) {', '.join(sorted(set(removed_fields))[:5])} appear removed from the response.",
                "Confirm clients don't read these fields; version the response if needed"))
            idx += 1
        else:
            findings.append(_finding(idx, norm, Severity.medium, 0.6,
                f"API route changed: {norm}",
                "An API route file changed. Confirm request/response is backward compatible.",
                "Confirm request/response contract is unchanged or versioned"))
            idx += 1
    return findings


def _finding(idx, path, sev, conf, title, summary, action) -> Finding:
    blocking = sev in (Severity.high, Severity.critical)
    return Finding(
        id=f"CG-API-{idx:03d}",
        category=Category.api,
        severity=sev,
        confidence=conf,
        title=title,
        summary=summary,
        evidence_files=[path],
        recommended_actions=[action],
        blocking=Blocking(guarded=blocking, strict=blocking),
    )
