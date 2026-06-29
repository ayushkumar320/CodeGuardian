# Changelog

All notable changes to CodeGuardian AI. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Partial Python support** (Phase 12, in-scope expansion):
  - `pr/classify.py` routes `.py` to `backend` and recognizes `test_*.py` /
    `*_test.py` test files.
  - `analyzers/imports.py` parses `import x.y` and `from .pkg import z`,
    resolves relative imports against the importer's package and absolute
    imports against repo root + `src/` layouts; the import graph now spans
    JS/TS *and* Python in a single pass.
  - `analyzers/tests.py` suggests `test_*.py` / `*_test.py` / `tests/test_*.py`
    candidates for missing coverage, and detects test-impact via the Python
    import graph the same way it did for JS/TS.
  - Architecture findings (layer direction, circular deps) come along for free
    since they sit on the import graph.
  - Out of scope for now (kept JS/TS-only): types-breaking-change, API contract,
    Prisma/ORM migration risk. Tracked in `doc/POST-V1-ROADMAP.md`.

## [0.2.0] - 2026-06-30

First tagged release. The MVP (Phases 0–6) was finished as `0.1.0` but never
published; `0.2.0` is the initial real Marketplace-eligible cut and bundles all
Production-track work since: live-API hardening from the public-PR validation
(Phase 7), never-crash + observability (Phase 8), security & supply-chain
hardening (Phase 9), the performance pass (Phase 10), reproducible packaging +
automated releases (Phase 11), and the beta/feedback scaffolding for v1.0
(Phase 12). Consumer pins: `@v0.2.0` (exact) or `@v0` (moves with non-breaking
updates).

### Added
- **Beta scaffolding for v1.0** (Phase 12):
  - Issue templates for [false-positive](.github/ISSUE_TEMPLATE/false-positive.yml),
    [false-negative](.github/ISSUE_TEMPLATE/false-negative.yml), and
    [bug](.github/ISSUE_TEMPLATE/bug.yml); each auto-labelled `needs-triage` so
    the feedback loop can be tracked.
  - [`SUPPORT.md`](SUPPORT.md) documents the triage process and bookkeeping for
    beta false-positive / false-negative reports.
  - [`doc/GA-CHECKLIST.md`](doc/GA-CHECKLIST.md) is the step-by-step sequence for
    cutting v1.0, including the deferred Phase-7 pre-release gate.
  - [`doc/POST-V1-ROADMAP.md`](doc/POST-V1-ROADMAP.md) records what v1.0 is
    deliberately *not* doing and where contributors can pick up post-GA.
- **Reproducible packaging** (Phase 11): `requirements.lock` pins every transitive
  dependency. The Action installs from the lockfile and then installs its own
  package with `--no-deps`, so there is no live PyPI resolution at run time. CI's
  new `lockfile` job verifies the lock stays in sync with `pyproject.toml`.
- **Automated release workflow** (Phase 11):
  [`.github/workflows/release.yml`](.github/workflows/release.yml) — pushing a
  `vX.Y.Z` tag runs tests, extracts the matching CHANGELOG section as notes,
  creates the GitHub Release, and moves the major (`v0`) alias consumers pin to.
- **Consumer examples** (Phase 11): [`examples/`](examples/README.md) — ready-to-copy
  workflows for public, private (with Groq), required-check, and monorepo setups.
- README CI + CodeQL badges.

### Performance
- **Import graph built once per run** (Phase 10): the dependency, test, types, and
  architecture analyzers previously each rebuilt the JS/TS import graph (4-5 full
  repo walks per run, architecture twice on its own). It is now built a single
  time in `repository_context` and shared via graph state. New
  `imports.build_import_graph` constructs forward + reverse maps in one pass.
- **Bounded, gitignore-aware repo walk** (Phase 10): new `walk.iter_repo_files`
  centralizes file enumeration — prefers `git ls-files` (respects `.gitignore`),
  skips vendored/build/minified/lockfiles, and caps file count + per-file size.
  The import graph and `repository_context` both use it. Caps are configurable via
  the new `policy.performance` (`max_files`, `max_file_bytes`).
- **Batched diff** (Phase 10): the PR diff now runs a single `git diff` and splits
  the unified output per file, instead of one `git diff -- <path>` per changed
  file (was O(files) git invocations).
- **Large-diff cap** (Phase 10): PRs touching more than `policy.performance.
  max_diff_files` (default 300) are analyzed top-N by change size, with a clear
  "diff too large, analyzed top N" note surfaced on the check and sticky comment
  (new `Report.notes`).
- **Memory retention/compaction** (Phase 10): the memory branch is now bounded —
  `memory.compact_records` drops records older than `policy.memory.retention_days`
  (default 180) and keeps the `policy.memory.max_records` (default 500) most
  recent. Applied on every append in both the local and git-branch stores.
- **Benchmark harness** (Phase 10): `bench/run_bench.py` generates synthetic repos
  (1k/10k/50k files) and times the import-graph build and a full run; `bench/
  README.md` records the baseline and the regression budgets.

### Changed
- **Command trigger is now `/codeguardian`** (was `@codeguardian`). The `@` form
  is auto-linked by the GitHub UI to whatever account owns that username,
  notifying an unrelated person on every command. The slash form has no such
  collision. `@codeguardian` is still accepted for back-compat. Found during
  Phase 7 live sandbox validation.

### Fixed
- **Action no longer fails on non-Python consumer repos**: removed the
  `setup-python` pip cache, which keyed off a `requirements.txt`/`pyproject.toml`
  in the consumer repo and aborted the run when absent. Found during Phase 7.

## [0.1.0] - 2026-06-27

First MVP — a GitHub-native, deterministic-first pre-merge risk checker
(Phases 0–6). Runs entirely in GitHub Actions; works with zero model keys.

### Added
- **Product contract** (Phase 0): user journey, risk rubric, blocking modes,
  sticky-comment / check copy, command set, acceptance criteria.
- **PR checker MVP** (Phase 1): diff collection, file classification, import
  blast-radius + missing-test analyzers, deterministic risk score, GitHub check,
  idempotent sticky comment, JSON/MD artifacts.
- **LangGraph agentic workflow** (Phase 2): parallel domain agents fanning into
  risk scoring; provider router Groq → Hugging Face → deterministic with model
  output schema validation.
- **`@codeguardian` conversation loop** (Phase 3): `help`, `explain`, `tests`,
  `why blocked`, `compare`, `summary`, `recheck`, `ignore`; maintainer
  permissions; reply idempotency.
- **Deep analyzers + policy** (Phase 4): shared-type breakage, Prisma/SQL
  destructive-change detection, API + OpenAPI/GraphQL drift, layer-direction and
  circular-dependency rules, import-graph test impact; policy `layers`,
  `test_suite_mappings`, `service_owners`, `ignored_findings`.
- **GitHub-native memory** (Phase 5): compact records on a `codeguardian-memory`
  branch, similarity retrieval, "has this happened before?" history.
- **Packaging** (Phase 6): reusable Action metadata with inputs, example
  workflow, starter policy, install + troubleshooting guides, CI workflow.

### Security
- Untrusted-repo-text fencing and secret redaction before any model call; every
  finding requires analyzer evidence; the LLM never sets the score.
