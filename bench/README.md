# Performance benchmarks (Phase 10)

Synthetic-repo harness for tracking CodeGuardian's hot paths: the shared
import-graph build and a full deterministic analysis run. No model keys are used.

## Run

```bash
python bench/run_bench.py                 # 1000, 10000
python bench/run_bench.py 1000 10000 50000
```

Each size generates a throwaway git repo of N interlinked TS modules, times the
import-graph build and a full `run_analysis`, and prints a row.

## Baseline (recorded 2026-06-28, Apple Silicon, deterministic mode)

| files  | graph build | full run |
|-------:|------------:|---------:|
|  1,000 |     ~0.03 s |  ~0.06 s |
| 10,000 |     ~0.33 s |  ~0.39 s |

Timings scale roughly linearly with file count (single repo pass + single diff).

## Budgets (regression guardrails)

These are generous ceilings; investigate if a change pushes past them on the
benchmark repos:

| files  | graph build | full run |
|-------:|------------:|---------:|
|  1,000 |     < 0.5 s |  < 1.0 s |
| 10,000 |     < 2.0 s |  < 3.0 s |
| 50,000 |     < 8.0 s | < 15.0 s |

Budgets assume the Phase 10 optimizations stay in place: the import graph is built
**once** per run and shared, the repo walk is bounded/gitignore-aware, and the
diff is computed with a single `git diff`. Very large diffs are additionally
capped by `policy.performance.max_diff_files`.
