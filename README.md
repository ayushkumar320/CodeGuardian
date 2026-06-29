# CodeGuardian AI

[![CI](https://github.com/ayushkumar320/CodeGuardian/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ayushkumar320/CodeGuardian/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ayushkumar320/CodeGuardian/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/ayushkumar320/CodeGuardian/actions/workflows/codeql.yml)

**Know what breaks before you merge.**

CodeGuardian AI is a **GitHub-Action-native pre-merge risk checker**. It runs on
pull requests, analyzes what changed, and publishes the result directly on the
GitHub PR merge page.

The product is intentionally centered on two surfaces only:

- the `CodeGuardian Risk` check near the merge box
- one sticky PR summary comment for concise explanation

Every pull request should answer:

- What could this change break?
- Which services, APIs, files, and tests are affected?
- Is this safe to merge?
- What should the developer do next?

This repository contains the working product and the docs for that GitHub-first
experience. The MVP implementation (phases 0–6) is complete: a GitHub Action
that runs deterministic PR risk analysis orchestrated by LangGraph, with zero
model keys required.

## Quick Start

Add CodeGuardian to a repo's PRs (full guide: [INSTALL.md](doc/INSTALL.md)):

```yaml
# .github/workflows/codeguardian.yml
name: CodeGuardian Risk
on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
  issue_comment:
    types: [created]
permissions:
  checks: write
  pull-requests: write
  issues: write
  contents: read          # use `write` only if you enable cross-PR memory
  actions: read
jobs:
  risk:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # required: full history for the diff
      - uses: your-org/CodeGuardian@v0
        # No secrets needed. The two inputs below are OPTIONAL — without them
        # CodeGuardian runs fully in deterministic mode.
        with:
          groq-api-key: ${{ secrets.GROQ_API_KEY }}   # optional
          hf-token: ${{ secrets.HF_TOKEN }}           # optional
```

**No API keys are required.** Provider fallback is
**Groq → Hugging Face → deterministic**, and the deterministic path is the
baseline: it produces the full score, findings, and recommendations with **zero
model keys**. A model, if configured, only rephrases the summary prose — it can
never set the score or invent a finding. Groq/HF are an optional nicety, not a
dependency.

> **Want to try it before installing anything?** You can run the exact same
> analysis on any local repo with no token and no PR:
> `scripts/run-local.sh /path/to/repo`. See [TESTING.md](doc/TESTING.md).

## Product

CodeGuardian focuses on one job: help the developer decide whether a pull
request is safe to merge.

It should feel less like a generic AI reviewer and more like a staff engineer
quietly answering the questions that matter:

- Does this violate an architecture boundary?
- Could this API change break consumers?
- Did this migration remove or alter data unsafely?
- Which tests actually matter for this PR?
- Has a similar change caused an incident before?
- Should this merge be blocked, warned, or allowed?

## PR Merge-Page Workflow

```mermaid
flowchart TD
  A["Developer opens or updates PR"] --> B["GitHub Action starts"]
  B --> C["Fetch diff, base SHA, head SHA"]
  C --> D["Run deterministic analyzers"]
  D --> E["Optionally synthesize summary with model provider"]
  E --> F["Compute risk score"]
  F --> G["Publish CodeGuardian Risk check"]
  G --> H["Post or update sticky PR comment"]
  H --> I{"Policy threshold exceeded?"}
  I -->|Yes| J["Require action or fail check"]
  I -->|No| K["Mark success or neutral"]
```

The merge decision should be understandable without leaving GitHub:

- `CodeGuardian Risk` tells the developer whether the PR looks safe to merge.
- The sticky comment answers why, with concise findings and next actions.
- The artifact contains the full evidence when someone needs depth.
- Optional `/codeguardian` commands keep follow-up inside the PR thread.

## How It Works

CodeGuardian builds its result from deterministic evidence first, then uses a
model only to summarize and explain. The Action must still work with no model
keys at all.

```mermaid
flowchart TD
  DIFF["PR diff"] --> ANALYZERS["Deterministic analyzers"]
  ANALYZERS --> FINDINGS["Evidence-backed findings"]
  FINDINGS --> SCORE["Risk score"]
  SCORE --> CHECK["Check conclusion"]
  FINDINGS --> SUMMARY["Sticky comment summary"]
  FINDINGS --> ARTIFACT["Full report artifact"]
```

Today the Action is strongest on JS / TS / Node / React / Next repositories and
focuses on:

- dependency blast radius
- API contract risk
- database and migration risk
- architecture boundary violations
- missing or mismatched test coverage
- historical similarity from GitHub-native memory

## Language support

CodeGuardian runs on **any repo** — but what it can *say* about your code
depends on the language. Per strict rule #2 (deterministic-first), each
analyzer is real parsing work; we don't let the LLM fabricate findings for
languages we don't have a parser for.

| Language     | Dependency / blast-radius | Tests (missing + impacted) | Architecture (layers / cycles) | Types-breaking | API contract | DB migrations |
|--------------|:-:|:-:|:-:|:-:|:-:|:-:|
| TypeScript / JavaScript | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (Prisma) |
| Python                  | ✅ | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| Anything else (Go, Rust, Java, Ruby, …) | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

**Every repo, every language**, you also get the language-agnostic baseline:

- `high-risk path` edits (e.g. anything under `**/auth/**`, `**/billing/**`)
- `pr_shape` findings: oversized PRs, deletion-heavy changes
- An **honest "language-agnostic mode" note** on the check + sticky comment
  when a PR touches only languages we don't deeply analyze, so a low score
  isn't misread as "all clear"

Per-language analyzer parity (types/API/DB for Python, Go support, etc.) is in
[POST-V1-ROADMAP](doc/POST-V1-ROADMAP.md), explicitly *not* in v1.0.

## Scope Today

In scope:

- GitHub Action workflow install
- `CodeGuardian Risk` check
- one sticky PR summary comment
- `/codeguardian` PR commands
- deterministic-first analysis with optional model summarization
- GitHub-native memory via artifacts and branch-backed storage
- **language-agnostic baseline** so the Action is useful on any repo

Out of scope:

- hosted dashboard
- billing
- separate web app
- team analytics UI
- SaaS control plane

## Docs

- [INSTALL.md](doc/INSTALL.md) — install and configure the Action
- [TESTING.md](doc/TESTING.md) — **run it locally with no token**, on a sandbox repo, or via the e2e harness
- [SECURITY.md](SECURITY.md) — security policy, vulnerability reporting, hardening
- [THREAT-MODEL.md](doc/THREAT-MODEL.md) — threats, mitigations, and residual risks
- [TROUBLESHOOTING.md](doc/TROUBLESHOOTING.md) — common setup and runtime issues
- [doc/GitHub-PR-User-Flowmap.md](doc/GitHub-PR-User-Flowmap.md) — merge-page product behavior
- [doc/IMPROVEMENT-PLAN.md](doc/IMPROVEMENT-PLAN.md) — active P0/P1/P2 backlog
- [doc/POST-V1-ROADMAP.md](doc/POST-V1-ROADMAP.md) — what v1.0 is deliberately *not* doing
- [doc/GA-CHECKLIST.md](doc/GA-CHECKLIST.md) — v1.0 cut sequence
- [doc/CodeGuardian-AI-Blueprint.md](doc/CodeGuardian-AI-Blueprint.md) — original long-term blueprint (historical)
- [doc/build/archive/](doc/build/archive/) — historical phase build docs (0–12, delivered)

## Current Status

All build phases (0–12) are delivered. Forward work is prioritized in
[doc/IMPROVEMENT-PLAN.md](doc/IMPROVEMENT-PLAN.md); the v1.0 GA sequence
(beta runs, the tag push, Marketplace publish) is in
[doc/GA-CHECKLIST.md](doc/GA-CHECKLIST.md).
