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
| P5 | GitHub-native memory & history | ✅ done — branch-backed memory, similarity retrieval, history node |
| P6 | Packaging, distribution, adoption | ✅ done — Action inputs, CI, INSTALL/TROUBLESHOOTING/CHANGELOG/RELEASING |

**MVP complete (Phases 0–6).** Next is hardening + a real release tag, or post-MVP
items (see below).

## Next up: hardening / release

The build plan (Phases 0–6) is implemented. Remaining work is operational:

- Cut the first real release: tag `v0.1.0` + moving `v0` (see RELEASING.md).
- Validate on a live PR: required-check gating, `recheck` fetching the PR head,
  and the `codeguardian-memory` branch push under real permissions.
- Post-MVP (only if asked — out of scope per CLAUDE.md): Python/other languages,
  Neo4j graph, hosted dashboard/DB, learned ML risk model, SSO.
