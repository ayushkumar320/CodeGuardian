"""Assemble the Phase 1 LangGraph and run it.

LangGraph is the orchestrator from Phase 1 (committed stack decision). The graph
is linear for now; Phase 2 fans out into per-domain agents.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..models import PrContext, Report
from ..policy import Policy
from . import nodes
from .state import CodeGuardianState


def build_graph():
    g = StateGraph(CodeGuardianState)
    g.add_node("collect_pr_context", nodes.collect_pr_context)
    g.add_node("classify_changes", nodes.classify_changes)
    g.add_node("dependency_scan", nodes.dependency_scan)
    g.add_node("test_recommendation", nodes.test_recommendation)
    g.add_node("risk_score", nodes.risk_score)
    g.add_node("llm_summarize", nodes.llm_summarize)

    g.add_edge(START, "collect_pr_context")
    g.add_edge("collect_pr_context", "classify_changes")
    g.add_edge("classify_changes", "dependency_scan")
    g.add_edge("dependency_scan", "test_recommendation")
    g.add_edge("test_recommendation", "risk_score")
    g.add_edge("risk_score", "llm_summarize")
    g.add_edge("llm_summarize", END)
    return g.compile()


def run_analysis(repo_root: str, pr: PrContext, policy: Policy) -> tuple[Report, str]:
    graph = build_graph()
    initial: CodeGuardianState = {
        "repo_root": repo_root,
        "policy": policy,
        "pr": pr,
        "evidence": [],
        "errors": [],
    }
    final = graph.invoke(initial)
    return final["report"], final.get("narrative", "")
