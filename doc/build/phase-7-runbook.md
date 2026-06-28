# Phase 7 Runbook

Practical execution guide for **Phase 7: Real-PR Validation & End-to-End
Hardening**.

## Current Local Status

The repo-side groundwork is in place:

- sticky comment lookup paginates across large PR threads
- command replies dedupe by comment marker
- report artifact history lookup supports multi-page artifact scans
- fork-originated PRs skip write attempts and degrade safely
- `recheck` fetches from the actual PR head repo/ref when available
- a workflow-dispatch sandbox validator exists

What is **not** proven yet is the live GitHub behavior on a real sandbox
repository. That final proof is the last Phase 7 gate.

## Sandbox Repositories

Prepare:

1. one public sandbox repo
2. one private sandbox repo
3. one fork of the public sandbox repo for fork-PR validation

Install the CodeGuardian workflow on the public and private sandbox repos.

## Required Test PRs

Create and keep open fixture PRs for:

1. docs-only / low-risk change
2. high-risk change with API + migration impact
3. PR with more than 100 comments to force sticky-comment pagination
4. fork-originated PR
5. command-loop PR where `@codeguardian tests`, `explain`, `compare`, `history`,
   `recheck`, and `ignore` can all be exercised

## Validation Commands

Run the workflow-dispatch validator:

```bash
GITHUB_TOKEN=... python e2e/validate_sandbox.py verify-pr \
  --repo owner/name --pr 12 --expect-sticky --expect-artifact
```

Validate command handling:

```bash
GITHUB_TOKEN=... python e2e/validate_sandbox.py send-command \
  --repo owner/name --pr 12 --body "@codeguardian tests" --expect-single-reply
```

Or run the repository workflow:

- `.github/workflows/phase7-sandbox-validate.yml`

## Acceptance Checklist

- `CodeGuardian Risk` check appears on the PR merge page
- sticky summary comment is updated in place
- report artifacts are uploaded and readable
- `explain`, `tests`, `why blocked`, `compare`, and history replies work
- `recheck` re-analyzes the latest PR head commit
- fork PRs complete without attempted writes or crashes
- no duplicate sticky comments or duplicate command replies

## Defect Log Template

Capture each live-API gap with:

- scenario
- expected behavior
- actual behavior
- GitHub event type
- repo visibility: public/private/fork
- fix commit
- regression test added

## Exit Criteria

Phase 7 is ready to close when:

- sandbox validation has been executed on real public, private, and fork PRs
- discovered defects are fixed
- the validator/runbook are updated with any learned limitations
- docs clearly describe fork-PR limitations and safe degradation
