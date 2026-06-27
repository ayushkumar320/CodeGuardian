# Changelog

All notable changes to CodeGuardian AI. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
