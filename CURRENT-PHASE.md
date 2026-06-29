# CURRENT PHASE

Quick reference for where the build is. Update this when a phase ships.

- **Branch model:** solo dev — commit directly to `main`.
- **Stack (committed):** Python + LangGraph + Pydantic. Overrides the docs'
  TypeScript recommendation.
- **Active plan:** [doc/build/README.md](doc/build/README.md) — Production &
  Shipment (v1.0). MVP build record archived under
  [doc/build/archive/](doc/build/archive/).

## MVP (Phases 0–6) — ✅ DELIVERED

PR checker + LangGraph agents + `/codeguardian` loop + deep analyzers +
GitHub-native memory + packaging. Code under `src/codeguardian/`; 55 tests green;
runs zero-key deterministic. Detail: [archive/](doc/build/archive/).

## Production track (Phases 7–12) — toward v1.0 GA

| Phase | What | State |
|-------|------|-------|
| **P7** | **Real-PR validation & live-API hardening** | **🟡 PARTIAL — public deterministic path validated live; remainder is a pre-release gate (see below)** |
| P8 | Robustness & observability (never-crash, retries, job summary) | ✅ DONE — all acceptance criteria met |
| P9 | Security & supply-chain hardening (fork-PR safety, injection corpus) | ✅ DONE — code + CI + docs landed; SBOM/signed releases deferred to P11 |
| P10 | Performance & scale (shared import graph, memory compaction) | ✅ DONE — all acceptance criteria met (minor wall-clock soft-timeout deferred) |
| P11 | Release engineering & Marketplace (reproducible packaging, automation) | ✅ DONE — code-side complete; Marketplace UI publish is a one-time manual step on first release |
| **P12** | **Beta, tuning & v1.0 GA** | **▶ NEXT** |

## 🟡 Phase 7 — partially validated; remainder is a pre-release gate

> **Status (as of June 28, 2026):** live sandbox validation was started on a real
> public repo (`ayushkumar320/clawcode-test`). The **public, zero-key
> deterministic path is proven**: the Action runs clean, the `CodeGuardian Risk`
> check posts to the merge box with its rich summary, report artifacts upload, the
> quiet-by-default path behaves correctly, and the comment command loop reaches the
> bot and replies. **Two live-only defects were found and fixed** in the process:
>
> - **pip-cache crash on non-Python consumer repos** — `setup-python cache: pip`
>   keyed off a `requirements.txt`/`pyproject.toml` in the consumer repo and aborted
>   the run. Removed. (`action.yml`; `tests/test_phase7_action_metadata.py`)
> - **`@codeguardian` username collision** — the GitHub UI auto-linked the mention
>   to an unrelated account, notifying a stranger on every command. Trigger is now
>   **`/codeguardian`** (slash form); `@codeguardian` still accepted for back-compat.
>   (`commands/parser.py`; `tests/test_phase7_slash_trigger.py`)
>
> **Decision:** the core path is proven, so the team is moving on to P10. The
> remaining P7 validation is **deferred to a pre-release gate** (run before P11
> release / P12 GA), not skipped.
>
> **Pre-release gate — must run before GA (do NOT mark P7 ✅ until then):**
> - **findings PR** — confirm a non-zero-risk PR posts the sticky comment, updates
>   it in place (upsert, no duplicate), and emits annotations.
> - **command loop on `/codeguardian`** — `explain` / `tests` / `recheck` reply once.
> - **private repo** behavior.
> - **fork PR safety** — read-only token, no write attempts, no crash (highest-risk
>   gate; required by strict rules).
>   Use [doc/build/phase-7-runbook.md](doc/build/phase-7-runbook.md) +
>   `e2e/validate_sandbox.py` (workflow_dispatch runner ready).

Prove the Action against the live GitHub API before release.

- **Read first:** CONTEXT-GRAPH.md → then ROOT, BIDX, P7.
- **Goal:** install on a sandbox repo; exercise low-risk/high-risk/comment-command
  /recheck/ignore/compare/history on public, private, and **fork** PRs; fix
  live-API gaps (comment pagination, artifact download, recheck head fetch, memory
  branch push, fork read-only token + no secrets, rate limits, large diffs); add
  an `e2e/` harness.
- **Keep working:** zero-key deterministic path, quiet defaults, evidence-cited.

### Repo-side groundwork completed

- check run update-or-create path added
- sticky comment and reply pagination covered by tests
- artifact history scan paginates across multiple pages
- fork PRs skip forbidden writes and degrade safely
- `recheck` fetches the PR head repo/ref more reliably
- sandbox validator harness + workflow-dispatch runner added

### Remaining Phase 7 gate

Run the real sandbox validation described in
[doc/build/phase-7-runbook.md](doc/build/phase-7-runbook.md). Phase 7 should not
be marked complete until public, private, and fork PR behavior is validated on
the live GitHub API.

## Phase 8 — robustness & observability ✅ DONE

Phase 7's live sandbox validation is deferred (to be run later); Phase 8 was
completed in parallel. Acceptance criteria all met:

- **Failure boundary**: any uncaught error → neutral check, error in artifact,
  exit 0 (`__main__.run`). Per-analyzer isolation surfaces `Report.errors[]` +
  `degraded`. Provider timeout falls through to deterministic (tested); GitHub
  publish failures are caught and never crash.
- **Retry+timeout HTTP helper** (`src/codeguardian/http.py`): bounded exponential
  backoff with jitter, honors `Retry-After`, retries only transient
  (timeout/conn/429/5xx). All network calls routed through it (no raw
  `requests.*` left in client/providers).
- **Leveled secret-safe logging** (`src/codeguardian/log.py`): `CODEGUARDIAN_DEBUG`
  flips to DEBUG; every message passes through secret redaction (tested).
- **Job summary** writer to `$GITHUB_STEP_SUMMARY` on every analysis path.
- **`python -m codeguardian --selfcheck`** (`src/codeguardian/selfcheck.py`):
  pass/fail per dependency (git, repo env, token reachability, provider).
- **Degraded badge** surfaces in check title, check summary, and sticky comment
  (`report.py`).

Coverage: 76 tests green.

## Phase 9 — security & supply-chain hardening ✅ DONE

Landed:

- **Egress secret-scan**: `security.safe_output`/`find_secrets` + a `_scrub`
  chokepoint in `github/client.py` redact any secret-shaped content from every
  check/comment/reply before it is posted (defense-in-depth on top of ingress
  redaction).
- **Prompt-injection corpus + tests** (`tests/injection_corpus.py`,
  `tests/test_phase9_security.py`): hostile payloads are proven inert (fenced +
  redacted), and the schema rejects evidence-free findings — a model can't
  fabricate one.
- **Fork-PR safety**: documented `pull_request` vs `pull_request_target` and the
  least-privilege `permissions:` table in `INSTALL.md`; behavior covered by tests
  (`_can_publish`).
- **Supply chain**: third-party actions SHA-pinned across all workflows;
  `.github/dependabot.yml` (actions + pip); `.github/workflows/codeql.yml`.
- **Docs**: `SECURITY.md` (disclosure policy + posture) and `THREAT-MODEL.md`
  (T1–T9), linked from the README.

Deferred to **P11** (release engineering, where the release workflow lives):
**SBOM generation** and **signed releases/tags** — these are release-time
artifacts and belong with reproducible packaging.

Plus (post-Phase-9 hardening): opt-in `policy.model.require_model` /
`block_when_missing` to guarantee the LLM summary ran; CodeQL PR permissions
fixed (`actions: read` + skip Dependabot read-only-token runs); Dependabot
updates grouped into a single PR.

Coverage: 93 tests green.

## Phase 10 — performance & scale ✅ DONE

All acceptance criteria met:

- **Import graph built once per run** and shared across analyzers (was 4-5 full
  repo walks; architecture alone built it twice). `imports.build_import_graph`
  builds forward + reverse in one pass; `repository_context` builds it once and
  passes it through state. Regression test asserts exactly one build per run.
- **Bounded, gitignore-aware walk** (`walk.iter_repo_files`): prefers
  `git ls-files`, skips vendored/build/minified/lockfiles, caps file count +
  per-file size. Configurable via `policy.performance`.
- **Batched diff**: one `git diff` split per file instead of one `git diff` per
  changed file.
- **Large-diff cap**: `policy.performance.max_diff_files` (default 300) truncates
  to top-N by size with a user-visible note (`Report.notes`).
- **Memory retention/compaction**: `memory.compact_records` bounds the branch by
  `policy.memory.max_records` (500) + `retention_days` (180).
- **Benchmark harness** (`bench/`): baseline + regression budgets (1k ~0.06s,
  10k ~0.39s end-to-end, deterministic).

Deferred (minor, not in acceptance criteria): a wall-clock soft timeout that
publishes a partial result mid-run — the large-diff cap already bounds the
dominant cost, so this is a nice-to-have for a later pass.

Coverage: 114 tests green.

## Phase 11 — release engineering & Marketplace ✅ DONE

Code-side complete; the only remaining step is a **one-time** Marketplace publish
from the GitHub Release UI on the first tag (`v0.1.0`).

- **Reproducible packaging**: `requirements.lock` (pip-tools, 35 pinned deps).
  `action.yml` installs from the lockfile + the package with `--no-deps`, so no
  live PyPI resolution at run time. New CI `lockfile` job keeps the lock in sync
  with `pyproject.toml`.
- **Automated release workflow** (`.github/workflows/release.yml`): tag push →
  tests → version-tag-match check → CHANGELOG-driven release notes → `gh release
  create` → move the major (`v0`) alias.
- **Consumer examples** (`examples/`): public, private+Groq, required-check,
  monorepo, each ready to copy as `.github/workflows/codeguardian.yml`.
- **Listing polish**: README CI + CodeQL badges; `action.yml` `name`/`description`/
  `branding`/`author` already in place.
- **RELEASING.md** rewritten to reflect the automation.

Deferred to first release / P9 carry-over: **SBOM generation** and **signed
releases**. Both are release-workflow additions and can land alongside the first
tag without re-cutting work here.

Coverage: 116 tests green.

## Open operational items (not new phases)

- `main` is in sync with `origin`; supply-chain automation (grouped Dependabot +
  CodeQL) is live and green.
- Cut `v0.1.0` once P7 validates live behavior (see RELEASING.md) — note: the
  first GA tag is **v1.0** at the end of P12.
