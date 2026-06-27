# CURRENT PHASE

Quick reference for where the build is. Update this when a phase ships.

- **Branch model:** solo dev — commit directly to `main`.
- **Stack (committed):** Python + LangGraph + Pydantic. Overrides the docs'
  TypeScript recommendation.
- **Active plan:** [doc/build/README.md](doc/build/README.md) — Production &
  Shipment (v1.0). MVP build record archived under
  [doc/build/archive/](doc/build/archive/).

## MVP (Phases 0–6) — ✅ DELIVERED

PR checker + LangGraph agents + `@codeguardian` loop + deep analyzers +
GitHub-native memory + packaging. Code under `src/codeguardian/`; 55 tests green;
runs zero-key deterministic. Detail: [archive/](doc/build/archive/).

## Production track (Phases 7–12) — toward v1.0 GA

| Phase | What | State |
|-------|------|-------|
| **P7** | **Real-PR validation & live-API hardening** | **▶ NEXT — start here** |
| P8 | Robustness & observability (never-crash, retries, job summary) | ⬜ pending |
| P9 | Security & supply-chain hardening (fork-PR safety, injection corpus) | ⬜ pending |
| P10 | Performance & scale (shared import graph, memory compaction) | ⬜ pending |
| P11 | Release engineering & Marketplace (reproducible packaging, automation) | ⬜ pending |
| P12 | Beta, tuning & v1.0 GA | ⬜ pending |

## Next up: Phase 7 — real-PR validation

Prove the Action against the live GitHub API before deeper hardening.

- **Read first:** CONTEXT-GRAPH.md → then ROOT, BIDX, P7.
- **Goal:** install on a sandbox repo; exercise low-risk/high-risk/comment-command
  /recheck/ignore/compare/history on public, private, and **fork** PRs; fix
  live-API gaps (comment pagination, artifact download, recheck head fetch, memory
  branch push, fork read-only token + no secrets, rate limits, large diffs); add
  an `e2e/` harness.
- **Keep working:** zero-key deterministic path, quiet defaults, evidence-cited.

## Open operational items (not new phases)

- Push `main` to `origin` (currently several commits ahead).
- Cut `v0.1.0` once P7 validates live behavior (see RELEASING.md) — note: the
  first GA tag is **v1.0** at the end of P12.
