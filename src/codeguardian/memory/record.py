"""Compact, privacy-safe memory record for one analysis run.

Stores only structured outcomes — never source code, diffs, or secrets
(P5 privacy rule). Paths are kept at directory granularity to generalize and to
avoid leaking full file layouts more than necessary.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from ..models import Report


def _dir_of(path: str) -> str:
    d = os.path.dirname(path.replace(os.sep, "/"))
    return d or path.replace(os.sep, "/")


class MemoryRecord(BaseModel):
    pr_number: int
    head_sha: str
    risk_score: float
    risk_level: str
    finding_categories: list[str] = Field(default_factory=list)
    affected_paths: list[str] = Field(default_factory=list)  # directory granularity
    recommended_tests: list[str] = Field(default_factory=list)
    blocking_finding_ids: list[str] = Field(default_factory=list)
    suppressions: list[dict] = Field(default_factory=list)  # {id, by, reason}
    merged: Optional[bool] = None
    outcome_notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_report(cls, report: Report, merged: Optional[bool] = None) -> "MemoryRecord":
        active = report.active_findings()
        paths = []
        for f in active:
            for ev in f.evidence_files:
                d = _dir_of(ev)
                if d not in paths:
                    paths.append(d)
        tests = [
            a for f in active if f.category.value == "test" for a in f.recommended_actions
        ]
        return cls(
            pr_number=report.pr.number,
            head_sha=report.pr.head_sha,
            risk_score=report.risk.score,
            risk_level=report.risk.level.value,
            finding_categories=sorted({f.category.value for f in active}),
            affected_paths=paths[:50],
            recommended_tests=tests[:20],
            blocking_finding_ids=[f.id for f in active if f.blocking.guarded or f.blocking.strict],
            suppressions=[
                {"id": f.id, "by": f.suppressed.by, "reason": f.suppressed.reason}
                for f in report.findings
                if f.suppressed is not None
            ],
            merged=merged,
        )

    def signature(self) -> "Signature":
        return Signature(
            paths=set(self.affected_paths),
            categories=set(self.finding_categories),
        )


class Signature(BaseModel):
    paths: set[str] = Field(default_factory=set)
    categories: set[str] = Field(default_factory=set)

    @classmethod
    def from_report(cls, report: Report) -> "Signature":
        rec = MemoryRecord.from_report(report)
        return rec.signature()
