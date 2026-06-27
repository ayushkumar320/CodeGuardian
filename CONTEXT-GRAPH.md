# CONTEXT-GRAPH.md

A compact **concept → location** memory graph for CodeGuardian AI. Purpose: find
the right doc/section without reading every file. Read this first; then open only
the one `doc/...:Section` a node points to.

- **Repo state:** Phase 0–4 implemented. Code under `src/codeguardian/`.
  Stack is **Python + LangGraph** (committed; overrides the docs' TypeScript
  recommendation).
- **Authority:** for MVP conflicts, the build plan + phase docs override the
  blueprint. See [CLAUDE.md](CLAUDE.md) strict rules.
- **Maintenance:** update the relevant node whenever you add a doc or create code.
  See "Code map (Phase 1)" below for the source layout.

## Files (nodes)

| ID | File | One-line role |
|----|------|----------------|
| ROOT | [CLAUDE.md](CLAUDE.md) | Repo working rules, MVP invariants, scope guardrails |
| BP | [doc/CodeGuardian-AI-Blueprint.md](doc/CodeGuardian-AI-Blueprint.md) | Long-term product + engineering vision (the end state) |
| PLAN | [doc/Phase-Wise-Build-Plan.md](doc/Phase-Wise-Build-Plan.md) | GitHub-Actions-first MVP plan (what to build now) |
| BIDX | [doc/build/README.md](doc/build/README.md) | Index + build order for the phase docs |
| P0 | [doc/build/phase-0-product-foundation.md](doc/build/phase-0-product-foundation.md) | Product contract spec, GitHub-native UX |
| P0C | [doc/build/phase-0-product-contract.md](doc/build/phase-0-product-contract.md) | **Realized** Phase 0 contract: journey, rubric, blocking, comment/check copy, commands, tech foundation |
| P1 | [doc/build/phase-1-github-actions-pr-checker.md](doc/build/phase-1-github-actions-pr-checker.md) | First working PR risk checker MVP |
| P2 | [doc/build/phase-2-langgraph-agentic-ai.md](doc/build/phase-2-langgraph-agentic-ai.md) | Multi-agent LangGraph workflow |
| P3 | [doc/build/phase-3-pr-conversation-loop.md](doc/build/phase-3-pr-conversation-loop.md) | `@codeguardian` in-PR commands |
| P4 | [doc/build/phase-4-advanced-analyzers.md](doc/build/phase-4-advanced-analyzers.md) | DB / API / architecture analysis + policy file |
| P5 | [doc/build/phase-5-memory-and-history.md](doc/build/phase-5-memory-and-history.md) | GitHub-native memory + historical learning |
| P6 | [doc/build/phase-6-packaging-and-adoption.md](doc/build/phase-6-packaging-and-adoption.md) | Reusable Action, onboarding, release |
| FLOW | [doc/GitHub-PR-User-Flowmap.md](doc/GitHub-PR-User-Flowmap.md) | End-to-end PR user flow |
| WFI | [doc/Workflow-Improvements.md](doc/Workflow-Improvements.md) | Workflow refinements |

## Concept → location (edges)

Pick the topic, open only the listed target.

| If you need… | Go to |
|---|---|
| What the product is / vision / moat / competitors | BP §1, §17 |
| PRD, users, functional/non-functional requirements | BP §2 |
| System architecture (modular monolith + workers) | BP §3 |
| AI design philosophy, multi-agent responsibilities | BP §4 |
| GitHub App vs Action, webhooks, checks, permissions | BP §5 ; PLAN "GitHub Actions-Only Deployment Model" |
| PostgreSQL schema / tables | BP §6 |
| Knowledge graph nodes, edges, storage, indexing | BP §7 |
| Public/internal API endpoints | BP §8 |
| Scaling stages, queues | BP §9 |
| Security + LLM security requirements | BP §10 ; PLAN "Prompt Safety Rules" |
| Roadmap / MVP vs V1 vs V2 scope | BP §11–§14 |
| Cost estimates | BP §15 |
| Monetization / pricing tiers | BP §18 |
| **MVP architecture diagram + constraints** | PLAN "Target MVP Architecture", "Build Constraints" |
| Required GitHub events / secrets / permissions | PLAN "Required GitHub Events/Secrets/Permissions" ; P1 "Required Inputs" |
| **Model routing Groq→HF→deterministic** | PLAN "Model Strategy" |
| PR merge-page output contract (example check) | PLAN "GitHub PR Merge Page Output Contract" |
| Definition of MVP done | PLAN "Definition Of Done" ; BIDX bottom |
| **Realized product contract (check states, score rubric, blocking modes, sticky comment, commands, data contracts)** | P0C |
| Check conclusion mapping (success/neutral/action_required/failure) per mode | P0C §A2, §A5 |
| Finding / Report / PrContext / State TypeScript contracts | P0C §B4, §B5 |
| Build order between phases | BIDX "Recommended Build Order" |
| Risk report / finding schema | P1 "Finding Schema" ; P4 "Finding schema" |
| LangGraph node list / state contract | P1 "LangGraph MVP Nodes" ; P2 "LangGraph State Contract" |
| Agent graph + per-agent rules | P2 "Agent Graph" ; BP §4 |
| Supported `@codeguardian` commands | P3 "Supported Commands" |
| Conversation event handling / idempotency | P3 "Senior Developer Prompt" |
| Prisma / SQL migration / API / arch analyzers | P4 "Deliverables" |
| `.codeguardian/policy.yml` policy file shape | P4 "Policy File Concept" |
| Memory storage options (artifacts/branch/issues) | P5 "GitHub Actions-Friendly Memory Options" |
| Packaging the Action / Marketplace / onboarding | P6 "Deliverables" |
| Sticky comment vs check vs artifact publishing split | WFI §3, §12, §18 ; P1 "Publishing Contract" |
| Noise budgets / docs-only quiet path / inline comment defaults | WFI §10, §11 ; P6 "Default Configuration" |
| Deterministic mode behavior when no model keys exist | WFI §5 ; P2 "Model Provider Routing" |
| Recheck / compare / ignore command behavior | WFI §13, §14, §17 ; P3 "Supported Commands", "Command Rules" |
| Suppression accountability | WFI §14 ; P3 "Command Rules" ; P4 "Policy File" |
| Prompt-injection and untrusted repo text rules | WFI §19 ; PLAN "Prompt Safety Rules" ; ROOT "Strict rules" |
| Build prompt token-saving rules | This file, "Build prompt preflight" |

## Code map (Phase 1–4)

Python package at `src/codeguardian/`. Stack: Python + LangGraph + Pydantic.

| If you need… | Go to |
|---|---|
| `@codeguardian` command parser / permissions / reply handlers / plan logic | `src/codeguardian/commands/parser.py`, `commands/permissions.py`, `commands/handlers.py`, `commands/loop.py` |
| Comment-event parsing / artifact retrieval / reply idempotency / get_pull | `src/codeguardian/github/events.py` (`parse_comment_event`), `github/client.py` (`latest_reports`, `already_replied`, `get_pull`) |
| Shared-type breakage analyzer | `src/codeguardian/analyzers/types.py` |
| Deep DB (Prisma field/model removal, destructive SQL) / API spec drift / layers+cycles | `analyzers/database.py`, `analyzers/api.py`, `analyzers/architecture.py` |
| Import graph (forward + reverse) | `src/codeguardian/analyzers/imports.py` (`build_forward_imports`, `build_reverse_imports`) |
| Glob matching with `**/` semantics | `src/codeguardian/globs.py` (`glob_match`, `matches_any`) |
| Policy: layers / test-suite maps / service owners / ignored findings | `src/codeguardian/policy.py` |
| ignored_findings pre-suppression + reviewer suggestions | `src/codeguardian/graph/agents.py` (`risk_scoring_agent`, `_reviewers`) |
| Data contracts (Finding/Report/PrContext/RepositoryContext/enums) | `src/codeguardian/models.py` |
| Policy loader + defaults (modes, thresholds, noise, architecture rules) | `src/codeguardian/policy.py` |
| PR diff from git / file classification | `src/codeguardian/pr/diff.py`, `pr/classify.py` |
| Deterministic analyzers (import blast radius, missing tests) | `src/codeguardian/analyzers/imports.py`, `analyzers/tests.py` |
| Deterministic analyzers (API contract, DB/migration, architecture) | `src/codeguardian/analyzers/api.py`, `analyzers/database.py`, `analyzers/architecture.py` |
| Risk scoring (confidence-weighted aggregate) | `src/codeguardian/scoring.py` |
| Provider router Groq→HF→deterministic + output schema validation | `src/codeguardian/providers.py` (`validate_summary`) |
| Secret redaction / untrusted-text fencing | `src/codeguardian/security.py` |
| LangGraph state (reducers) / entry+context nodes / domain+synthesis agents / builder | `src/codeguardian/graph/state.py`, `graph/nodes.py`, `graph/agents.py`, `graph/build.py` |
| Check summary / sticky comment / artifacts | `src/codeguardian/report.py` |
| GitHub event parsing + REST client | `src/codeguardian/github/events.py`, `github/client.py` |
| Action entrypoint (publish + exit code) | `src/codeguardian/__main__.py` |
| Action metadata / example workflow / policy | `action.yml`, `.github/workflows/codeguardian.yml`, `.codeguardian/policy.yml` |
| Tests | `tests/` |

## Build prompt preflight

Use this preflight at the top of implementation prompts to avoid pasting broad
product context:

```text
Before implementing, read CONTEXT-GRAPH.md first. Then open only ROOT, PLAN, and
the current phase node(s) named below. Treat those docs as the source of truth;
do not re-read the blueprint unless a graph edge explicitly points there.
```

Recommended phase node sets:

| Build task | Read |
|---|---|
| Product foundation | ROOT, PLAN, P0, WFI |
| PR checker MVP | ROOT, PLAN, P1, P2, WFI |
| LangGraph workflow | ROOT, PLAN, P2, P1 |
| PR conversation loop | ROOT, PLAN, P3, P1, P5 |
| Advanced analyzers | ROOT, PLAN, P4, P1, P2 |
| Memory/history | ROOT, PLAN, P5, P3 |
| Packaging/adoption | ROOT, PLAN, P6, P1 |

## Key invariants (memorize; don't re-derive)

- Surfaces: GitHub **Check Run `CodeGuardian Risk`** + **one sticky PR comment**.
- Triggers: `pull_request` (opened/reopened/synchronize/ready_for_review) +
  comment events for the conversation loop.
- Provider fallback: **Groq → Hugging Face → deterministic** (zero-key path must work).
- LLM synthesizes only; deterministic analyzers own the evidence.
- MVP languages: JS / TS / Node / React / Next.
- Publishing split: check = merge decision, sticky comment = concise why, artifacts = full evidence.
- Quiet defaults: advisory mode first, no long comments for docs-only or low-risk changes.
