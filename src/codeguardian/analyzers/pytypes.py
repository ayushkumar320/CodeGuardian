"""Python public-API surface change analysis (deterministic — P2-1 increment).

The Python analog of :mod:`types` (which is TS-only): a removed or renamed
*public, module-level* ``def``/``class`` in a changed ``.py`` file is a likely
breaking change for every file that imports that module. Severity scales with
the import blast radius.

Patch-only and removal-only (a re-added name is a no-op reformat, not a break),
so it carries the same low-false-positive profile as the TS types analyzer. The
deeper AST work (Protocol/TypedDict/dataclass field renames) remains future
work; this covers the common "you deleted/renamed a public function or class"
case that breaks importers.
"""

from __future__ import annotations

import os
import re

from ..models import Blocking, Category, DiffFile, Finding, Severity
from .imports import ImportGraph, build_import_graph

# Top-level def/class only: in a patch line the keyword sits immediately after
# the +/- marker (an indented method would have whitespace first). Public only
# (a leading underscore means private by convention — renaming it isn't a
# public-contract break).
_PUBLIC_DEF_RE = re.compile(r"^(?:async\s+)?(?:def|class)\s+([A-Za-z][A-Za-z0-9_]*)")


def _public_symbols(patch: str | None, marker: str) -> set[str]:
    out: set[str] = set()
    if not patch:
        return out
    skip = marker * 3  # '---' / '+++' file headers
    for line in patch.splitlines():
        if line.startswith(marker) and not line.startswith(skip):
            m = _PUBLIC_DEF_RE.match(line[1:])
            if m:
                out.add(m.group(1))
    return out


def _removed_public_symbols(patch: str | None) -> list[str]:
    removed = _public_symbols(patch, "-")
    added = _public_symbols(patch, "+")
    return sorted(removed - added)


def analyze(repo_root: str, changed: list[DiffFile],
            graph: ImportGraph | None = None) -> list[Finding]:
    targets = [f for f in changed if f.path.endswith(".py")]
    if not targets:
        return []
    reverse = (graph or build_import_graph(repo_root)).reverse
    findings: list[Finding] = []
    idx = 1
    for f in targets:
        norm = f.path.replace(os.sep, "/")
        removed = _removed_public_symbols(f.patch)
        if not removed:
            continue
        dependents = sorted(reverse.get(norm, set()))
        n = len(dependents)
        if n >= 3:
            sev, conf = Severity.critical, 0.82
        elif n >= 1:
            sev, conf = Severity.high, 0.78
        else:
            sev, conf = Severity.medium, 0.6
        findings.append(
            Finding(
                id=f"CG-PYAPI-{idx:03d}",
                category=Category.dependency,
                severity=sev,
                confidence=conf,
                title=f"Public symbol removed/renamed in {norm}: {', '.join(removed[:3])}",
                summary=(
                    f"Public def/class {', '.join(removed[:5])} removed/renamed. "
                    f"{n} file(s) import this module and may break at import time."
                ),
                evidence_files=[norm] + dependents[:10],
                recommended_actions=[
                    f"Update the {n} importer(s) or keep a backward-compatible alias",
                ],
                blocking=Blocking(
                    guarded=sev in (Severity.high, Severity.critical),
                    strict=sev in (Severity.high, Severity.critical),
                ),
            )
        )
        idx += 1
    return findings
