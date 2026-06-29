# Post-v1.0 roadmap (explicitly deferred)

What v1.0 is **not** trying to be, and what could come next. This document keeps
the v1.0 product small and clear, and gives future contributors a place to start
without expanding the GA scope.

## v1.0 is

- A **GitHub-Action-native, pre-merge risk checker** for JS/TS/Node/React/Next.
- **Deterministic-first.** Static analysis owns the score and findings; an LLM
  (optional) rephrases the summary only.
- **Quiet by default.** One check, one sticky comment. Blocking is opt-in.
- **Zero-key by default.** Groq/HF are optional.

## What v1.0 is not — and why

Each item below is deliberately deferred. If you want to pick one up post-GA,
the notes are the starting point.

### Hosted / SaaS backend
- *Not in v1.0.* Strict rule #8 keeps the product GitHub-Actions-native.
- Post-v1.0 path: a thin hosted endpoint to centralize memory and benchmarks
  across consumer repos. Only worth doing if there's clear demand and a way to
  keep the zero-key, in-Action default working unchanged.

### More language support
- *Not in v1.0.* Analyzers are tuned for JS/TS/Node/React/Next.
- Post-v1.0 path: start with Python (analyzers/imports.py already walks `.py`),
  then Go. Schema diff + API contract analyzers will need per-language pieces.

### Richer API / schema contract analyzers
- *Not in v1.0.* The current API analyzer is heuristic.
- Post-v1.0 path: OpenAPI / GraphQL / tRPC schema diff; SDL-aware breaking
  change detection. Highest-value next analyzer per beta feedback.

### Learned ML risk model
- *Not in v1.0.* Strict rule #2 (deterministic-first, evidence-cited).
- Post-v1.0 path: an *advisory layer on top of* the deterministic score, never a
  replacement, and only with labeled outcomes from memory records.

### Marketplace billing / paid tiers
- *Not in v1.0.* GA is OSS-only.

## Roadmap candidates, ranked by likely impact

1. Python analyzer parity (imports + tests, then types).
2. OpenAPI / GraphQL schema-diff analyzer.
3. PR-level cost/time observability (artifact JSON already has timings).
4. Optional hosted backend (only if real demand surfaces).
5. Go support.
6. Learned-ML advisory layer over deterministic findings.

This list is suggestive, not committed. Beta feedback can re-order it freely.
