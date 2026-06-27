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
| P2 | LangGraph agentic AI (per-domain agents) | ✅ done — parallel agent graph, API/DB/arch analyzers, 21 tests green |
| **P3** | **`@codeguardian` PR conversation loop** | **▶ NEXT — start here** |
| P4 | DB / API / architecture analyzers + policy | ⬜ pending |
| P5 | GitHub-native memory & history | ⬜ pending |
| P6 | Packaging, distribution, adoption | ⬜ pending |

## Next up: Phase 3 — PR conversation loop

Let developers interact with CodeGuardian via `@codeguardian` PR comments.

- **Read first:** CONTEXT-GRAPH.md → then ROOT, PLAN, P3, P1, P5.
- **Goal:** handle `issue_comment` / `pull_request_review_comment` events; parse
  `@codeguardian` commands (`explain`, `tests`, `why blocked`, `recheck`,
  `compare`, `summary`, `ignore <id>`); load the latest report artifact; reply
  in-thread idempotently; ignore bot comments; `recheck` re-dispatches analysis.
- **Keep working:** quiet defaults, evidence-cited answers, zero-key path.
