"""Bounded, gitignore-aware repository file enumeration (Phase 10).

Central place that decides which files CodeGuardian looks at, so the work stays
bounded on large repos and monorepos:

- prefers ``git ls-files`` (respects ``.gitignore``, only tracked files) and
  falls back to ``os.walk`` outside a git work tree;
- skips vendored/build directories and minified/generated/lockfiles;
- caps the number of files and skips files larger than a byte budget.

Keeping this dependency-light (no Policy import) so analyzers can call it; callers
pass caps in from ``policy.performance``.
"""

from __future__ import annotations

import os
import subprocess

_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", ".nuxt", ".svelte-kit",
    ".venv", "venv", "coverage", "__pycache__", ".turbo", "out", ".cache",
    "vendor", ".pytest_cache", ".mypy_cache",
}
_SKIP_SUFFIXES = (".min.js", ".min.css", ".bundle.js", ".map", ".d.ts.map")
_SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}

DEFAULT_MAX_FILES = 20000
DEFAULT_MAX_FILE_BYTES = 1_000_000


def _is_skippable(rel: str) -> bool:
    low = rel.lower()
    if any(low.endswith(s) for s in _SKIP_SUFFIXES):
        return True
    if os.path.basename(low) in _SKIP_NAMES:
        return True
    return any(part in _SKIP_DIRS for part in rel.split("/"))


def _git_tracked(repo_root: str) -> list[str] | None:
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "ls-files"],
            capture_output=True, text=True, check=True, timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout.splitlines()


def _walk_candidates(repo_root: str) -> list[str]:
    out: list[str] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            out.append(os.path.relpath(os.path.join(root, f), repo_root).replace(os.sep, "/"))
    return out


def iter_repo_files(
    repo_root: str,
    exts: tuple[str, ...] | None = None,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> list[str]:
    """Return repo-relative (forward-slash) paths, bounded and filtered.

    ``exts`` (lowercase, with leading dot) restricts to matching extensions;
    ``None`` returns all non-skipped files.
    """
    tracked = _git_tracked(repo_root)
    candidates = tracked if tracked is not None else _walk_candidates(repo_root)

    rels: list[str] = []
    for rel in candidates:
        rel = rel.replace(os.sep, "/")
        if exts and not rel.lower().endswith(exts):
            continue
        if _is_skippable(rel):
            continue
        try:
            if os.path.getsize(os.path.join(repo_root, rel)) > max_file_bytes:
                continue
        except OSError:
            continue
        rels.append(rel)
        if len(rels) >= max_files:
            break
    return rels
