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
| P3 | `@codeguardian` PR conversation loop | ✅ done — command parser, handlers, recheck/ignore, 36 tests green |
| **P4** | **DB / API / architecture analyzers (deep) + policy** | **▶ NEXT — start here** |
| P5 | GitHub-native memory & history | ⬜ pending |
| P6 | Packaging, distribution, adoption | ⬜ pending |

## Next up: Phase 4 — deep DB / API / architecture analysis

Expand the Phase 2 baseline analyzers into the product's strongest risk categories.

- **Read first:** CONTEXT-GRAPH.md → then ROOT, PLAN, P4, P1, P2.
- **Goal:** real Prisma schema diff + destructive-migration detection; API
  request/response shape diffing (incl. OpenAPI/GraphQL when specs exist);
  shared-types breakage; layer-direction + circular-dep architecture rules;
  richer `.codeguardian/policy.yml` (layers, service owners, test-suite maps,
  ignored findings). Every finding still cites evidence into the agent state.
- **Keep working:** deterministic without LLMs, zero-key path.
