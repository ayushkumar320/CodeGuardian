"""Database / migration risk analysis (deterministic).

- Destructive SQL (DROP/TRUNCATE/DELETE/ALTER...DROP/RENAME, ALTER COLUMN TYPE,
  added NOT NULL) -> critical/high.
- Prisma model/field removals and made-required fields -> high/critical.
- Prisma schema change with no accompanying migration -> high.

Evidence includes the changed file plus the affected models/tables where we can
extract them. Deep before/after schema modelling remains future work.
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
    r"(?i)\b(drop\s+table|drop\s+column|truncate|delete\s+from|"
    r"alter\s+table\s+\w+\s+drop|alter\s+table\s+\w+\s+rename|"
    r"alter\s+column\s+\w+\s+type|alter\s+column\s+\w+\s+set\s+not\s+null)\b"
)
_SQL_TABLE_RE = re.compile(r"(?i)\b(?:table|from|into)\s+[\"`']?([A-Za-z_][\w]*)")
_PRISMA_MODEL_RE = re.compile(r"^\s*model\s+([A-Za-z_]\w*)\s*\{")
_PRISMA_FIELD_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)(\??)")


def _added(patch: str | None) -> list[str]:
    if not patch:
        return []
    return [ln[1:] for ln in patch.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def _removed(patch: str | None) -> list[str]:
    if not patch:
        return []
    return [ln[1:] for ln in patch.splitlines() if ln.startswith("-") and not ln.startswith("---")]


def _tables(lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in lines:
        m = _SQL_TABLE_RE.search(ln)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def _prisma_changes(patch: str | None) -> tuple[list[str], list[str]]:
    """Return (removed_models, removed_fields) from a Prisma schema diff."""
    removed_models, removed_fields = [], []
    for ln in _removed(patch):
        mm = _PRISMA_MODEL_RE.match(ln)
        if mm:
            removed_models.append(mm.group(1))
            continue
        fm = _PRISMA_FIELD_RE.match(ln)
        if fm and fm.group(2)[0].isupper() is False:
            # field declarations like `email String` -> capture field name
            removed_fields.append(fm.group(1))
    # made-required: field optional removed and re-added without '?'
    added_required = {
        m.group(1)
        for ln in _added(patch)
        if (m := _PRISMA_FIELD_RE.match(ln)) and m.group(3) == ""
    }
    removed_optional = {
        m.group(1)
        for ln in _removed(patch)
        if (m := _PRISMA_FIELD_RE.match(ln)) and m.group(3) == "?"
    }
    made_required = sorted(added_required & removed_optional)
    return removed_models, sorted(set(removed_fields)) + [f"{f} (now required)" for f in made_required]


def analyze(repo_root: str, changed: list[DiffFile]) -> list[Finding]:
    findings: list[Finding] = []
    idx = 1
    db_files = [f for f in changed if f.category == FileCategory.database]
    schema_changed = [f for f in db_files if f.path.lower().endswith("schema.prisma")]
    migration_changed = [f for f in changed if "migration" in f.path.lower()]

    for f in db_files:
        norm = f.path.replace(os.sep, "/")
        is_prisma = norm.lower().endswith("schema.prisma")

        if is_prisma:
            models, fields = _prisma_changes(f.patch)
            if models or fields:
                detail = []
                if models:
                    detail.append(f"removed model(s): {', '.join(models)}")
                if fields:
                    detail.append(f"removed/required field(s): {', '.join(fields[:5])}")
                sev = Severity.critical if models else Severity.high
                findings.append(
                    Finding(
                        id=f"CG-DB-{idx:03d}",
                        category=Category.database,
                        severity=sev,
                        confidence=0.8,
                        title=f"Breaking Prisma schema change in {norm}",
                        summary="; ".join(detail),
                        evidence_files=[norm],
                        recommended_actions=[
                            "Confirm a backfill/rollback plan and update dependent queries",
                        ],
                        blocking=Blocking(guarded=True, strict=True),
                    )
                )
                idx += 1
            continue

        destructive = [ln.strip() for ln in _added(f.patch) if _DESTRUCTIVE_SQL.search(ln)]
        if destructive:
            tables = _tables(destructive)
            findings.append(
                Finding(
                    id=f"CG-DB-{idx:03d}",
                    category=Category.database,
                    severity=Severity.critical,
                    confidence=0.8,
                    title=f"Destructive database migration in {norm}",
                    summary=(
                        f"Potentially destructive operation(s): {destructive[0][:80]}"
                        + (f" — affects {', '.join(tables)}" if tables else "")
                    ),
                    evidence_files=[norm],
                    recommended_actions=[
                        "Confirm a rollback/backfill plan and that no live data is lost",
                    ],
                    blocking=Blocking(guarded=True, strict=True),
                )
            )
            idx += 1

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
