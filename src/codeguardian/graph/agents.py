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
from ..globs import glob_match
from ..analyzers import api as api_analyzer
from ..analyzers import architecture as arch_analyzer
from ..analyzers import database as db_analyzer
from ..analyzers import imports as imports_analyzer
from ..analyzers import pr_shape as pr_shape_analyzer
from ..analyzers import tests as tests_analyzer
from ..analyzers import types as types_analyzer
from ..memory.record import Signature
from ..memory.retrieve import context_lines, find_similar
from ..models import DiffSummaryFile, Finding, Provider, Report, Suppression
from ..security import safe_output
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
            state["repo_root"], state["diff"], state["policy"].high_risk_paths,
            graph=state.get("import_graph"),
        ),
    )


def test_impact_agent(state: CodeGuardianState) -> dict:
    if _skip_docs_only(state):
        return {}
    return _safe(
        "test",
        lambda: tests_analyzer.analyze(
            state["repo_root"], state["diff"], state["policy"].test_suite_mappings,
            graph=state.get("import_graph"),
        ),
    )


def types_agent(state: CodeGuardianState) -> dict:
    if _skip_docs_only(state):
        return {}
    return _safe(
        "types",
        lambda: types_analyzer.analyze(
            state["repo_root"], state["diff"], graph=state.get("import_graph")
        ),
    )


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
            state["repo_root"], state["diff"], state["policy"].architecture,
            graph=state.get("import_graph"),
        ),
    )


def pr_shape_agent(state: CodeGuardianState) -> dict:
    """Language-agnostic — runs on docs-only PRs too (large docs reorgs count)."""
    return _safe(
        "pr_shape",
        lambda: pr_shape_analyzer.analyze(state["diff"], state["policy"].pr_shape),
    )


# --- Synthesis agents -----------------------------------------------------
def risk_scoring_agent(state: CodeGuardianState) -> dict:
    policy = state["policy"]
    findings = state.get("evidence", [])

    # Policy-level pre-suppression (ignored_findings) — kept visible, excluded
    # from the score (scoring ignores suppressed findings).
    ignored = set(policy.ignored_findings)
    for f in findings:
        if f.id in ignored and f.suppressed is None:
            f.suppressed = Suppression(by="policy", reason="listed in policy.ignored_findings")

    risk = score(findings, policy)

    actions: list[str] = []
    for f in sorted((x for x in findings if x.suppressed is None),
                    key=lambda x: x.confidence, reverse=True):
        for a in f.recommended_actions:
            if a != "No action required" and a not in actions:
                actions.append(a)

    reviewers = _reviewers(findings, policy)

    pr = state["pr"]
    diff_summary = _build_diff_summary(state.get("diff", []))
    report = Report(
        pr=pr,
        mode=policy.mode,
        provider=Provider.deterministic,  # finalized by recommendation_agent
        risk=risk,
        affected_areas=state.get("affected_areas", []),
        findings=findings,
        actions=actions,
        reviewers=reviewers,
        errors=state.get("errors", []),
        notes=state.get("notes", []),
        diff_summary=diff_summary,
        degraded=bool(state.get("errors", [])),
        dedupe_key=f"{pr.owner}/{pr.repo}#{pr.number}@{pr.head_sha}:{ANALYZER_VERSION}",
    )
    return {"report": report}


# Per-file patch excerpt cap. Big enough to convey *what* changed (a function
# rename, added file, removed branch fits well below this), small enough to keep
# the artifact + ask-mode prompt bounded.
_MAX_PATCH_EXCERPT = 1600


def _build_diff_summary(diff) -> list[DiffSummaryFile]:
    out: list[DiffSummaryFile] = []
    for f in diff or []:
        excerpt = None
        if f.patch:
            text = f.patch
            if len(text) > _MAX_PATCH_EXCERPT:
                text = text[:_MAX_PATCH_EXCERPT] + "\n…(truncated)"
            # Secret-redact (defense in depth — patches can contain anything).
            excerpt = safe_output(text)
        out.append(DiffSummaryFile(
            path=f.path, status=f.status,
            additions=f.additions, deletions=f.deletions,
            patch_excerpt=excerpt,
        ))
    return out


def _reviewers(findings: list[Finding], policy) -> list[str]:
    """Suggest owners for the paths flagged by active findings (WFI §16)."""
    paths = {ev for f in findings if f.suppressed is None for ev in f.evidence_files}
    out: list[str] = []
    for rule in policy.service_owners:
        if any(glob_match(p, rule.paths) for p in paths):
            for owner in rule.owners:
                if owner not in out:
                    out.append(owner)
    return out


def historical_knowledge_agent(state: CodeGuardianState) -> dict:
    """Attach historical context (similar past PRs) to the report. Informational
    only — it never changes the deterministic score, just adds a 'has this
    happened before?' signal (P5: history appears only when useful)."""
    policy = state["policy"]
    store = state.get("memory_store")
    report = state["report"]
    if store is None or not policy.memory.enabled:
        return {}
    try:
        records = store.load()
    except Exception as exc:  # noqa: BLE001
        return {"errors": [f"history: {exc}"]}
    matches = find_similar(
        Signature.from_report(report),
        records,
        report.pr.number,
        policy.memory.max_results,
        policy.memory.min_similarity,
    )
    report.historical_context = context_lines(matches)
    report.errors = state.get("errors", [])
    report.degraded = bool(report.errors)
    return {"report": report}


def recommendation_agent(state: CodeGuardianState) -> dict:
    policy = state["policy"]
    report = state["report"]
    result = summarize(report)
    report.provider = result.provider
    errors = list(state.get("errors", []))
    if result.provider == Provider.deterministic:
        report.deterministic_notice = (
            "CodeGuardian ran in deterministic mode because no model provider "
            "token was configured. Risk score and recommendations are based on "
            "static analysis only."
        )
        # Opt-in: a repo that requires the LLM summary wants this surfaced loudly
        # rather than silently falling back (strict rule #3 keeps it opt-in).
        if policy.model.require_model:
            errors.append(
                "model: require_model is set but no provider token (GROQ_API_KEY / "
                "HF_TOKEN) was configured; summary fell back to deterministic."
            )
            if policy.model.block_when_missing:
                report.risk.blocking = True
    report.errors = errors
    report.degraded = bool(errors)
    return {"report": report, "narrative": result.text, "provider_usage": [f"summary:{result.provider.value}"]}
