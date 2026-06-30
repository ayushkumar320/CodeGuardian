"""Entry / context LangGraph nodes (Phase 2).

collect_pr_context loads the diff; repository_context builds a lightweight repo
understanding (languages, frameworks, manifests, tests) the domain agents share.
Domain + synthesis agents live in agents.py.
"""

from __future__ import annotations

import os

from ..analyzers.imports import build_import_graph
from ..analyzers import graph_cache
from ..languages import _EXT_TO_LANG, detect as detect_languages
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
        # Count any known language extension, not just the deep-supported ones,
        # so the language report can describe what's actually in the repo
        # (graceful-degradation tier).
        if ext in _EXT_TO_LANG or ext in _CODE_EXT:
            langs[ext] = langs.get(ext, 0) + 1
        if fn == "package.json":
            manifests.append(rel)
            frameworks |= _frameworks_from_manifest(os.path.join(root, rel))
        if fn.lower().endswith("schema.prisma"):
            frameworks.add("prisma")
        if ".test." in fn or ".spec." in fn or "__tests__/" in rel:
            tests.append(rel)

    # Honest language matrix: tell the user when this PR is fully in a language
    # we don't deeply analyze, so a low score isn't misread as "all clear"
    # (graceful-degradation tier — strict rule #2 won't let us fabricate findings).
    notes: list[str] = []
    lr = detect_languages(
        language_summary=langs,
        changed_paths=[f.path for f in state.get("diff", [])],
    )
    if lr.fully_unsupported_pr:
        names = ", ".join(lr.unsupported_in_pr)
        notes.append(
            f"Language-agnostic mode: this PR touches {names}, which has no "
            f"deep CodeGuardian analyzer yet. Only PR-shape and high-risk path "
            f"signals will fire — a low score does not mean low risk."
        )
    elif lr.unsupported_in_pr:
        names = ", ".join(lr.unsupported_in_pr)
        notes.append(
            f"Partial analysis: {names} files in this PR get only language-"
            f"agnostic signals (PR shape, high-risk paths)."
        )

    return {
        "repository": RepositoryContext(
            language_summary=langs,
            framework_summary=sorted(frameworks),
            package_manifests=manifests[:20],
            test_files=tests[:200],
        ),
        # Build the import graph once here (before the parallel domain fan-out) so
        # every analyzer shares it instead of rebuilding (Phase 10). When a cache
        # sidecar is configured (CODEGUARDIAN_GRAPH_CACHE), reuse it and patch
        # only the changed files instead of walking the whole repo (P1-4).
        "import_graph": _resolve_import_graph(root, perf, state.get("diff", [])),
        "notes": notes,
    }


def _resolve_import_graph(root: str, perf, diff):
    """Cached-and-patched graph when CODEGUARDIAN_GRAPH_CACHE points at a valid,
    fresh sidecar; otherwise a full build (and the cache is refreshed for next
    time). Any cache miss / staleness falls back to the full walk."""
    cache_path = os.environ.get("CODEGUARDIAN_GRAPH_CACHE", "")
    if cache_path:
        cached = graph_cache.load_graph(cache_path)
        if cached is not None:
            return graph_cache.patch_graph(cached, root, diff)
    graph = build_import_graph(root, perf.max_files, perf.max_file_bytes)
    if cache_path:
        graph_cache.save_graph(cache_path, graph)
    return graph


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
