"""LangGraph agent nodes (Phase 2).

Topology: collect_pr_context -> repository_context -> {dependency, test_impact,
api_contract, database, architecture} (parallel) -> risk_scoring -> recommendation.

Deterministic analyzers own all evidence; the recommendation agent is the only
LLM step and it merely rephrases the summary. No agent may emit a finding without
analyzer evidence (Pydantic enforces non-empty evidence on construction).

Each agent is wrapped so an unexpected analyzer error degrades to "no findings
from this agent" plus a recorded error — one agent failing never breaks the run.
"""

from __future__ import annotations

from typing import Callable

from .. import ANALYZER_VERSION
from ..analyzers import api as api_analyzer
from ..analyzers import architecture as arch_analyzer
from ..analyzers import database as db_analyzer
from ..analyzers import imports as imports_analyzer
from ..analyzers import tests as tests_analyzer
from ..models import Finding, Provider, Report
from ..pr.classify import is_docs_only
from ..providers import summarize
from ..scoring import score
from .state import CodeGuardianState


def _safe(name: str, fn: Callable[[], list[Finding]]) -> dict:
    """Run a domain analyzer, returning its evidence + provider tag, or an error."""
    try:
        return {"evidence": fn(), "provider_usage": [f"{name}:deterministic"]}
    except Exception as exc:  # noqa: BLE001 - isolate agent failures
        return {"evidence": [], "errors": [f"{name}: {exc}"]}


def _skip_docs_only(state: CodeGuardianState) -> bool:
    return is_docs_only([f.category for f in state.get("diff", [])])


# --- Domain agents (deterministic evidence) -------------------------------
def dependency_agent(state: CodeGuardianState) -> dict:
    if _skip_docs_only(state):
        return {}
    return _safe(
        "dependency",
        lambda: imports_analyzer.analyze(
            state["repo_root"], state["diff"], state["policy"].high_risk_paths
        ),
    )


def test_impact_agent(state: CodeGuardianState) -> dict:
    if _skip_docs_only(state):
        return {}
    return _safe("test", lambda: tests_analyzer.analyze(state["repo_root"], state["diff"]))


def api_contract_agent(state: CodeGuardianState) -> dict:
    if _skip_docs_only(state):
        return {}
    return _safe("api", lambda: api_analyzer.analyze(state["repo_root"], state["diff"]))


def database_agent(state: CodeGuardianState) -> dict:
    if _skip_docs_only(state):
        return {}
    return _safe("database", lambda: db_analyzer.analyze(state["repo_root"], state["diff"]))


def architecture_agent(state: CodeGuardianState) -> dict:
    if _skip_docs_only(state):
        return {}
    return _safe(
        "architecture",
        lambda: arch_analyzer.analyze(
            state["repo_root"], state["diff"], state["policy"].architecture
        ),
    )


# --- Synthesis agents -----------------------------------------------------
def risk_scoring_agent(state: CodeGuardianState) -> dict:
    policy = state["policy"]
    findings = state.get("evidence", [])
    risk = score(findings, policy)

    actions: list[str] = []
    for f in sorted(findings, key=lambda x: x.confidence, reverse=True):
        for a in f.recommended_actions:
            if a != "No action required" and a not in actions:
                actions.append(a)

    pr = state["pr"]
    report = Report(
        pr=pr,
        mode=policy.mode,
        provider=Provider.deterministic,  # finalized by recommendation_agent
        risk=risk,
        affected_areas=state.get("affected_areas", []),
        findings=findings,
        actions=actions,
        dedupe_key=f"{pr.owner}/{pr.repo}#{pr.number}@{pr.head_sha}:{ANALYZER_VERSION}",
    )
    return {"report": report}


def recommendation_agent(state: CodeGuardianState) -> dict:
    report = state["report"]
    result = summarize(report)
    report.provider = result.provider
    if result.provider == Provider.deterministic:
        report.deterministic_notice = (
            "CodeGuardian ran in deterministic mode because no model provider "
            "token was configured. Risk score and recommendations are based on "
            "static analysis only."
        )
    return {"report": report, "narrative": result.text, "provider_usage": [f"summary:{result.provider.value}"]}
