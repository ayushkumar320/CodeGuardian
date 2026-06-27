"""LangGraph node functions for the Phase 1 pipeline.

Order: collect_pr_context -> classify_changes -> dependency_scan ->
test_recommendation -> risk_score -> llm_summarize -> publish_result.

Deterministic nodes own all evidence; llm_summarize only rephrases. Each node
returns a partial state dict that LangGraph merges.
"""

from __future__ import annotations

from .. import ANALYZER_VERSION
from ..analyzers import imports as imports_analyzer
from ..analyzers import tests as tests_analyzer
from ..models import (
    FileCategory,
    Mode,
    Provider,
    Report,
)
from ..pr.classify import is_docs_only
from ..pr.diff import compute_diff
from ..providers import deterministic_summary, summarize
from ..scoring import score
from .state import CodeGuardianState

_AREA_BY_CATEGORY = {
    FileCategory.frontend: "Frontend",
    FileCategory.backend: "Backend",
    FileCategory.database: "Database",
    FileCategory.config: "Config",
    FileCategory.types: "Shared types",
    FileCategory.test: "Tests",
    FileCategory.docs: "Docs",
}


def collect_pr_context(state: CodeGuardianState) -> dict:
    pr = state["pr"]
    files = compute_diff(state["repo_root"], pr.base_sha, pr.head_sha)
    return {"diff": files, "errors": state.get("errors", [])}


def classify_changes(state: CodeGuardianState) -> dict:
    areas = sorted(
        {
            _AREA_BY_CATEGORY[f.category]
            for f in state.get("diff", [])
            if f.category in _AREA_BY_CATEGORY and f.category != FileCategory.docs
        }
    )
    return {"affected_areas": areas}


def dependency_scan(state: CodeGuardianState) -> dict:
    diff = state.get("diff", [])
    if is_docs_only([f.category for f in diff]):
        return {"evidence": state.get("evidence", [])}
    findings = imports_analyzer.analyze(
        state["repo_root"], diff, state["policy"].high_risk_paths
    )
    return {"evidence": state.get("evidence", []) + findings}


def test_recommendation(state: CodeGuardianState) -> dict:
    diff = state.get("diff", [])
    if is_docs_only([f.category for f in diff]):
        return {"evidence": state.get("evidence", [])}
    findings = tests_analyzer.analyze(state["repo_root"], diff)
    return {"evidence": state.get("evidence", []) + findings}


def risk_score(state: CodeGuardianState) -> dict:
    policy = state["policy"]
    findings = state.get("evidence", [])
    risk = score(findings, policy)
    actions: list[str] = []
    for f in sorted(findings, key=lambda x: x.confidence, reverse=True):
        for a in f.recommended_actions:
            if a != "No action required" and a not in actions:
                actions.append(a)

    report = Report(
        pr=state["pr"],
        mode=policy.mode,
        provider=Provider.deterministic,  # updated in llm_summarize
        risk=risk,
        affected_areas=state.get("affected_areas", []),
        findings=findings,
        actions=actions,
        dedupe_key=_dedupe_key(state),
    )
    return {"report": report}


def llm_summarize(state: CodeGuardianState) -> dict:
    report = state["report"]
    result = summarize(report)
    report.provider = result.provider
    if result.provider == Provider.deterministic:
        report.deterministic_notice = (
            "CodeGuardian ran in deterministic mode because no model provider "
            "token was configured. Risk score and recommendations are based on "
            "static analysis only."
        )
    return {"report": report, "narrative": result.text}


def _dedupe_key(state: CodeGuardianState) -> str:
    pr = state["pr"]
    return f"{pr.owner}/{pr.repo}#{pr.number}@{pr.head_sha}:{ANALYZER_VERSION}"
