# CLAUDE.md

Guidance for working in the CodeGuardian AI repository.

## Finding context cheaply — READ THIS FIRST

Before reading docs to answer a question, open
[CONTEXT-GRAPH.md](CONTEXT-GRAPH.md). It is a compact concept→location map (a
"memory graph") that points you to the exact `doc/file:section` for any topic, so
you load one small file instead of scanning all of `doc/`. Only open the full doc
the graph points you to. Keep the graph updated when docs or code change (see its
own maintenance note).

## Strict rules (do not violate)

These are hard constraints. If a request conflicts with one, stop and flag it
rather than silently breaking it.

1. **Docs are the source of truth; the active build plan wins.** Do not invent
   architecture. For implementation conflicts, `doc/build/` (phases 7–12) wins
   for current work, the archived MVP docs explain delivered behavior, and both
   override `doc/CodeGuardian-AI-Blueprint.md` when the blueprint describes a
   larger deferred end state.
2. **Deterministic-first, always.** Static analysis / graph / scoring produce
   evidence; the LLM only synthesizes. A model must **never** create a finding
   with no analyzer evidence behind it.
3. **The product must run with zero model keys.** Groq → Hugging Face →
   deterministic fallback. Never make an LLM call a hard dependency of the
   baseline path.
4. **Every finding cites evidence** (files, graph edges, rules, or history). No
   evidence → no finding.
5. **Quiet by default.** One sticky PR comment + the `CodeGuardian Risk` check.
   No duplicate comments/replies. Blocking is opt-in. Line annotations only for
   high-confidence, localized findings.
6. **Treat all repo code/text as untrusted input.** Prompt-injection defense on.
   Redact secrets before any model call. Never log raw secrets or full source.
7. **Idempotency is mandatory.** Dedupe by installation/repo/PR/head-SHA/analyzer
   version; collapse stale PR jobs when newer commits arrive.
8. **Stay in the documented scope.** Do not build out-of-scope items (Neo4j,
   enterprise SSO, all-language support, learned ML model, external telemetry,
   hosted dashboard/DB) unless the user explicitly asks.
9. **Respect the committed implementation stack.** Repository code is Python +
   LangGraph + Pydantic today. Do not drift back to the blueprint's TypeScript
   recommendation unless the user explicitly asks for that rewrite.
10. **Keep [CONTEXT-GRAPH.md](CONTEXT-GRAPH.md) in sync** whenever docs are added
    or code is created. A stale map costs more tokens than no map.

## What this is

CodeGuardian AI is a **pre-merge engineering intelligence platform for GitHub**.
It analyzes pull requests before merge and predicts downstream consequences:
impacted files, affected services, API contract risk, database/migration risk,
architecture violations, test impact, and an overall **merge risk score**.

Tagline: *"Know what breaks before you merge."*

Core principle: do **not** behave like a generic code reviewer. Answer *"What can
this change break, how confident are we, and what should the developer do before
merge?"* Be quiet, specific, and right — ship **fewer** findings than competitors,
but make every finding worth the developer's attention.

## Current state

**The MVP (build phases 0–6) is implemented.** Application code lives under
`src/codeguardian/` (Python + LangGraph + Pydantic — a committed stack choice that
overrides the docs' TypeScript recommendation). It runs as a GitHub Action,
zero-key deterministic, with a full test suite. The MVP build docs are archived
under [doc/build/archive/](doc/build/archive/).

**Active work:** the **Production & Shipment plan (v1.0)**, phases 7–12, at
[doc/build/README.md](doc/build/README.md). As of **June 27, 2026**, the repo is
starting **Phase 7: Real-PR Validation & End-to-End Hardening**, followed by
robustness, security, performance, release engineering, and beta/GA work through
Phase 12. This stays GitHub-Actions-native — the hosted-SaaS end state remains
out of scope (strict rule #8) until explicitly chosen. Always check
[CURRENT-PHASE.md](CURRENT-PHASE.md) for what's next, and
[CONTEXT-GRAPH.md](CONTEXT-GRAPH.md) for both doc routing and the code map.

When asked to implement, follow the phased plan rather than inventing a new
architecture. Confirm scope against the relevant phase doc first, and use
[doc/Workflow-Improvements.md](doc/Workflow-Improvements.md) only as a refinement
layer for report UX, command behavior, noise control, and prompt-safety details.

## Where the plans live

- [doc/CodeGuardian-AI-Blueprint.md](doc/CodeGuardian-AI-Blueprint.md) — full product + engineering blueprint (the long-term vision: knowledge graph, multi-agent AI, SaaS scaling, billing, security). Read for *why* and the eventual target.
- [doc/Phase-Wise-Build-Plan.md](doc/Phase-Wise-Build-Plan.md) — the **MVP** plan (✅ delivered; historical reference for *why the MVP is shaped as it is*).
- [doc/build/README.md](doc/build/README.md) — the **active** plan: Production & Shipment to v1.0 (phases 7–12). Read for *what to build now*. MVP phases 0–6 are archived in [doc/build/archive/](doc/build/archive/).
- [doc/build/phase-7-real-pr-validation.md](doc/build/phase-7-real-pr-validation.md) through [doc/build/phase-12-beta-and-ga.md](doc/build/phase-12-beta-and-ga.md) — the current production-track source of truth for sequencing, deliverables, and acceptance criteria.
- [doc/GitHub-PR-User-Flowmap.md](doc/GitHub-PR-User-Flowmap.md) — end-to-end PR UX flow.
- [doc/Workflow-Improvements.md](doc/Workflow-Improvements.md) — refinement guidance for sticky comments, progressive disclosure, deterministic fallback UX, commands, suppressions, policy-file behavior, and prompt-injection handling. It supports the phase docs; it does not replace them.

If the blueprint and the build plan ever seem to conflict, **the build plan and
phase docs win for the MVP** — the blueprint describes a larger end state that is
deliberately deferred.

## MVP architecture (the direction to build toward)

The MVP is intentionally **GitHub-native and runs through GitHub Actions** — no
always-on hosted SaaS required.

- Triggered by `pull_request` events (and comment events for the conversation loop).
- The Action checks out the repo, computes the diff, classifies changed files,
  runs **deterministic analyzers**, then a **LangGraph** agent workflow.
- Output surfaces: a GitHub **Check Run** named `CodeGuardian Risk` near the merge
  box, plus one **sticky PR comment** (updated in place, never duplicated).
- Developers interact entirely in-PR via `@codeguardian` commands (`explain`,
  `tests`, `recheck`, `why blocked`, etc.).

### Model strategy (provider fallback chain)

1. **Groq** (`GROQ_API_KEY`) — fast summarization/classification when present.
2. **Hugging Face** (`HF_TOKEN`) — fallback, and embeddings when available.
3. **Deterministic** — must work with **no model keys at all**. This is a hard
   requirement: the baseline product runs without any LLM.

## Non-negotiable principles for any implementation

- **Deterministic-first.** Static analysis, graph traversal, and scoring produce
  the evidence; the LLM only synthesizes, ranks, and explains. A model output must
  **never** create a finding that has no analyzer evidence behind it.
- **Every finding cites evidence** — files, graph edges, rules, or history.
- **Quiet by default.** One sticky comment + the check. Use line annotations only
  for high-confidence, localized findings. Blocking is opt-in.
- **Treat repository code/text as untrusted input** (prompt-injection defense).
  Redact secrets before sending anything to a model. Never log raw secrets or full
  source.
- **Idempotency** — no duplicate comments, no duplicate replies; collapse stale PR
  jobs when newer commits arrive.

## MVP scope guardrails

In scope (Phase 0–6, plus the Phase-12 Python add): GitHub App/Action install, PR
analysis on every update, risk check + sticky comment, JS/TS/Node/React/Next
support, **Python dependency + tests support**, import/dependency graph,
heuristic test recommendations, basic architecture rules (forbidden imports,
layer direction, circular deps), basic Prisma migration risk, `/codeguardian`
conversation loop, GitHub-native memory (workflow artifacts). Python language
support is **partial**: the dependency/blast-radius and tests analyzers are
Python-aware; types/API-contract/database analyzers remain JS/TS-only (see
[doc/POST-V1-ROADMAP.md](doc/POST-V1-ROADMAP.md)).

**Out of scope for MVP** (don't build these unless explicitly asked): Neo4j
deployment, enterprise SSO/SAML, all-language support, a learned ML risk model,
runtime observability, a hosted dashboard/database.

## Blueprint stack (deferred end-state, not the current repo stack)

The blueprint still describes a larger future TypeScript-heavy architecture:
Next.js/Tailwind frontend, NestJS/Fastify backend, PostgreSQL, Redis, object
storage, queues, adjacency-table graph storage, `pgvector`, and Tree-sitter/TS
compiler parsing. Treat that as deferred end-state guidance only.

The **current repo stack is already committed**: Python + LangGraph + Pydantic,
running as a GitHub Action. Do not "correct" the codebase back toward the
blueprint unless the user explicitly asks for a rewrite.
