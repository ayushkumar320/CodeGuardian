# CodeGuardian AI

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

Add CodeGuardian to a repo's PRs (full guide: [INSTALL.md](INSTALL.md)):

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
> `scripts/run-local.sh /path/to/repo`. See [TESTING.md](TESTING.md).

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
- Optional `@codeguardian` commands keep follow-up inside the PR thread.

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

## Scope Today

In scope:

- GitHub Action workflow install
- `CodeGuardian Risk` check
- one sticky PR summary comment
- `@codeguardian` PR commands
- deterministic-first analysis with optional model summarization
- GitHub-native memory via artifacts and branch-backed storage

Out of scope:

- hosted dashboard
- billing
- separate web app
- team analytics UI
- SaaS control plane

## Docs

- [INSTALL.md](INSTALL.md) — install and configure the Action
- [TESTING.md](TESTING.md) — **run it locally with no token**, on a sandbox repo, or via the e2e harness
- [SECURITY.md](SECURITY.md) — security policy, vulnerability reporting, hardening
- [THREAT-MODEL.md](THREAT-MODEL.md) — threats, mitigations, and residual risks
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — common setup and runtime issues
- [doc/GitHub-PR-User-Flowmap.md](doc/GitHub-PR-User-Flowmap.md) — merge-page product behavior
- [doc/build/README.md](doc/build/README.md) — active production roadmap to v1.0
- [doc/Workflow-Improvements.md](doc/Workflow-Improvements.md) — workflow and report refinements
- [doc/CodeGuardian-AI-Blueprint.md](doc/CodeGuardian-AI-Blueprint.md) — deferred long-term blueprint, not the current product surface

## Current Status

Working toward a trusted **v1.0** GitHub Action focused on the PR merge page.

- **MVP (phases 0–6): delivered** — deterministic PR analysis, LangGraph agents,
  `@codeguardian` loop, GitHub-native memory.
- **Robustness & observability (phase 8): done** — never-crash boundary, retries
  with timeouts, secret-safe logging, job summary, `--selfcheck`.
- **Security & supply-chain (phase 9): done** — egress secret-scan, prompt-injection
  corpus, fork-PR safety, SHA-pinned actions, CodeQL, Dependabot. See
  [SECURITY.md](SECURITY.md).
- **In flight:** live real-PR validation on a sandbox repo (phase 7), then
  performance, release engineering, and beta to v1.0.

See [CURRENT-PHASE.md](CURRENT-PHASE.md) for the live status and
[doc/build/README.md](doc/build/README.md) for the full roadmap.
