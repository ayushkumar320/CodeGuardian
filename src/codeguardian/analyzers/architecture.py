"""Basic architecture-rule analysis (deterministic).

Phase 2 baseline: enforce policy `forbidden_imports` rules — a file matching a
rule's `paths` glob must not import anything whose spec contains `cannot_import`.
Layer-direction and circular-dependency detection are Phase 4.
"""

from __future__ import annotations

import fnmatch
import os

from ..models import (
    Blocking,
    Category,
    DiffFile,
    Finding,
    Severity,
)
from ..policy import Architecture
from .imports import _IMPORT_RE  # reuse the same import matcher

_CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def analyze(repo_root: str, changed: list[DiffFile], arch: Architecture) -> list[Finding]:
    if not arch.forbidden_imports:
        return []
    findings: list[Finding] = []
    idx = 1
    for f in changed:
        norm = f.path.replace(os.sep, "/")
        if not norm.endswith(_CODE_EXT):
            continue
        full = os.path.join(repo_root, f.path)
        if not os.path.isfile(full):
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                specs = _IMPORT_RE.findall(fh.read())
        except OSError:
            continue
        for rule in arch.forbidden_imports:
            if not fnmatch.fnmatch(norm.lower(), rule.paths.lower()):
                continue
            bad = [s for s in specs if rule.cannot_import.lower() in s.lower()]
            if not bad:
                continue
            findings.append(
                Finding(
                    id=f"CG-ARCH-{idx:03d}",
                    category=Category.architecture,
                    severity=Severity.high,
                    confidence=0.8,
                    title=f"Forbidden import in {norm}",
                    summary=(
                        f"{norm} imports '{bad[0]}' which violates rule "
                        f"'{rule.paths} cannot import {rule.cannot_import}'."
                        + (f" {rule.reason}" if rule.reason else "")
                    ),
                    evidence_files=[norm],
                    recommended_actions=[
                        f"Remove the dependency on '{rule.cannot_import}' from {norm}",
                    ],
                    blocking=Blocking(guarded=True, strict=True),
                )
            )
            idx += 1
    return findings
