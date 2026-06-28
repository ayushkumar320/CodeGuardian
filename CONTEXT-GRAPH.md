# CONTEXT-GRAPH.md

A compact **concept → location** memory graph for CodeGuardian AI. Purpose: find
the right doc/section without reading every file. Read this first; then open only
the one `doc/...:Section` a node points to.

- **Repo state:** MVP complete (Phase 0–6). Code under `src/codeguardian/`.
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
| PLAN | [doc/Phase-Wise-Build-Plan.md](doc/Phase-Wise-Build-Plan.md) | MVP plan (✅ delivered; historical reference) |
| BIDX | [doc/build/README.md](doc/build/README.md) | **Active** production & shipment plan (v1.0): phases 7–12 |
| P7 | [doc/build/phase-7-real-pr-validation.md](doc/build/phase-7-real-pr-validation.md) | Real-PR validation & live-API hardening (▶ next) |
| P8 | [doc/build/phase-8-robustness-observability.md](doc/build/phase-8-robustness-observability.md) | Never-crash, retries/timeouts, job summary, logs |
| P9 | [doc/build/phase-9-security-hardening.md](doc/build/phase-9-security-hardening.md) | Fork-PR safety, prompt-injection corpus, supply chain |
| P10 | [doc/build/phase-10-performance-scale.md](doc/build/phase-10-performance-scale.md) | Perf budgets, shared import graph, memory compaction |
| P11 | [doc/build/phase-11-release-marketplace.md](doc/build/phase-11-release-marketplace.md) | Reproducible packaging, release automation, Marketplace |
| P12 | [doc/build/phase-12-beta-and-ga.md](doc/build/phase-12-beta-and-ga.md) | Beta, scoring tuning, v1.0 GA |
| MVPDOCS | [doc/build/archive/](doc/build/archive/) | ✅ Delivered MVP build phases 0–6 (archived record) |
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
| Current production objective / what v1.0 means | BIDX "Goal", "Definition Of Production-Ready (v1.0 done)" |
| **Realized product contract (check states, score rubric, blocking modes, sticky comment, commands, data contracts)** | P0C |
| Check conclusion mapping (success/neutral/action_required/failure) per mode | P0C §A2, §A5 |
| Finding / Report / PrContext / State TypeScript contracts | P0C §B4, §B5 |
| Build order between phases | BIDX "Recommended Build Order" |
| Why phases 7–12 stay GitHub-Actions-native and still exclude hosted SaaS | BIDX intro ; ROOT strict rule #8 |
| Real-PR validation scope / sandbox repo / public-private-fork coverage | P7 "Objective", "Scope", "Deliverables" |
| Live API gaps to harden first (pagination, rate limits, large diffs, concurrent runs, missing permissions) | P7 "Scope" |
| E2E harness expectations for real PRs | P7 "Deliverables", "Acceptance Criteria" |
| Never-crash boundary / degraded-run behavior / exit-0 on internal errors | P8 "Scope", "Deliverables", "Acceptance Criteria" ; `src/codeguardian/__main__.py` (`run`, `_internal_error_report`) ; `models.py` (`Report.errors`, `degraded`) |
| Retry/backoff/timeouts for GitHub, Groq, HF | P8 "Scope", "Deliverables" ; `src/codeguardian/http.py` (`request`) |
| Debug logging (`CODEGUARDIAN_DEBUG`, secret-safe) | P8 "Scope" ; `src/codeguardian/log.py` (`get_logger`, `debug_enabled`) |
| Job summary writer (`$GITHUB_STEP_SUMMARY`) | P8 "Deliverables" ; `src/codeguardian/__main__.py` (`_write_job_summary`) |
| `--selfcheck` (env, token reachability, provider) | P8 "Deliverables" ; `src/codeguardian/selfcheck.py` (`run_selfcheck`) |
| Fork PR safety / `pull_request` vs `pull_request_target` guidance | P9 ; `doc/INSTALL.md` "Permissions explained" ; `doc/THREAT-MODEL.md` (T4) ; `__main__._can_publish` |
| Prompt-injection validation corpus and evidence-only model rule | P9 ; WFI §19 ; `tests/injection_corpus.py` ; `tests/test_phase9_security.py` ; `models.Finding` (evidence required) |
| Output secret scanning before posting (egress) | P9 ; `src/codeguardian/security.py` (`safe_output`, `find_secrets`) ; `github/client.py` (`_scrub`) |
| Secret reporting / vulnerability disclosure / security posture | `SECURITY.md` ; `doc/THREAT-MODEL.md` |
| Supply-chain hardening (SHA-pinned actions, Dependabot, CodeQL) | P9 ; `.github/workflows/*.yml` + `action.yml` (SHA pins) ; `.github/dependabot.yml` ; `.github/workflows/codeql.yml` |
| SBOM / signed releases (release-time supply chain) | P9 "Deliverables" ; deferred to P11 release workflow ; [RELEASING.md](doc/RELEASING.md) |
| Performance bottlenecks to measure first | P10 "Current cost centers (to measure first)" |
| Shared import graph / bounded repo walk / batched diff parsing | P10 "Scope", "Deliverables" |
| Large-diff caps / soft timeout / partial-result publishing | P10 "Scope", "Deliverables" |
| Memory retention / compaction policy | P10 "Scope", "Deliverables" ; `src/codeguardian/policy.py` (`Memory`) ; `src/codeguardian/memory/*` |
| Release packaging choice (Docker vs locked wheels) | P11 "Scope", "Deliverables" |
| Automated release workflow / moving `v1` tag / SemVer consumer contract | P11 "Scope", "Deliverables", "Acceptance Criteria" ; [RELEASING.md](doc/RELEASING.md) |
| Marketplace listing assets / examples / screenshots | P11 "Scope", "Deliverables" |
| Beta plan / dogfood repos / false-positive feedback loop | P12 "Scope", "Deliverables", "Acceptance Criteria" |
| Scoring and threshold tuning for low false positives | P12 "Scope", "Deliverables" |
| GA readiness / support-triage / post-v1 roadmap | P12 "Scope", "Deliverables" |
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
| Opt-in `require_model` / `block_when_missing` (guarantee LLM summary ran) | `src/codeguardian/policy.py` (`Model`) ; `graph/agents.py` (`recommendation_agent`) ; `.codeguardian/policy.yml` ; `doc/INSTALL.md` |
| Recheck / compare / ignore command behavior | WFI §13, §14, §17 ; P3 "Supported Commands", "Command Rules" |
| Suppression accountability | WFI §14 ; P3 "Command Rules" ; P4 "Policy File" |
| Progressive disclosure in reports / concise PR comment vs full artifact | WFI §3, §18 |
| Policy-file refinement ideas and service-owner hints | WFI §15, §16 ; `src/codeguardian/policy.py` |
| Quiet rollout strategy (advisory -> guarded -> strict) | WFI §9 ; ROOT "Quiet by default" |
| Prompt-injection and untrusted repo text rules | WFI §19 ; PLAN "Prompt Safety Rules" ; ROOT "Strict rules" |
| Build prompt token-saving rules | This file, "Build prompt preflight" |

## Code map (Phase 1–5)

Python package at `src/codeguardian/`. Stack: Python + LangGraph + Pydantic.

| If you need… | Go to |
|---|---|
| Memory record (compact, privacy-safe) + signature | `src/codeguardian/memory/record.py` |
| Memory stores (local JSONL / git branch) | `src/codeguardian/memory/store.py` |
| Similarity retrieval (path/category Jaccard) | `src/codeguardian/memory/retrieve.py` |
| Historical-knowledge graph node | `src/codeguardian/graph/agents.py` (`historical_knowledge_agent`) |
| Memory policy (enable/branch/thresholds) | `src/codeguardian/policy.py` (`Memory`) |
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
| Secret redaction (ingress) / untrusted-text fencing / egress secret-scan | `src/codeguardian/security.py` (`redact`, `wrap_untrusted`, `find_secrets`, `safe_output`) |
| Egress secret-scan chokepoint before posting | `src/codeguardian/github/client.py` (`_scrub`) |
| Prompt-injection corpus + security tests | `tests/injection_corpus.py`, `tests/test_phase9_security.py` |
| Supply-chain config (SHA-pinned actions, Dependabot, CodeQL) | `.github/workflows/*.yml`, `.github/dependabot.yml`, `.github/workflows/codeql.yml` |
| Security policy / threat model | `SECURITY.md`, `doc/THREAT-MODEL.md` |
| LangGraph state (reducers) / entry+context nodes / domain+synthesis agents / builder | `src/codeguardian/graph/state.py`, `graph/nodes.py`, `graph/agents.py`, `graph/build.py` |
| Check summary / sticky comment / artifacts | `src/codeguardian/report.py` |
| GitHub event parsing + REST client | `src/codeguardian/github/events.py`, `github/client.py` |
| Retry+timeout HTTP helper (backoff+jitter; used by client + providers) | `src/codeguardian/http.py` (`request`) |
| Leveled secret-safe logging (`CODEGUARDIAN_DEBUG`) | `src/codeguardian/log.py` |
| `--selfcheck` diagnostics (env / token / provider) | `src/codeguardian/selfcheck.py` |
| Action entrypoint (publish + exit code, failure boundary, job summary, `--selfcheck` dispatch) | `src/codeguardian/__main__.py` |
| Action metadata (inputs) / example workflow / CI / policy | `action.yml`, `.github/workflows/codeguardian.yml`, `.github/workflows/ci.yml`, `.codeguardian/policy.yml` |
| Install / troubleshooting / changelog / release docs | `doc/INSTALL.md`, `doc/TROUBLESHOOTING.md`, `CHANGELOG.md`, `doc/RELEASING.md` |
| How to run/test (local no-token, sandbox Action, e2e harness) | `doc/TESTING.md` ; `scripts/run-local.sh` ; `e2e/` ; `doc/build/phase-7-runbook.md` |
| Tests | `tests/` |

## Build prompt preflight

Use this preflight at the top of implementation prompts to avoid pasting broad
product context:

```text
Before implementing, read CONTEXT-GRAPH.md first. Then open only ROOT, PLAN, and
the current phase node(s) named below. Treat those docs as the source of truth;
do not re-read the blueprint unless a graph edge explicitly points there.
```

Recommended phase node sets (active = production plan; MVP nodes are in archive/):

| Build task | Read |
|---|---|
| Real-PR validation | ROOT, BIDX, P7, Code map |
| Robustness/observability | ROOT, BIDX, P8, Code map |
| Security hardening | ROOT, BIDX, P9, WFI |
| Performance/scale | ROOT, BIDX, P10, Code map |
| Release/Marketplace | ROOT, BIDX, P11, doc/RELEASING.md |
| Beta/GA | ROOT, BIDX, P12 |
| Workflow/report UX refinements | ROOT, WFI, then the matching active phase doc |
| (MVP history) any 0–6 topic | archive/ + Code map |

## Key invariants (memorize; don't re-derive)

- Surfaces: GitHub **Check Run `CodeGuardian Risk`** + **one sticky PR comment**.
- Triggers: `pull_request` (opened/reopened/synchronize/ready_for_review) +
  comment events for the conversation loop.
- Provider fallback: **Groq → Hugging Face → deterministic** (zero-key path must work).
- LLM synthesizes only; deterministic analyzers own the evidence.
- MVP languages: JS / TS / Node / React / Next.
- Publishing split: check = merge decision, sticky comment = concise why, artifacts = full evidence.
- Quiet defaults: advisory mode first, no long comments for docs-only or low-risk changes.
