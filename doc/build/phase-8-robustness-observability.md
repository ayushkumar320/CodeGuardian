# Phase 8: Robustness & Observability

## Objective

Make the Action **impossible to crash** and easy to debug. A failure in any
analyzer, model call, or GitHub API call must degrade gracefully and be reported,
never abort the run with an opaque stack trace.

## Scope

Included:

- A top-level failure boundary: unexpected errors produce a neutral check with a
  "CodeGuardian hit an internal error" message + the error in the artifact, and a
  zero exit code (never block merge on our own bug).
- Per-analyzer isolation already exists in the agent layer — extend it with an
  explicit `errors[]` surface in the report and a visible "degraded run" note.
- Retries with exponential backoff + jitter and explicit timeouts on every
  network call (GitHub API, Groq, HF).
- Structured, leveled logging; `CODEGUARDIAN_DEBUG` verbose mode; secrets never
  logged.
- A GitHub Actions **job summary** (`$GITHUB_STEP_SUMMARY`) with the risk headline
  and links, so maintainers see results without opening the PR.
- A `--selfcheck` mode validating environment, token scopes, and provider
  reachability.

Excluded:

- External telemetry by default. Any metrics are opt-in and anonymized (privacy).

## Deliverables

- Failure-boundary wrapper around the entrypoint with tests simulating analyzer,
  API, and provider failures.
- Retry/timeout utility used by all HTTP calls.
- `errors[]` rendered in the report + a "degraded" badge in the check/comment when
  any analyzer failed.
- Job-summary writer.
- `python -m codeguardian --selfcheck`.

## Senior Developer Prompt

```text
You are making CodeGuardian robust and observable (Phase 8).
Read CONTEXT-GRAPH.md, then ROOT, PLAN, and the code map.

Implement:
- A top-level try/except boundary: any uncaught error -> neutral check, error in
  artifact, exit 0. Never crash, never block on our own bug.
- A shared retry+timeout HTTP helper (backoff+jitter) for GitHub/Groq/HF.
- Report.errors surfaced; "degraded run" note when analyzers fail.
- Leveled logging + CODEGUARDIAN_DEBUG; never log secrets or full source.
- A GitHub job-summary writer.
- A --selfcheck command (env, token scopes, provider reachability).

Return: design, files, failure-injection tests.
```

## Acceptance Criteria

- Injected failures (analyzer exception, API 500, provider timeout) never crash
  the Action; the run reports a degraded result and exits 0.
- Every network call has a timeout and bounded retries.
- A job summary appears on every run.
- `--selfcheck` reports a clear pass/fail per dependency.
- No secret or full-source content appears in any log at any level.
