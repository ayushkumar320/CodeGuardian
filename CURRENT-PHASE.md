# CURRENT PHASE

Quick reference for where the build is. Update this when a phase ships.

- **Branch model:** solo dev — commit directly to `main`.
- **Stack (committed):** Python + LangGraph + Pydantic. Overrides the docs'
  TypeScript recommendation.

## Status

| Phase | What | State |
|-------|------|-------|
| P0 | Product contract | ✅ done — [doc/build/phase-0-product-contract.md](doc/build/phase-0-product-contract.md) |
| P1 | GitHub Actions PR checker MVP | ✅ done — code under `src/codeguardian/`, 12 tests green |
| **P2** | **LangGraph agentic AI (per-domain agents)** | **▶ NEXT — start here** |
| P3 | `@codeguardian` PR conversation loop | ⬜ pending |
| P4 | DB / API / architecture analyzers + policy | ⬜ pending |
| P5 | GitHub-native memory & history | ⬜ pending |
| P6 | Packaging, distribution, adoption | ⬜ pending |

## Next up: Phase 2

Fan the current linear graph (`src/codeguardian/graph/build.py`) into the
evidence-based multi-agent workflow.

- **Read first:** CONTEXT-GRAPH.md → then ROOT, PLAN, P2, P1.
- **Goal:** Repository Context → {Dependency, API, Database, Test, Architecture}
  agents → Risk Scoring → Recommendation. Deterministic analyzers still own all
  evidence; LLM agents only summarize/classify/rank. Validate every node output;
  no LLM-only findings.
- **Keep working:** provider fallback Groq→HF→deterministic, zero-key path.
