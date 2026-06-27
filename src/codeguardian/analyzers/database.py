"""Basic database / migration risk analysis (deterministic).

Phase 2 baseline:
- Flag destructive SQL / Prisma operations in the diff (DROP, DELETE, TRUNCATE,
  removed Prisma model/field) as high/critical.
- Flag a Prisma schema change with no accompanying migration file change.

Deep schema-drift / before-after modelling is Phase 4.
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

_DESTRUCTIVE_SQL = re.compile(
    r"(?i)\b(drop\s+table|drop\s+column|truncate|delete\s+from|alter\s+table\s+\w+\s+drop)\b"
)


def _added_lines(patch: str | None) -> list[str]:
    if not patch:
        return []
    return [ln[1:] for ln in patch.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def _removed_lines(patch: str | None) -> list[str]:
    if not patch:
        return []
    return [ln[1:] for ln in patch.splitlines() if ln.startswith("-") and not ln.startswith("---")]


def analyze(repo_root: str, changed: list[DiffFile]) -> list[Finding]:
    findings: list[Finding] = []
    idx = 1
    db_files = [f for f in changed if f.category == FileCategory.database]

    schema_changed = [f for f in db_files if f.path.lower().endswith("schema.prisma")]
    migration_changed = [f for f in changed if "migration" in f.path.lower()]

    for f in db_files:
        norm = f.path.replace(os.sep, "/")
        destructive = [ln.strip() for ln in _added_lines(f.patch) if _DESTRUCTIVE_SQL.search(ln)]
        # Prisma model/field removals.
        prisma_removed = [
            ln.strip()
            for ln in _removed_lines(f.patch)
            if norm.endswith("schema.prisma") and re.match(r"\s*(model\s+\w+|\w+\s+\w+)", ln)
        ]
        if destructive or prisma_removed:
            ev = destructive or prisma_removed
            findings.append(
                Finding(
                    id=f"CG-DB-{idx:03d}",
                    category=Category.database,
                    severity=Severity.critical,
                    confidence=0.8,
                    title=f"Destructive database change in {norm}",
                    summary=f"Diff includes potentially destructive operation(s): {ev[0][:80]}",
                    evidence_files=[norm],
                    recommended_actions=[
                        "Confirm a rollback/backfill plan and that no live data is lost",
                    ],
                    blocking=Blocking(guarded=True, strict=True),
                )
            )
            idx += 1

    # Schema changed but no migration touched.
    if schema_changed and not migration_changed:
        findings.append(
            Finding(
                id=f"CG-DB-{idx:03d}",
                category=Category.database,
                severity=Severity.high,
                confidence=0.7,
                title="Prisma schema changed without a migration",
                summary="schema.prisma was modified but no migration file changed in this PR.",
                evidence_files=[f.path.replace(os.sep, "/") for f in schema_changed],
                recommended_actions=["Generate and commit the matching Prisma migration"],
                blocking=Blocking(guarded=True, strict=True),
            )
        )
    return findings
