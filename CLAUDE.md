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

1. **Docs are the source of truth; the build plan wins for the MVP.** Do not
   invent architecture. For MVP conflicts, `doc/Phase-Wise-Build-Plan.md` and
   `doc/build/` override `doc/CodeGuardian-AI-Blueprint.md`.
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
8. **Stay in MVP scope.** Do not build out-of-scope items (Neo4j, enterprise SSO,
   all-language support, learned ML model, runtime observability, hosted
   dashboard/DB) unless the user explicitly asks.
9. **Confirm before scaffolding code or committing a stack choice** — the stack
   below is a doc recommendation, not yet a committed decision.
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

**This repo is documentation-only. There is no application code yet.** The work so
far defines the product and the build plan. Everything in `doc/` is the source of
truth for *what to build*; implementation has not started.

When asked to implement, follow the phased plan rather than inventing a new
architecture. Confirm scope against the relevant phase doc first.

## Where the plans live

- [doc/CodeGuardian-AI-Blueprint.md](doc/CodeGuardian-AI-Blueprint.md) — full product + engineering blueprint (the long-term vision: knowledge graph, multi-agent AI, SaaS scaling, billing, security). Read for *why* and the eventual target.
- [doc/Phase-Wise-Build-Plan.md](doc/Phase-Wise-Build-Plan.md) — converts the blueprint into a buildable, **GitHub-Actions-first** MVP plan. Read for *what to build now*.
- [doc/build/](doc/build/) — per-phase detail. Start at [doc/build/README.md](doc/build/README.md), then phases 0–6.
- [doc/GitHub-PR-User-Flowmap.md](doc/GitHub-PR-User-Flowmap.md), [doc/Workflow-Improvements.md](doc/Workflow-Improvements.md) — UX flow and refinements.

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

In scope (Phase 0–6): GitHub App/Action install, PR analysis on every update,
risk check + sticky comment, JS/TS/Node/React/Next support, import/dependency
graph, heuristic test recommendations, basic architecture rules (forbidden
imports, layer direction, circular deps), basic Prisma migration risk,
`@codeguardian` conversation loop, GitHub-native memory (workflow artifacts).

**Out of scope for MVP** (don't build these unless explicitly asked): Neo4j
deployment, enterprise SSO/SAML, all-language support, a learned ML risk model,
runtime observability, a hosted dashboard/database.

## Intended stack (per the blueprint — not yet scaffolded)

TypeScript throughout. Frontend Next.js + Tailwind (dashboard is post-MVP).
Backend NestJS/Fastify modular monolith + workers. PostgreSQL (source of truth),
Redis, object storage, queue. Graph as PostgreSQL adjacency tables first (Neo4j
much later). `pgvector` for embeddings. Tree-sitter + TS compiler API for parsing.
LangGraph for agent orchestration.

Confirm the actual stack choice with the user before scaffolding — these are
recommendations in the doc, not yet committed decisions in code.
