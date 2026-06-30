# CONTEXT-GRAPH.md

A compact **concept → file** map for CodeGuardian. Purpose: find the right
file/symbol without grepping every directory. Read this first; then open only
the one entry a node points to.

- **Repo state:** all build phases (0–12) delivered. Forward work is incremental
  upgrades from [doc/IMPROVEMENT-PLAN.md](doc/IMPROVEMENT-PLAN.md).
- **Stack:** Python + LangGraph + Pydantic (committed; overrides the
  blueprint's TypeScript recommendation).
- **Maintenance:** update the relevant row whenever you add a doc or a code
  module. Stale map costs more tokens than no map.

## Docs

| ID | File | Role |
|----|------|------|
| ROOT | [CLAUDE.md](CLAUDE.md) | Repo working rules + strict rules + scope guardrails |
| IMP  | [doc/IMPROVEMENT-PLAN.md](doc/IMPROVEMENT-PLAN.md) | **Active** P0/P1/P2 backlog with file-level pointers |
| ZT   | [doc/ZERO-TOUCH-PLAN.md](doc/ZERO-TOUCH-PLAN.md) | v1.1 plan: one-command activation, risk dashboard, quality analyzer, Groq model tier |
| GA   | [doc/GA-CHECKLIST.md](doc/GA-CHECKLIST.md) | v1.0 cut sequence (what's automated vs human) |
| POST | [doc/POST-V1-ROADMAP.md](doc/POST-V1-ROADMAP.md) | What v1.0 is deliberately *not* doing |
| BP   | [doc/CodeGuardian-AI-Blueprint.md](doc/CodeGuardian-AI-Blueprint.md) | Original long-term vision (historical) |
| FLOW | [doc/GitHub-PR-User-Flowmap.md](doc/GitHub-PR-User-Flowmap.md) | End-to-end PR UX flow |
| SUP  | [SUPPORT.md](SUPPORT.md) | Triage + beta FP/FN bookkeeping |
| SEC  | [SECURITY.md](SECURITY.md), [doc/THREAT-MODEL.md](doc/THREAT-MODEL.md) | Security policy + threat model |
| INST | [doc/INSTALL.md](doc/INSTALL.md), [doc/TROUBLESHOOTING.md](doc/TROUBLESHOOTING.md), [doc/RELEASING.md](doc/RELEASING.md), [doc/TESTING.md](doc/TESTING.md) | User-facing operating docs |

## Concept → file (code map)

Topic → the symbol or file to open.

### Pipeline & contracts
| If you need… | Go to |
|---|---|
| Action entrypoint (publish + exit, failure boundary, job summary, `--selfcheck`) | `src/codeguardian/__main__.py` |
| Action metadata (inputs) | `action.yml` |
| Data contracts (Finding/Report/PrContext/DiffSummaryFile/enums) | `src/codeguardian/models.py` |
| LangGraph state + reducers + entry/context nodes + agents + builder | `src/codeguardian/graph/{state,nodes,agents,build}.py` |
| Risk scoring (confidence-weighted aggregate) | `src/codeguardian/scoring.py` |
| Provider router Groq→HF→deterministic + schema validation | `src/codeguardian/providers.py` (`summarize`, `answer_question`, `validate_summary`) |
| Check summary / sticky comment / markdown artifact | `src/codeguardian/report.py` |
| Check title (score+verdict+narrative snippet) · inline annotations · cost footer · reaction tally | `src/codeguardian/report.py` (`check_title`, `annotations_from_report`, `usage_footer`, `reaction_tally`, `FEEDBACK_FOOTER`) |
| Retry+timeout HTTP helper | `src/codeguardian/http.py` |
| Leveled secret-safe logging (`CODEGUARDIAN_DEBUG`) | `src/codeguardian/log.py` |
| `--selfcheck` diagnostics | `src/codeguardian/selfcheck.py` |

### Analyzers
| If you need… | Go to |
|---|---|
| Import graph (forward + reverse, single-pass, language-dispatched: TS/Python/Go) | `src/codeguardian/analyzers/imports.py` (`ImportGraph`, `build_import_graph`, `_extract_py_imports`, `_resolve_py`, `_extract_go_imports`, `_resolve_go`, `_go_module_path`) |
| Import-graph cache (sidecar persist + incremental patch across runs) | `src/codeguardian/analyzers/graph_cache.py` (`load_graph`, `save_graph`, `patch_graph`) ; env `CODEGUARDIAN_GRAPH_CACHE` ; wired in `graph/nodes.py` (`_resolve_import_graph`) |
| Test impact + missing coverage (TS + Python + Go conventions) | `src/codeguardian/analyzers/tests.py` |
| API contract / DB-migration / architecture (forbidden imports, layers, cycles) | `analyzers/api.py`, `analyzers/database.py`, `analyzers/architecture.py` |
| Schema breaking-change diff (OpenAPI paths/operations, GraphQL types/fields) | `analyzers/schema.py` (removal-only; runs inside `api_contract_agent`) |
| Types-breaking-change: TS exported types | `analyzers/types.py` · Python public def/class | `analyzers/pytypes.py` (runs inside `types_agent`) |
| Confidence calibration (lower conf for whitespace/comment-only edits) | `src/codeguardian/calibrate.py` (`calibrate_confidence`, in `risk_scoring_agent`) |
| PR-shape (language-agnostic: oversized / deletion-heavy) | `analyzers/pr_shape.py` ; `policy.PrShape` ; `models.Category.pr_shape` |
| Language detection + analyzer support matrix | `src/codeguardian/languages.py` (`detect`, `supports`, `_EXT_TO_LANG`, `_SUPPORT`) |
| "Language-agnostic mode" degraded note | `graph/nodes.py` (`repository_context`) |

### PR / diff / classification
| If you need… | Go to |
|---|---|
| PR diff from git (single `git diff` + split per file) | `src/codeguardian/pr/diff.py` (`compute_diff`, `_split_patches`) |
| File classification (frontend/backend/config/test/db/docs/types) | `src/codeguardian/pr/classify.py` |
| Bounded gitignore-aware repo walk + caps | `src/codeguardian/walk.py` (`iter_repo_files`) ; `policy.Performance` |
| Large-diff cap + truncation note | `graph/nodes.py` (`collect_pr_context`) ; `policy.Performance.max_diff_files` ; `Report.notes` |

### Commands / conversation
| If you need… | Go to |
|---|---|
| `/codeguardian` parser (commands + free-form `ask`) | `src/codeguardian/commands/parser.py` |
| Per-command deterministic handlers + free-form LLM Q&A | `src/codeguardian/commands/handlers.py` (`ask` uses `providers.answer_question`; zero-key intent router `_route_no_provider`; `show` renders hunks+findings) |
| Follow-up Q&A context across asks in a PR | `commands/loop.py` (`load_recent_asks`) → `providers._build_qa_prompt` (`previous_qa`) |
| Plan logic (Outcome: reply / recheck / suppression) | `src/codeguardian/commands/loop.py` (`plan`, `reply_marker`) |
| Permissions (recheck/suppress-blocking gates) | `src/codeguardian/commands/permissions.py` |
| Comment-event parsing + idempotency + artifact retrieval | `src/codeguardian/github/events.py` (`parse_comment_event`) ; `github/client.py` (`latest_reports`, `already_replied`) |

### Memory & history
| If you need… | Go to |
|---|---|
| Memory record (compact, privacy-safe) + signature | `src/codeguardian/memory/record.py` |
| Memory stores (local JSONL / git branch) | `src/codeguardian/memory/store.py` (`compact_records`, retention/compaction) |
| Similarity retrieval (path/category Jaccard) | `src/codeguardian/memory/retrieve.py` |
| Historical-knowledge LangGraph node | `graph/agents.py` (`historical_knowledge_agent`) |
| Memory policy (enable/branch/thresholds/retention) | `src/codeguardian/policy.py` (`Memory`) |

### Policy
| If you need… | Go to |
|---|---|
| Policy schema (modes, thresholds, noise, architecture, performance, pr_shape, model, memory) | `src/codeguardian/policy.py` |
| Glob matching with `**/` semantics | `src/codeguardian/globs.py` (`glob_match`, `matches_any`) |
| Default policy file | `.codeguardian/policy.yml` |
| Opt-in `require_model` / `block_when_missing` | `policy.Model` ; `graph/agents.py` (`recommendation_agent`) |

### Security
| If you need… | Go to |
|---|---|
| Secret redaction (ingress) / untrusted-text fencing / egress secret-scan | `src/codeguardian/security.py` (`redact`, `wrap_untrusted`, `find_secrets`, `safe_output`) |
| Egress chokepoint before posting to GitHub | `github/client.py` (`_scrub`) |
| Prompt-injection corpus + tests | `tests/injection_corpus.py`, `tests/test_phase9_security.py` |
| Supply-chain config (SHA-pinned actions, Dependabot, CodeQL) | `.github/workflows/*.yml`, `.github/dependabot.yml`, `.github/workflows/codeql.yml` |
| Fork-PR safety / `pull_request` vs `pull_request_target` | `doc/INSTALL.md` "Permissions explained" ; `doc/THREAT-MODEL.md` (T4) ; `__main__._can_publish` |

### Release & ops
| If you need… | Go to |
|---|---|
| Reproducible packaging (lockfile install, no live PyPI) | `requirements.lock` ; `action.yml` (install) ; `.github/workflows/ci.yml` (`lockfile` job) |
| Automated release workflow / moving major tag / SemVer | `.github/workflows/release.yml` ; `doc/RELEASING.md` |
| Consumer example workflows | `examples/` (public, private+Groq, required-check, monorepo) |
| Marketplace listing metadata + badges | `action.yml` (`name`/`description`/`branding`) ; `README.md` (badges) |
| Beta plan / FP-FN feedback templates | `.github/ISSUE_TEMPLATE/{false-positive,false-negative,bug,config}.yml` |
| Performance benchmark harness + budgets | `bench/run_bench.py` ; `bench/README.md` |
| How to test (local no-token, sandbox Action, e2e harness) | `doc/TESTING.md` ; `scripts/run-local.sh` ; `e2e/` |

## Key invariants (memorize; don't re-derive)

- Surfaces: GitHub **Check Run `CodeGuardian Risk`** + **one sticky PR comment**.
- Triggers: `pull_request` (opened/reopened/synchronize/ready_for_review) +
  comment events for the conversation loop.
- Trigger token: `/codeguardian` (preferred); `@codeguardian` still accepted
  for back-compat (but pings a stranger — IMPROVEMENT-PLAN P0-5 sunsets it).
- Provider fallback: **Groq → Hugging Face → deterministic** (zero-key must work).
- LLM only synthesizes / answers free-form; deterministic analyzers own the
  evidence. Strict rule #2: no LLM-fabricated findings, ever.
- Languages: JS/TS full; Python dependency+tests+arch; everything else gets the
  language-agnostic baseline (PR-shape + high-risk paths) with an honest note.
- Quiet defaults: advisory mode first, no sticky comment for docs-only or
  no-findings PRs.
- Publishing split: check = merge decision · sticky comment = concise why ·
  artifacts = full evidence.
