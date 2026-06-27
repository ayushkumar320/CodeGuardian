"""Policy loading and defaults (.codeguardian/policy.yml).

Phase 1 reads a small subset: blocking mode, risk thresholds, noise budgets,
high-risk paths. Unknown keys are ignored so the file can grow in later phases.
"""

from __future__ import annotations

import os
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from .models import Mode


class Thresholds(BaseModel):
    medium: float = 3.1
    high: float = 6.1
    critical: float = 8.6


class NoiseBudget(BaseModel):
    max_findings_check: int = 3
    max_findings_comment: int = 5
    comment_on_medium: bool = True
    allow_inline_annotations: bool = False
    skip_comment_for_docs_only: bool = True


class ForbiddenImport(BaseModel):
    paths: str  # glob of files this rule applies to
    cannot_import: str  # substring an import spec must not contain
    reason: str = ""


class Architecture(BaseModel):
    forbidden_imports: list[ForbiddenImport] = Field(default_factory=list)


class Policy(BaseModel):
    mode: Mode = Mode.advisory  # gradual rollout: advisory first
    thresholds: Thresholds = Field(default_factory=Thresholds)
    noise: NoiseBudget = Field(default_factory=NoiseBudget)
    architecture: Architecture = Field(default_factory=Architecture)
    high_risk_paths: list[str] = Field(
        default_factory=lambda: [
            "**/migrations/**",
            "**/prisma/schema.prisma",
            "**/auth/**",
            "**/billing/**",
            "**/api/**",
            "**/*.types.ts",
        ]
    )

    @classmethod
    def load(cls, repo_root: str) -> "Policy":
        path = os.path.join(repo_root, ".codeguardian", "policy.yml")
        if not os.path.isfile(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError):
            return cls()
        return cls.model_validate(_pick_known(data))


def _pick_known(data: dict) -> dict:
    known = {"mode", "thresholds", "noise", "architecture", "high_risk_paths"}
    return {k: v for k, v in data.items() if k in known}
