"""Lightweight dependency / blast-radius analysis.

Builds a reverse-import map across the repo so we can estimate which files
depend on a changed module. Produces deterministic ``dependency`` findings with
the impacted files as evidence. Also flags high-risk path edits.

Supports JS/TS (the primary target) and Python (Phase 12 add). Each language gets
its own regex pair (extract + resolve); the rest of the pipeline is language-
agnostic.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from ..models import (
    Blocking,
    Category,
    DiffFile,
    FileCategory,
    Finding,
    Severity,
)
from ..pr.classify import matches_any
from ..walk import DEFAULT_MAX_FILES, DEFAULT_MAX_FILE_BYTES, iter_repo_files

# --- JS / TS ------------------------------------------------------------------
_IMPORT_RE = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*|require\(\s*|export\s[^'"]*?from\s*)['"]([^'"]+)['"]"""
)
_TS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
_RESOLVE_EXT = ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]

# --- Python -------------------------------------------------------------------
_PY_EXT = (".py",)
# `from .util import foo`, `from ..pkg.mod import x`, `from pkg.mod import x`,
# also `from . import util`.
_PY_FROM_RE = re.compile(
    r"^\s*from\s+(?P<dots>\.+)?(?P<mod>[A-Za-z_][\w.]*)?\s+import\s+",
    re.MULTILINE,
)
# `import pkg.mod`, `import pkg.mod as alias` — bare/absolute only; `import .x` is
# not legal Python without `from`, so we don't try to match it.
_PY_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<mod>[A-Za-z_][\w.]*)(?:\s+as\s+\w+)?\s*$",
    re.MULTILINE,
)

# --- Go (P2-2) ----------------------------------------------------------------
_GO_EXT = (".go",)
# Import specs in a block: `import (\n  "a/b"\n  alias "c/d"\n)`.
_GO_BLOCK_RE = re.compile(r"import\s*\(\s*(.*?)\)", re.DOTALL)
# A single import: `import "a/b"` or `import alias "a/b"`.
_GO_SINGLE_RE = re.compile(r'^\s*import\s+(?:[\w.]+\s+)?"([^"]+)"', re.MULTILINE)
_GO_QUOTED_RE = re.compile(r'"([^"]+)"')

_CODE_EXT = _TS_EXT + _PY_EXT + _GO_EXT


def _go_module_path(repo_root: str) -> str | None:
    """The module path from go.mod (e.g. ``github.com/acme/app``), or None.
    Local imports are prefixed with this; everything else is a third-party
    package we don't resolve to a repo file."""
    try:
        with open(os.path.join(repo_root, "go.mod"), "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("module "):
                    return line.split(None, 1)[1].strip()
    except OSError:
        return None
    return None


def _extract_go_imports(text: str) -> list[str]:
    specs: list[str] = []
    for block in _GO_BLOCK_RE.finditer(text):
        for line in block.group(1).splitlines():
            m = _GO_QUOTED_RE.search(line)
            if m:
                specs.append(m.group(1))
    for m in _GO_SINGLE_RE.finditer(text):
        specs.append(m.group(1))
    return specs


def _resolve_go(spec: str, fileset: set[str], module_path: str | None) -> list[str]:
    """A Go import names a *package* (directory). Resolve a local import to every
    non-test ``.go`` file in that package directory — changing any of them affects
    importers. Third-party / stdlib imports (no module prefix) resolve to nothing.
    """
    if not module_path or not spec.startswith(module_path + "/"):
        return []
    reldir = spec[len(module_path) + 1:]
    out = []
    for cand in fileset:
        if not cand.endswith(".go") or cand.endswith("_test.go"):
            continue
        d = cand.rsplit("/", 1)[0] if "/" in cand else ""
        if d == reldir:
            out.append(cand)
    return out


def _iter_code_files(
    repo_root: str,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> list[str]:
    return iter_repo_files(
        repo_root, _CODE_EXT, max_files=max_files, max_file_bytes=max_file_bytes
    )


def _resolve_ts(importer: str, spec: str, all_files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None  # package import, not a local file
    base = os.path.normpath(os.path.join(os.path.dirname(importer), spec))
    for ext in _RESOLVE_EXT:
        cand = (base + ext).replace(os.sep, "/")
        if cand in all_files:
            return cand
    return None


# Kept under the old name so existing tests/imports keep working.
_resolve = _resolve_ts


def _extract_py_imports(text: str) -> list[tuple[int, str]]:
    """Return [(leading_dots, dotted_module_or_empty), ...] for a Python file.

    ``dots`` is 0 for absolute imports (``from pkg.x import y`` / ``import pkg.x``)
    and 1+ for relative imports. ``module`` may be empty for ``from . import x``
    (we still emit the entry so the caller can resolve to the package dir).
    """
    out: list[tuple[int, str]] = []
    for m in _PY_FROM_RE.finditer(text):
        dots = len(m.group("dots") or "")
        mod = m.group("mod") or ""
        if dots == 0 and not mod:
            continue
        out.append((dots, mod))
    for m in _PY_IMPORT_RE.finditer(text):
        out.append((0, m.group("mod")))
    return out


def _resolve_py(
    importer: str, dots: int, module: str, all_files: set[str]
) -> str | None:
    """Resolve a Python import to a repo-relative file path, or None.

    Conservatively handles:
    - relative imports (``dots >= 1``) anchored on the importer's directory;
    - absolute imports tried first at repo root, then under a top-level ``src/``
      (common 'src layout').
    Returns the first ``pkg/mod.py`` or ``pkg/mod/__init__.py`` that exists.
    Multiple plausible matches → returns the first; ambiguous absolute imports
    that don't match are simply skipped (preferred over wrong attribution).
    """
    parts = module.split(".") if module else []

    if dots >= 1:
        # Walk up `dots - 1` directories from the importer's directory.
        here = importer.split("/")[:-1]
        up = dots - 1
        if up > len(here):
            return None
        base_dir = here[: len(here) - up]
        candidate_dir = base_dir + parts
    else:
        # Absolute import: try repo-root layout first, then src/ layout.
        candidate_dir = parts

    base = "/".join(candidate_dir)
    candidates = [f"{base}.py" if base else "", f"{base}/__init__.py" if base else ""]
    if dots == 0:
        candidates += [f"src/{base}.py", f"src/{base}/__init__.py"]
    for c in candidates:
        if c and c in all_files:
            return c
    return None


@dataclass
class ImportGraph:
    """Forward + reverse local-import maps, built in a single repo pass.

    ``forward[f]``  = local files that ``f`` imports.
    ``reverse[f]``  = local files that import ``f``.

    Built once per run (Phase 10) and shared across analyzers via graph state, so
    the repo is walked and each file read exactly once instead of 4-5 times.
    """

    forward: dict[str, set[str]] = field(default_factory=dict)
    reverse: dict[str, set[str]] = field(default_factory=dict)


def build_import_graph(
    repo_root: str,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> ImportGraph:
    """Walk the repo once, read each code file once, build forward + reverse maps.

    The walk is bounded (``max_files``) and gitignore-aware via :mod:`walk`.
    """
    files = _iter_code_files(repo_root, max_files, max_file_bytes)
    fileset = set(f.replace(os.sep, "/") for f in files)
    module_path = _go_module_path(repo_root)
    forward: dict[str, set[str]] = {f: set() for f in fileset}
    reverse: dict[str, set[str]] = {f: set() for f in fileset}
    for f in files:
        try:
            with open(os.path.join(repo_root, f), "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        importer = f.replace(os.sep, "/")
        targets: list[str] = []
        if importer.endswith(_PY_EXT):
            for dots, mod in _extract_py_imports(text):
                t = _resolve_py(importer, dots, mod, fileset)
                if t:
                    targets.append(t)
        elif importer.endswith(_GO_EXT):
            for spec in _extract_go_imports(text):
                targets.extend(t for t in _resolve_go(spec, fileset, module_path) if t != importer)
        else:  # JS/TS family
            for spec in _IMPORT_RE.findall(text):
                t = _resolve_ts(importer, spec, fileset)
                if t:
                    targets.append(t)
        for t in targets:
            forward[importer].add(t)
            reverse[t].add(importer)
    return ImportGraph(forward=forward, reverse=reverse)


def build_reverse_imports(repo_root: str) -> dict[str, set[str]]:
    """Map each file -> set of files that import it. (Standalone; prefer
    ``build_import_graph`` when both directions are needed.)"""
    return build_import_graph(repo_root).reverse


def build_forward_imports(repo_root: str) -> dict[str, set[str]]:
    """Map each file -> set of local files it imports. (Standalone; prefer
    ``build_import_graph`` when both directions are needed.)"""
    return build_import_graph(repo_root).forward


def analyze(
    repo_root: str,
    changed: list[DiffFile],
    high_risk_paths: list[str],
    graph: ImportGraph | None = None,
) -> list[Finding]:
    reverse = (graph or build_import_graph(repo_root)).reverse
    findings: list[Finding] = []
    idx = 1

    for f in changed:
        norm = f.path.replace(os.sep, "/")
        dependents = sorted(reverse.get(norm, set()))
        is_high_risk = matches_any(norm, high_risk_paths)

        if not dependents and not is_high_risk:
            continue

        n = len(dependents)
        severity, confidence = _grade(n, is_high_risk, f.category)
        evidence = [norm] + dependents[:10]
        blast = f"{n} file(s) import this module" if n else "high-risk path edit"
        findings.append(
            Finding(
                id=f"CG-DEP-{idx:03d}",
                category=Category.dependency,
                severity=severity,
                confidence=confidence,
                title=f"Change in {norm} affects {n} dependent file(s)"
                if n
                else f"High-risk path changed: {norm}",
                summary=f"{norm} was {f.status.value}. {blast}.",
                evidence_files=evidence,
                recommended_actions=_actions(norm, dependents, is_high_risk),
                blocking=Blocking(
                    guarded=severity in (Severity.high, Severity.critical),
                    strict=severity in (Severity.high, Severity.critical),
                ),
            )
        )
        idx += 1
    return findings


def _grade(n: int, high_risk: bool, category: FileCategory) -> tuple[Severity, float]:
    if high_risk and n >= 5:
        return Severity.critical, 0.8
    if high_risk or n >= 8:
        return Severity.high, 0.75
    if n >= 3:
        return Severity.medium, 0.65
    return Severity.low, 0.55


def _actions(path: str, dependents: list[str], high_risk: bool) -> list[str]:
    actions = []
    if dependents:
        actions.append(f"Review the {len(dependents)} file(s) importing {path}")
    if high_risk:
        actions.append("Confirm backward compatibility for this high-risk path")
    if not actions:
        actions.append("No action required")
    return actions
