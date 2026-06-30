"""Schema breaking-change detection for committed API schemas (P2-3 increment).

Deterministic and removal-only — additions to a schema are backward-compatible,
removals are the breaking ones — so the false-positive profile stays low and we
stay quiet by default.

Covers the common high-signal cases from the diff alone (no schema parser yet):
- OpenAPI (`openapi.yaml` / `swagger.json` / `*.openapi.yml`): a removed path
  (`/users/{id}:`) or a removed HTTP operation (`delete:`) under it.
- GraphQL SDL (`*.graphql` / `*.gql`): a removed `type` / `enum` / `interface`
  / `input`, or a removed field line inside a type.

A full structural `oasdiff`-style diff (type narrowing, newly-required params)
remains future work; this catches outright removals, which are unambiguous
breaks for any client.
"""

from __future__ import annotations

import os
import re

from ..models import Blocking, Category, DiffFile, Finding, Severity

_OPENAPI_MARKERS = ("openapi.yaml", "openapi.yml", "openapi.json",
                    "swagger.yaml", "swagger.yml", "swagger.json")
_GRAPHQL_EXT = (".graphql", ".gql")

_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head")

_PATH_RE = re.compile(r"^\s*(/\S*?):\s*$")
_METHOD_RE = re.compile(r"^\s*(" + "|".join(_HTTP_METHODS) + r"):\s*$")
_GQL_TYPE_RE = re.compile(r"^\s*(?:type|enum|interface|input|union)\s+([A-Za-z_]\w*)")
_GQL_FIELD_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:\s*[A-Za-z\[]")


def _is_openapi(path: str) -> bool:
    p = path.lower()
    name = p.rsplit("/", 1)[-1]
    return name in _OPENAPI_MARKERS or name.endswith(".openapi.yaml") or name.endswith(".openapi.yml")


def _is_graphql(path: str) -> bool:
    return path.lower().endswith(_GRAPHQL_EXT)


def _removed_minus_added(patch: str | None, pattern: re.Pattern) -> list[str]:
    """Names matched by ``pattern`` on removed lines but not re-added (a re-add
    is a reorder/reformat, not a removal)."""
    if not patch:
        return []
    removed, added = [], set()
    for line in patch.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            m = pattern.match(line[1:])
            if m:
                removed.append(m.group(1))
        elif line.startswith("+"):
            m = pattern.match(line[1:])
            if m:
                added.add(m.group(1))
    return [r for r in removed if r not in added]


def _openapi_findings(f: DiffFile, idx: int) -> list[Finding]:
    norm = f.path.replace(os.sep, "/")
    removed_paths = _removed_minus_added(f.patch, _PATH_RE)
    removed_methods = _removed_minus_added(f.patch, _METHOD_RE)
    if not removed_paths and not removed_methods:
        return []
    removed = [f"path {p}" for p in removed_paths] + [f"operation {m}" for m in removed_methods]
    return [Finding(
        id=f"CG-SCHEMA-{idx:03d}",
        category=Category.api,
        severity=Severity.high,
        confidence=0.75,
        title=f"OpenAPI breaking change in {norm}: {', '.join(removed[:3])}",
        summary=(
            f"Removed from the API schema: {', '.join(removed[:6])}. "
            "Removing a path or operation breaks existing clients."
        ),
        evidence_files=[norm],
        recommended_actions=[
            "Deprecate before removing, or version the API (e.g. /v2) instead of removing in place",
        ],
        blocking=Blocking(guarded=True, strict=True),
    )]


def _graphql_findings(f: DiffFile, idx: int) -> list[Finding]:
    norm = f.path.replace(os.sep, "/")
    removed_types = _removed_minus_added(f.patch, _GQL_TYPE_RE)
    removed_fields = _removed_minus_added(f.patch, _GQL_FIELD_RE)
    if not removed_types and not removed_fields:
        return []
    removed = [f"type {t}" for t in removed_types] + [f"field {x}" for x in removed_fields]
    return [Finding(
        id=f"CG-SCHEMA-{idx:03d}",
        category=Category.api,
        severity=Severity.high,
        confidence=0.7,
        title=f"GraphQL breaking change in {norm}: {', '.join(removed[:3])}",
        summary=(
            f"Removed from the GraphQL schema: {', '.join(removed[:6])}. "
            "Removing a type or field breaks queries that reference it."
        ),
        evidence_files=[norm],
        recommended_actions=[
            "Mark the field/type @deprecated before removing it",
        ],
        blocking=Blocking(guarded=True, strict=True),
    )]


def analyze(repo_root: str, changed: list[DiffFile]) -> list[Finding]:
    findings: list[Finding] = []
    idx = 1
    for f in changed:
        if _is_openapi(f.path):
            new = _openapi_findings(f, idx)
        elif _is_graphql(f.path):
            new = _graphql_findings(f, idx)
        else:
            continue
        findings.extend(new)
        idx += len(new)
    return findings
