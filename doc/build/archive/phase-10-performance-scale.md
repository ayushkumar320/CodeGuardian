# Phase 10: Performance & Scale

## Objective

Keep CodeGuardian fast and bounded on real-world repositories, including large
monorepos and big diffs, without compromising the deterministic guarantees.

## Current cost centers (to measure first)

- `build_reverse_imports` / `build_forward_imports` walk the whole repo and read
  every code file — O(repo) per run, repeated across analyzers.
- Full-tree walk in `repository_context`.
- Per-file `git diff` calls in diff collection.
- Memory branch grows unbounded (append-only JSONL).

## Scope

Included:

- **Benchmark harness** on synthetic repos of varying size (1k / 10k / 50k files)
  with documented timing budgets.
- **Build the import graph once** and share it across analyzers (currently several
  analyzers each rebuild it).
- Bound the repo walk (respect `.gitignore`, skip vendored dirs, cap file count /
  size; skip minified/generated files).
- Batch the diff collection (single `git diff` parse instead of per-file calls).
- **Large-diff handling:** cap analyzed files with a clear "diff too large,
  analyzed top N" note.
- **Memory retention/compaction:** cap records, compact old entries, configurable
  retention window; keep the branch small.
- Overall run-time budget + a soft timeout that still publishes a partial result.

Excluded:

- Distributed/queued processing (that's the SaaS direction, out of scope).

## Deliverables

- `bench/` harness + a documented performance baseline and budgets.
- Shared import-graph build (one pass per run).
- Bounded walk + batched diff.
- Memory compaction with a retention policy in `policy.memory`.
- Large-diff and timeout handling with user-visible notes.

## Senior Developer Prompt

```text
You are optimizing CodeGuardian performance (Phase 10).
Read CONTEXT-GRAPH.md, then ROOT, PLAN, and the code map (analyzers/imports.py,
graph/*, pr/diff.py, memory/*).

Deliver:
- A benchmark harness + baseline timings (1k/10k/50k files).
- One shared import-graph build reused by all analyzers.
- Bounded repo walk (gitignore-aware, caps) and batched git diff parsing.
- Large-diff cap + soft run-time budget that still publishes partial results.
- Memory compaction + retention policy.

Return: design, measured before/after numbers, files, tests.
```

## Acceptance Criteria

- Documented timing budgets met on the benchmark repos; measured improvement vs
  the pre-phase baseline.
- The import graph is built at most once per run.
- A very large diff produces a bounded, clearly-noted result without timing out.
- The memory branch stays bounded under a retention policy.
- No change to findings/score correctness (existing tests still green).
