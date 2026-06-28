# Phase 7 E2E Harness

This folder is the starting point for the real-PR validation work in Phase 7.

## Goal

Exercise CodeGuardian against a live sandbox repository and verify the GitHub
surfaces that local unit tests cannot prove:

- `CodeGuardian Risk` check creation/update
- sticky PR comment upsert
- report artifact upload
- `@codeguardian` command replies
- `recheck`, `compare`, `ignore`, and history flows
- fork PR graceful degradation

## Suggested Sandbox Setup

1. Create a public sandbox repository for normal and fork PR cases.
2. Create a private sandbox repository for private-repo behavior.
3. Install the workflow from this repo onto both.
4. Seed fixture branches/PRs for:
   - docs-only change
   - high-risk migration + API change
   - PR with more than 100 existing comments
   - fork-originated PR

## Expected Assertions

- the check appears on the merge page
- the sticky comment is updated in place instead of duplicated
- artifacts contain `codeguardian-report.json` and `.md`
- command replies are posted once per triggering comment
- fork PRs complete without crashing and without attempting comment/check writes

## Next Step

Add a scripted runner here once the sandbox repositories and auth method are
chosen. The active Phase 7 deliverable is the harness plus regression fixes for
every live-API gap it exposes.
