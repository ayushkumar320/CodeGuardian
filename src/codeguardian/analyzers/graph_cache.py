"""Persist + incrementally patch the import graph across runs (P1-4).

Rebuilding the whole import graph every PR is O(repo); on a large monorepo that
dominates the run even though the diff is tiny and the graph is mostly stable.
This module serializes the graph to a small JSON sidecar and, on the next run,
loads it and re-parses *only the changed files'* imports.

Cache invalidation is deliberately aggressive (strict: a stale graph yields
wrong dependents): the cache header pins ``ANALYZER_VERSION`` and a build
timestamp, and any version mismatch / age-out / read error returns ``None`` so
the caller falls back to a full build. Only forward edges are stored; the
reverse map is derived on load.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from .. import ANALYZER_VERSION
from ..models import DiffFile, FileStatus
from .imports import (
    _CODE_EXT,
    _GO_EXT,
    _PY_EXT,
    _IMPORT_RE,
    _extract_go_imports,
    _extract_py_imports,
    _go_module_path,
    _resolve_go,
    _resolve_py,
    _resolve_ts,
    ImportGraph,
)

_CACHE_VERSION = 1  # bump if the on-disk shape changes


def serialize_graph(graph: ImportGraph) -> dict:
    """Forward edges only (reverse is derived on load), plus an invalidation
    header. Sets are sorted for a stable, diff-friendly artifact."""
    return {
        "cache_version": _CACHE_VERSION,
        "analyzer_version": ANALYZER_VERSION,
        "built_at": time.time(),
        "forward": {f: sorted(t) for f, t in graph.forward.items()},
    }


def _reverse_from_forward(forward: dict[str, set[str]]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {f: set() for f in forward}
    for importer, targets in forward.items():
        for t in targets:
            reverse.setdefault(t, set()).add(importer)
    return reverse


def deserialize_graph(data: dict, max_age_days: int = 30) -> Optional[ImportGraph]:
    """Rebuild an ImportGraph from cache data, or None when the cache is stale,
    version-mismatched, aged out, or malformed (caller does a full build)."""
    if not isinstance(data, dict):
        return None
    if data.get("cache_version") != _CACHE_VERSION:
        return None
    if data.get("analyzer_version") != ANALYZER_VERSION:
        return None
    built_at = data.get("built_at")
    if max_age_days and isinstance(built_at, (int, float)):
        if time.time() - built_at > max_age_days * 86400:
            return None
    raw_forward = data.get("forward")
    if not isinstance(raw_forward, dict):
        return None
    forward = {f: set(t) for f, t in raw_forward.items()}
    return ImportGraph(forward=forward, reverse=_reverse_from_forward(forward))


def load_graph(path: str, max_age_days: int = 30) -> Optional[ImportGraph]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return deserialize_graph(data, max_age_days=max_age_days)


def save_graph(path: str, graph: ImportGraph) -> bool:
    if not path:
        return False
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(serialize_graph(graph), fh)
    except OSError:
        return False
    return True


def _forward_edges_for_file(repo_root: str, rel: str, fileset: set[str],
                            module_path: Optional[str] = None) -> set[str]:
    """Re-parse a single file's local imports against ``fileset``."""
    try:
        with open(os.path.join(repo_root, rel), "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return set()
    targets: set[str] = set()
    if rel.endswith(_PY_EXT):
        for dots, mod in _extract_py_imports(text):
            t = _resolve_py(rel, dots, mod, fileset)
            if t:
                targets.add(t)
    elif rel.endswith(_GO_EXT):
        for spec in _extract_go_imports(text):
            targets.update(t for t in _resolve_go(spec, fileset, module_path) if t != rel)
    else:
        for spec in _IMPORT_RE.findall(text):
            t = _resolve_ts(rel, spec, fileset)
            if t:
                targets.add(t)
    return targets


def patch_graph(graph: ImportGraph, repo_root: str, changed: list[DiffFile]) -> ImportGraph:
    """Update a cached graph in place for the changed files only — re-parse the
    imports of added/modified code files, drop removed ones — skipping the full
    repo walk. Returns the same graph object.

    Note: an unchanged file that imports a *newly added* module won't gain that
    edge until the next full rebuild (we only re-parse changed files). This is
    an accepted freshness tradeoff; the next default-branch build heals it.
    """
    forward, reverse = graph.forward, graph.reverse
    module_path = _go_module_path(repo_root)
    # Current fileset reflecting the changes, so import resolution sees adds/removes.
    fileset = set(forward.keys())
    for f in changed:
        rel = f.path.replace(os.sep, "/")
        if not rel.endswith(_CODE_EXT):
            continue
        if f.status == FileStatus.removed:
            fileset.discard(rel)
        else:
            fileset.add(rel)

    for f in changed:
        rel = f.path.replace(os.sep, "/")
        if not rel.endswith(_CODE_EXT):
            continue

        # Detach this file's existing forward contributions from the reverse map.
        for t in forward.get(rel, set()):
            if t in reverse:
                reverse[t].discard(rel)

        if f.status == FileStatus.removed:
            forward.pop(rel, None)
            # Drop edges pointing at the removed file from its importers.
            for importer in reverse.get(rel, set()):
                forward.get(importer, set()).discard(rel)
            reverse.pop(rel, None)
            continue

        new_targets = _forward_edges_for_file(repo_root, rel, fileset, module_path)
        forward[rel] = new_targets
        reverse.setdefault(rel, set())
        for t in new_targets:
            reverse.setdefault(t, set()).add(rel)
    return graph
