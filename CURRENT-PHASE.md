# CURRENT PHASE

Quick reference for where the build is. Update this when a phase ships.

- **Branch model:** solo dev — commit directly to `main`.
- **Stack (committed):** Python + LangGraph + Pydantic. Overrides the docs'
  TypeScript recommendation.

## Status

| Phase | What | State |
|-------|------|-------|
| P0 | Product contract | ✅ done — [doc/build/phase-0-product-contract.md](doc/build/phase-0-product-contract.md) |
| P1 | GitHub Actions PR checker MVP | ✅ done — code under `src/codeguardian/` |
| P2 | LangGraph agentic AI (per-domain agents) | ✅ done — parallel agent graph, API/DB/arch analyzers |
| P3 | `@codeguardian` PR conversation loop | ✅ done — command parser, handlers, recheck/ignore |
| P4 | DB / API / architecture analyzers (deep) + policy | ✅ done — types/layers/cycles/spec-drift, richer policy, 48 tests green |
| **P5** | **GitHub-native memory & history** | **▶ NEXT — start here** |
| P6 | Packaging, distribution, adoption | ⬜ pending |

## Next up: Phase 5 — memory & historical learning

Add GitHub-native engineering memory without an external database.

- **Read first:** CONTEXT-GRAPH.md → then ROOT, PLAN, P5, P3.
- **Goal:** persist compact memory records per run (alongside report artifacts);
  retrieve prior records for the current PR and similar past PRs (by path/
  category/keyword; HF embeddings only if configured, else keyword/path match);
  feed historical matches into the LangGraph state for a Historical Knowledge
  signal; power `@codeguardian compare` / "has this happened before?". Never
  store secrets or large code chunks. Memory disableable by policy.
- **Keep working:** zero-key path, quiet defaults, evidence-cited output.
