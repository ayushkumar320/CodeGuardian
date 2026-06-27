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
| P4 | DB / API / architecture analyzers (deep) + policy | ✅ done — types/layers/cycles/spec-drift, richer policy |
| P5 | GitHub-native memory & history | ✅ done — branch-backed memory, similarity retrieval, history node, 55 tests green |
| **P6** | **Packaging, distribution, adoption** | **▶ NEXT — start here** |

## Next up: Phase 6 — packaging, distribution, adoption

Make CodeGuardian easy to install, configure, and trust as a reusable Action.

- **Read first:** CONTEXT-GRAPH.md → then ROOT, PLAN, P6, P1.
- **Goal:** Marketplace-ready `action.yml` (pin install, not pip-from-source on
  every run); minimal example workflow + starter policy; onboarding +
  troubleshooting guide; versioning/release process; CI validating the Action on
  fixture PR diffs; document Groq/HF setup and the zero-key default.
- **Keep working:** zero-key deterministic default, quiet-by-default UX.
