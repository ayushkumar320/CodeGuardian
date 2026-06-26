# Phase 1: GitHub Actions PR Checker MVP

## Objective

Build the first working CodeGuardian PR checker that runs inside GitHub Actions and publishes a `CodeGuardian Risk` check to the pull request merge area.

## Scope

Included:

- GitHub Actions workflow.
- PR diff collection.
- Changed file classification.
- Basic JavaScript and TypeScript analysis.
- Lightweight dependency scanning.
- Basic test recommendations.
- Risk report generation.
- GitHub Check output.
- Sticky PR comment.

Excluded:

- Hosted dashboard.
- Persistent external database.
- Full graph database.
- Deep semantic analysis.
- Enterprise installation flow.

## Workflow

```mermaid
flowchart TD
  A["pull_request event"] --> B["Checkout repository"]
  B --> C["Fetch base branch"]
  C --> D["Compute diff"]
  D --> E["Classify changed files"]
  E --> F["Scan imports and risky paths"]
  F --> G["Recommend tests"]
  G --> H["Generate risk report"]
  H --> I["Write GitHub check summary"]
  H --> J["Update sticky PR comment"]
```

## Required Inputs

- GitHub event payload.
- Base SHA.
- Head SHA.
- Changed files.
- Unified diff patches.
- Repository file tree.
- Optional `.codeguardian/policy.yml`.
- Optional `GROQ_API_KEY`.
- Optional `HF_TOKEN`.

## Outputs

- `codeguardian-report.json`
- `codeguardian-report.md`
- GitHub check summary.
- Sticky PR comment.
- Exit code that can pass or fail required check.

## Finding Schema

```text
finding
- id
- category
- severity
- confidence
- title
- summary
- evidence_files
- recommended_actions
- blocking
```

## Senior Developer Prompt

```text
You are implementing Phase 1 of CodeGuardian AI.

Build a GitHub Actions PR checker that:
- Runs on pull_request opened, synchronize, reopened, and ready_for_review.
- Checks out the repo and fetches the base branch.
- Computes changed files and patches.
- Classifies files by risk category.
- Scans JS/TS imports for likely dependency impact.
- Recommends tests using file naming and import heuristics.
- Generates a risk score.
- Publishes a GitHub check summary.
- Creates or updates one sticky PR comment.
- Uploads report JSON and Markdown artifacts.
- Works without LLM keys.

Return:
1. File structure.
2. Implementation steps.
3. Data schemas.
4. Error handling.
5. Test fixtures.
6. Acceptance criteria.
```

## Product Manager Prompt

```text
You are reviewing the Phase 1 MVP.

Given a sample PR and CodeGuardian output, decide whether the check is useful.

Evaluate:
1. Is the score understandable?
2. Are affected areas clear?
3. Are recommendations actionable?
4. Is the comment too long?
5. Would a developer trust this enough to act?

Return:
- Product verdict
- Copy improvements
- Missing information
- Noise concerns
- Launch readiness
```

## User Prompt

```text
@codeguardian explain

Explain the current risk score.
Tell me:
- What changed
- Why it matters
- Which tests I should run
- Whether this blocks merge
```

## Acceptance Criteria

- The Action runs successfully on a sample PR.
- The check appears in the GitHub PR merge area.
- The sticky comment updates in place.
- Docs-only changes produce low-risk output.
- High-risk path changes produce visible warnings.
- The report artifact is uploaded.
- No LLM key is required for baseline operation.

