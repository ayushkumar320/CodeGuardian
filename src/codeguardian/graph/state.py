"""Shared LangGraph state (Phase 0 §B5, Phase 2 state contract).

Plain TypedDict so LangGraph can merge node return values. Deterministic nodes
populate ``evidence`` first; the LLM node only fills ``narrative``.
"""

from __future__ import annotations

from typing import Optional, TypedDict

from ..models import DiffFile, Finding, PrContext, Report
from ..policy import Policy


class CodeGuardianState(TypedDict, total=False):
    repo_root: str
    policy: Policy
    pr: PrContext
    diff: list[DiffFile]
    evidence: list[Finding]
    affected_areas: list[str]
    report: Report
    narrative: str
    errors: list[str]
