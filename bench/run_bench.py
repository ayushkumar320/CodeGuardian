#!/usr/bin/env python3
"""Phase 10 performance benchmark harness.

Generates synthetic JS/TS repos of varying size, then times the two hot paths:
the shared import-graph build and a full deterministic analysis run. Prints a
small table so we can track timings against the budgets in bench/README.md.

Usage:
    python bench/run_bench.py                 # default sizes: 1000 10000
    python bench/run_bench.py 1000 10000 50000

No model keys are used; everything runs deterministically.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

# Make `src/` importable when run from the repo root without installation.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from codeguardian.analyzers.imports import build_import_graph  # noqa: E402
from codeguardian.graph.build import run_analysis  # noqa: E402
from codeguardian.models import PrContext  # noqa: E402
from codeguardian.policy import Policy  # noqa: E402


def _git(root: str, *args: str) -> None:
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


def generate_repo(root: str, n_files: int, fanout: int = 5) -> None:
    """Create n_files TS modules, each importing a few earlier ones."""
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    for i in range(n_files):
        imports = "".join(
            f"import {{ v{j} }} from './m{j}';\n"
            for j in range(max(0, i - fanout), i)
        )
        body = f"export const v{i} = {i};\n"
        with open(os.path.join(root, "src", f"m{i}.ts"), "w", encoding="utf-8") as fh:
            fh.write(imports + body)


def bench_size(n_files: int) -> dict:
    with tempfile.TemporaryDirectory(
        prefix=f"cg-bench-{n_files}-", ignore_cleanup_errors=True
    ) as root:
        _git(root, "init", "-q")
        generate_repo(root, n_files)
        _git(root, "add", "-A")
        _git(root, "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-q", "-m", "base")
        base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        # touch one file to create a diff
        with open(os.path.join(root, "src", "m0.ts"), "a", encoding="utf-8") as fh:
            fh.write("export const touched = true;\n")
        _git(root, "add", "-A")
        _git(root, "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-q", "-m", "change")
        head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

        t0 = time.perf_counter()
        graph = build_import_graph(root)
        t_graph = time.perf_counter() - t0

        pr = PrContext(owner="o", repo="r", number=1, base_sha=base, head_sha=head)
        t0 = time.perf_counter()
        run_analysis(root, pr, Policy())
        t_run = time.perf_counter() - t0

        return {
            "files": n_files,
            "nodes": len(graph.forward),
            "graph_s": round(t_graph, 3),
            "run_s": round(t_run, 3),
        }


def main(argv: list[str]) -> int:
    sizes = [int(a) for a in argv[1:]] or [1000, 10000]
    print(f"{'files':>8} {'graph(s)':>10} {'run(s)':>9}")
    for n in sizes:
        r = bench_size(n)
        print(f"{r['files']:>8} {r['graph_s']:>10} {r['run_s']:>9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
