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

## Scripted Validation

The first harness script is:

```bash
GITHUB_TOKEN=... python e2e/validate_sandbox.py verify-pr \
  --repo owner/name --pr 12 --expect-sticky
```

It verifies:

- check run exists for the PR head SHA
- sticky summary comment exists and is not duplicated
- report artifacts are present

You can also test command replies:

```bash
GITHUB_TOKEN=... python e2e/validate_sandbox.py send-command \
  --repo owner/name --pr 12 --body "@codeguardian tests"
```

## Next Step

Use this script against the sandbox repositories, record the failures that only
show up on the real API, and turn those into Phase 7 fixes plus regression
tests.
