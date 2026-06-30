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

1. **Code + IMPROVEMENT-PLAN are the source of truth.** Do not invent
   architecture. The current code wins for delivered behavior; the
   `doc/IMPROVEMENT-PLAN.md` queue defines what's next. Both override
   `doc/CodeGuardian-AI-Blueprint.md` when the blueprint describes a larger
   deferred end state.
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

All build phases (0–12) are delivered. Application code lives under
`src/codeguardian/` (Python + LangGraph + Pydantic — a committed stack choice
that overrides the docs' TypeScript recommendation). It runs as a GitHub Action,
zero-key deterministic, with a full test suite. Forward work is now incremental
upgrades, prioritized in [doc/IMPROVEMENT-PLAN.md](doc/IMPROVEMENT-PLAN.md).

Always check [CONTEXT-GRAPH.md](CONTEXT-GRAPH.md) for doc routing and the code
map. When asked to implement, prefer a P0/P1 item from the improvement plan over
inventing new scope.

## Where the plans live

- [doc/IMPROVEMENT-PLAN.md](doc/IMPROVEMENT-PLAN.md) — **active** backlog
  (P0/P1/P2 with file-level pointers; this is what to work on next).
- [doc/POST-V1-ROADMAP.md](doc/POST-V1-ROADMAP.md) — what v1.0 is deliberately
  *not* doing (hosted SaaS, full language parity, learned ML).
- [doc/GA-CHECKLIST.md](doc/GA-CHECKLIST.md) — the v1.0 cut sequence.
- [doc/CodeGuardian-AI-Blueprint.md](doc/CodeGuardian-AI-Blueprint.md) — the
  original long-term vision (historical; read for *why* the product looks the
  way it does).
- [doc/GitHub-PR-User-Flowmap.md](doc/GitHub-PR-User-Flowmap.md) — end-to-end
  PR UX flow.

If the blueprint and current code conflict, **the code (and IMPROVEMENT-PLAN)
wins** — the blueprint describes a larger deferred end state.

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
