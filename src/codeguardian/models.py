"""Data contracts for CodeGuardian.

Pydantic models for everything that crosses an interface (LangGraph state,
GitHub API payloads, the JSON artifact). Every Finding must carry non-empty
evidence: no evidence -> no finding. See
doc/build/archive/phase-0-product-contract.md for the original spec.
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
    pr_shape = "pr_shape"  # language-agnostic PR-level signals (size, churn)


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


class RepositoryContext(BaseModel):
    """Lightweight repo understanding gathered before the domain agents run."""

    language_summary: dict[str, int] = Field(default_factory=dict)  # ext -> file count
    framework_summary: list[str] = Field(default_factory=list)
    package_manifests: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)


class PrContext(BaseModel):
    owner: str
    repo: str
    number: int
    base_sha: str
    head_sha: str
    title: str = ""
    body: str = ""
    installation_id: Optional[int] = None
    is_fork: bool = False
    head_ref: str = ""
    head_repo_clone_url: str = ""


class DiffFile(BaseModel):
    path: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    patch: Optional[str] = None
    category: FileCategory = FileCategory.other


class DiffSummaryFile(BaseModel):
    """Compact per-file diff record persisted on the Report so /codeguardian
    free-form Q&A can reason about *what actually changed*, not just abstract
    finding categories. Patch is excerpted to keep the artifact small.
    """
    path: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    patch_excerpt: Optional[str] = None  # first ~80 hunk lines, already redacted
    # Whole hunks (already redacted) kept for files a finding points at, so the
    # changed symbol isn't lost to blind truncation on a large patch (P1-6).
    relevant_hunks: list[str] = Field(default_factory=list)


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
    reviewers: list[str] = Field(default_factory=list)
    historical_context: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # operational notes (e.g. diff truncated)
    diff_summary: list[DiffSummaryFile] = Field(default_factory=list)
    provider_usage: list[str] = Field(default_factory=list)  # e.g. ["dependency_agent:deterministic", "summary:groq"]
    dedupe_key: str = ""
    deterministic_notice: Optional[str] = None
    degraded: bool = False

    def active_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.suppressed is None]
