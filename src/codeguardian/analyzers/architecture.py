"""Architecture-rule analysis (deterministic).

Three checks, all driven by policy:
1. forbidden_imports — a file matching `paths` must not import a spec containing
   `cannot_import`.
2. layers — a file in layer L may only import files in `may_import` layers.
3. circular dependencies — cycles in the local import graph that involve a
   changed file.
"""

from __future__ import annotations

import os

from ..models import (
    Blocking,
    Category,
    DiffFile,
    Finding,
    Severity,
)
from ..globs import glob_match
from ..policy import Architecture, Layer
from .imports import _IMPORT_RE, ImportGraph, build_import_graph

_CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _read_specs(repo_root: str, rel: str) -> list[str]:
    full = os.path.join(repo_root, rel)
    if not os.path.isfile(full):
        return []
    try:
        with open(full, "r", encoding="utf-8", errors="ignore") as fh:
            return _IMPORT_RE.findall(fh.read())
    except OSError:
        return []


def _layer_of(path: str, layers: list[Layer]) -> Layer | None:
    for layer in layers:
        if glob_match(path, layer.paths):
            return layer
    return None


def analyze(repo_root: str, changed: list[DiffFile], arch: Architecture,
            graph: ImportGraph | None = None) -> list[Finding]:
    findings: list[Finding] = []
    idx = [1]  # mutable counter shared by helpers
    # Build (or reuse) the forward import map once; both layer-direction and
    # circular-dependency checks below share it instead of rebuilding twice.
    _forward: dict[str, set[str]] | None = None

    def forward_map() -> dict[str, set[str]]:
        nonlocal _forward
        if _forward is None:
            _forward = (graph or build_import_graph(repo_root)).forward
        return _forward

    def add(path, title, summary, action):
        findings.append(
            Finding(
                id=f"CG-ARCH-{idx[0]:03d}",
                category=Category.architecture,
                severity=Severity.high,
                confidence=0.8,
                title=title,
                summary=summary,
                evidence_files=[path] if isinstance(path, str) else path,
                recommended_actions=[action],
                blocking=Blocking(guarded=True, strict=True),
            )
        )
        idx[0] += 1

    code_changed = [f for f in changed if f.path.replace(os.sep, "/").endswith(_CODE_EXT)]

    # 1 + 2 need each changed file's import specs.
    for f in code_changed:
        norm = f.path.replace(os.sep, "/")
        specs = _read_specs(repo_root, norm)

        for rule in arch.forbidden_imports:
            if not glob_match(norm, rule.paths):
                continue
            bad = [s for s in specs if rule.cannot_import.lower() in s.lower()]
            if bad:
                add(norm, f"Forbidden import in {norm}",
                    f"{norm} imports '{bad[0]}' (rule: {rule.paths} cannot import "
                    f"{rule.cannot_import}). {rule.reason}".strip(),
                    f"Remove the dependency on '{rule.cannot_import}' from {norm}")

    # 2. Layer-direction violations (need resolved targets -> forward graph).
    if arch.layers:
        forward = forward_map()
        for f in code_changed:
            norm = f.path.replace(os.sep, "/")
            src_layer = _layer_of(norm, arch.layers)
            if src_layer is None or not src_layer.may_import:
                continue
            allowed = set(src_layer.may_import) | {src_layer.name}
            for target in sorted(forward.get(norm, set())):
                tgt_layer = _layer_of(target, arch.layers)
                if tgt_layer and tgt_layer.name not in allowed:
                    add([norm, target],
                        f"Layer violation: {src_layer.name} → {tgt_layer.name}",
                        f"{norm} (layer '{src_layer.name}') imports {target} "
                        f"(layer '{tgt_layer.name}'), which is not in may_import.",
                        f"Invert the dependency or route it through an allowed layer")

    # 3. Circular dependencies involving a changed file.
    if arch.detect_circular and code_changed:
        forward = forward_map()
        changed_set = {f.path.replace(os.sep, "/") for f in code_changed}
        seen_cycles: set[frozenset] = set()
        for start in changed_set:
            cycle = _find_cycle(start, forward)
            if cycle:
                key = frozenset(cycle)
                if key in seen_cycles:
                    continue
                seen_cycles.add(key)
                add(cycle,
                    f"Circular dependency involving {start}",
                    "Import cycle: " + " → ".join(cycle + [cycle[0]]),
                    "Break the cycle by extracting shared code or inverting a dependency")
    return findings


def _find_cycle(start: str, forward: dict[str, set[str]]) -> list[str] | None:
    """Return a cycle path starting and ending at `start`, or None. DFS bounded
    to nodes reachable from start."""
    stack = [(start, [start])]
    visited: set[str] = set()
    while stack:
        node, path = stack.pop()
        for nxt in forward.get(node, ()):
            if nxt == start and len(path) > 1:
                return path
            if nxt not in visited and nxt not in path:
                visited.add(nxt)
                stack.append((nxt, path + [nxt]))
    return None
