"""Data contracts for CodeGuardian.

Python (Pydantic) re-expression of the Phase 0 TypeScript contracts in
doc/build/phase-0-product-contract.md (B4 data contracts, B5 LangGraph state).
Every Finding must carry non-empty evidence: no evidence -> no finding.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from . import ANALYZER_VERSION, SCHEMA_VERSION


class FileCategory(str, Enum):
    frontend = "frontend"
    backend = "backend"
    config = "config"
    database = "database"
    test = "test"
    docs = "docs"
    types = "types"
    other = "other"


class FileStatus(str, Enum):
    added = "added"
    modified = "modified"
    removed = "removed"
    renamed = "renamed"


class Category(str, Enum):
    dependency = "dependency"
    api = "api"
    database = "database"
    architecture = "architecture"
    test = "test"
    history = "history"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Mode(str, Enum):
    advisory = "advisory"
    guarded = "guarded"
    strict = "strict"


class Provider(str, Enum):
    groq = "groq"
    huggingface = "huggingface"
    deterministic = "deterministic"


class PrContext(BaseModel):
    owner: str
    repo: str
    number: int
    base_sha: str
    head_sha: str
    title: str = ""
    installation_id: Optional[int] = None


class DiffFile(BaseModel):
    path: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    patch: Optional[str] = None
    category: FileCategory = FileCategory.other


class Blocking(BaseModel):
    guarded: bool = False
    strict: bool = False


class Suppression(BaseModel):
    by: str
    reason: str


class Finding(BaseModel):
    id: str  # CG-<CATEGORY>-<NNN>, stable per PR
    category: Category
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    summary: str
    evidence_files: list[str]
    recommended_actions: list[str] = Field(default_factory=list)
    blocking: Blocking = Field(default_factory=Blocking)
    suppressed: Optional[Suppression] = None

    @field_validator("evidence_files")
    @classmethod
    def _evidence_required(cls, v: list[str]) -> list[str]:
        # Strict rule #4: every finding cites evidence. No evidence -> no finding.
        if not v:
            raise ValueError("Finding requires at least one evidence file")
        return v


class Risk(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    level: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
    blocking: bool = False


class Report(BaseModel):
    schema_version: str = SCHEMA_VERSION
    analyzer_version: str = ANALYZER_VERSION
    pr: PrContext
    mode: Mode
    provider: Provider
    risk: Risk
    affected_areas: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    dedupe_key: str = ""
    deterministic_notice: Optional[str] = None

    def active_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.suppressed is None]
