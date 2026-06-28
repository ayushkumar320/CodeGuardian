"""Entry / context LangGraph nodes (Phase 2).

collect_pr_context loads the diff; repository_context builds a lightweight repo
understanding (languages, frameworks, manifests, tests) the domain agents share.
Domain + synthesis agents live in agents.py.
"""

from __future__ import annotations

import os

from ..analyzers.imports import build_import_graph
from ..models import FileCategory, RepositoryContext
from ..pr.diff import compute_diff
from ..walk import iter_repo_files
from .state import CodeGuardianState

_AREA_BY_CATEGORY = {
    FileCategory.frontend: "Frontend",
    FileCategory.backend: "Backend",
    FileCategory.database: "Database",
    FileCategory.config: "Config",
    FileCategory.types: "Shared types",
    FileCategory.test: "Tests",
}

_CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".css", ".scss")


def collect_pr_context(state: CodeGuardianState) -> dict:
    pr = state["pr"]
    files = compute_diff(state["repo_root"], pr.base_sha, pr.head_sha)

    notes: list[str] = []
    cap = state["policy"].performance.max_diff_files
    if len(files) > cap:
        total = len(files)
        # Prioritize the largest changes so the cap keeps the most impactful files.
        files = sorted(files, key=lambda f: f.additions + f.deletions, reverse=True)[:cap]
        notes.append(
            f"Diff too large: {total} files changed; analyzed the top {cap} by size. "
            f"Findings may be incomplete."
        )

    areas = sorted(
        {
            _AREA_BY_CATEGORY[f.category]
            for f in files
            if f.category in _AREA_BY_CATEGORY and f.category != FileCategory.docs
        }
    )
    return {"diff": files, "affected_areas": areas, "notes": notes}


def repository_context(state: CodeGuardianState) -> dict:
    root = state["repo_root"]
    perf = state["policy"].performance
    langs: dict[str, int] = {}
    manifests: list[str] = []
    tests: list[str] = []
    frameworks: set[str] = set()

    # Bounded, gitignore-aware enumeration (Phase 10) — same source of truth as
    # the import graph below.
    for rel in iter_repo_files(root, max_files=perf.max_files, max_file_bytes=perf.max_file_bytes):
        fn = rel.rsplit("/", 1)[-1]
        ext = os.path.splitext(fn)[1].lower()
        if ext in _CODE_EXT:
            langs[ext] = langs.get(ext, 0) + 1
        if fn == "package.json":
            manifests.append(rel)
            frameworks |= _frameworks_from_manifest(os.path.join(root, rel))
        if fn.lower().endswith("schema.prisma"):
            frameworks.add("prisma")
        if ".test." in fn or ".spec." in fn or "__tests__/" in rel:
            tests.append(rel)

    return {
        "repository": RepositoryContext(
            language_summary=langs,
            framework_summary=sorted(frameworks),
            package_manifests=manifests[:20],
            test_files=tests[:200],
        ),
        # Build the import graph once here (before the parallel domain fan-out) so
        # every analyzer shares it instead of rebuilding (Phase 10).
        "import_graph": build_import_graph(root, perf.max_files, perf.max_file_bytes),
    }


def _frameworks_from_manifest(path: str) -> set[str]:
    import json

    found: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return found
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for name, marker in (("next", "next"), ("react", "react"), ("express", "express")):
        if name in deps:
            found.add(marker)
    return found
