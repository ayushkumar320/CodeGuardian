"""Shared LangGraph state (Phase 0 §B5, Phase 2 state contract).

Phase 2: domain agents run in parallel and each append to ``evidence`` and
``provider_usage``. Those keys use additive reducers so concurrent writes from
the parallel superstep merge instead of clobbering each other.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from ..models import DiffFile, Finding, PrContext, RepositoryContext, Report
from ..policy import Policy


class CodeGuardianState(TypedDict, total=False):
    repo_root: str
    policy: Policy
    pr: PrContext
    diff: list[DiffFile]
    repository: RepositoryContext
    affected_areas: list[str]
    # Additive: parallel agents each contribute findings / provider tags.
    evidence: Annotated[list[Finding], operator.add]
    provider_usage: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    report: Report
    narrative: str
    memory_store: object  # optional MemoryStore for historical retrieval
