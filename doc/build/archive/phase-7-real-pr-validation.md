# Phase 7: Real-PR Validation & End-to-End Hardening

## Objective

Prove CodeGuardian works against the **real GitHub Actions environment and API**,
not just local fixtures. Find and fix the gaps that only appear on live PRs before
investing in deeper hardening.

## Why first

Everything in the MVP was validated against synthetic git repos and unit tests.
Live behavior (check creation, comment upsert pagination, artifact download,
`recheck` head fetch, memory-branch push, fork token limits) is currently
unproven. Hardening the wrong things is wasteful until real behavior is observed.

## Scope

Included:

- A sandbox repository with the workflow installed; scripted test PRs covering:
  low-risk/docs-only, high-risk (migration + API), comment commands, recheck,
  ignore, compare, history.
- Public, **private**, and **fork** PR scenarios.
- Live-API edge cases: pagination, rate limits (403/secondary), large/truncated
  diffs, draft PRs, force-pushes, concurrent runs (concurrency cancel), missing
  permissions.
- Fork-PR reality: `pull_request` from a fork has a **read-only token and no
  secrets** — confirm graceful degradation (deterministic, no failed writes).

Excluded:

- New analyzers or product features (frozen for this phase).

## Deliverables

- A documented manual/automated E2E run on the sandbox repo with screenshots of
  each surface (check, sticky comment, artifact, command replies).
- A defect list with fixes for every live-API gap found.
- An `e2e/` harness (script or workflow) that opens fixture PRs and asserts the
  check conclusion + comment presence via the API.
- A "known limitations on fork PRs" note in INSTALL/TROUBLESHOOTING.

## Senior Developer Prompt

```text
You are hardening CodeGuardian against the live GitHub API (Phase 7).
Read CONTEXT-GRAPH.md, then ROOT, PLAN, the archived P1/P3, and the code map.

Validate and fix on a real sandbox repo:
- Check run create/update near the merge box.
- Sticky comment upsert across >100 comments (pagination), no duplicates.
- Report artifact upload + cross-run download for compare/history.
- recheck: fetch PR head ref and re-analyze correctly.
- Memory branch push under real GITHUB_TOKEN permissions (worktree path).
- Fork PRs: read-only token, no secrets -> deterministic, no failed writes,
  no crash.
- Rate-limit / 403 / large-diff handling.

Return: defect list, fixes, an e2e harness, and updated docs.
```

## Acceptance Criteria

- A live PR on the sandbox repo shows the `CodeGuardian Risk` check and a correct
  sticky comment.
- `explain`, `tests`, `why blocked`, `recheck`, `compare`, `ignore`, and history
  all work against the real API.
- Fork PRs run in deterministic mode without errors and without attempting writes
  that the token can't perform.
- No duplicate comments under heavy comment volume.
- All discovered defects are fixed with regression coverage.
