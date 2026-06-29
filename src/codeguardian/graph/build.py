"""Assemble and run the Phase 2 agentic LangGraph.

collect_pr_context -> repository_context -> fan out to five parallel domain
agents -> risk_scoring -> recommendation. The parallel agents converge on
risk_scoring, which waits for all of them before scoring.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..models import PrContext, Report
from ..policy import Policy
from . import agents, nodes
from .state import CodeGuardianState

_DOMAIN_AGENTS = [
    ("dependency_agent", agents.dependency_agent),
    ("test_impact_agent", agents.test_impact_agent),
    ("api_contract_agent", agents.api_contract_agent),
    ("database_agent", agents.database_agent),
    ("architecture_agent", agents.architecture_agent),
    ("types_agent", agents.types_agent),
    ("pr_shape_agent", agents.pr_shape_agent),
]


def build_graph():
    g = StateGraph(CodeGuardianState)

    g.add_node("collect_pr_context", nodes.collect_pr_context)
    g.add_node("repository_context", nodes.repository_context)
    for name, fn in _DOMAIN_AGENTS:
        g.add_node(name, fn)
    g.add_node("risk_scoring_agent", agents.risk_scoring_agent)
    g.add_node("historical_knowledge_agent", agents.historical_knowledge_agent)
    g.add_node("recommendation_agent", agents.recommendation_agent)

    g.add_edge(START, "collect_pr_context")
    g.add_edge("collect_pr_context", "repository_context")
    for name, _ in _DOMAIN_AGENTS:
        g.add_edge("repository_context", name)   # fan out (parallel superstep)
        g.add_edge(name, "risk_scoring_agent")   # fan in (waits for all)
    g.add_edge("risk_scoring_agent", "historical_knowledge_agent")
    g.add_edge("historical_knowledge_agent", "recommendation_agent")
    g.add_edge("recommendation_agent", END)
    return g.compile()


def run_analysis(
    repo_root: str, pr: PrContext, policy: Policy, memory_store: object | None = None
) -> tuple[Report, str]:
    graph = build_graph()
    initial: CodeGuardianState = {
        "repo_root": repo_root,
        "policy": policy,
        "pr": pr,
        "evidence": [],
        "provider_usage": [],
        "errors": [],
    }
    if memory_store is not None:
        initial["memory_store"] = memory_store
    final = graph.invoke(initial)
    return final["report"], final.get("narrative", "")
