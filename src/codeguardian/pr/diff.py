"""Compute the PR diff from git.

Runs `git diff --numstat`, `--name-status`, and a single full `git diff` between
base and head SHAs inside the checked-out repo, then splits the unified diff into
per-file patches (Phase 10: one `git diff` instead of one per changed file).
Falls back gracefully if git data is unavailable.
"""

from __future__ import annotations

import re
import subprocess
from typing import Optional

from ..models import DiffFile, FileStatus
from .classify import classify

_STATUS_MAP = {
    "A": FileStatus.added,
    "M": FileStatus.modified,
    "D": FileStatus.removed,
    "R": FileStatus.renamed,
    "C": FileStatus.added,
}


def _git(repo_root: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_root, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def compute_diff(repo_root: str, base_sha: str, head_sha: str) -> list[DiffFile]:
    """Return changed files with patches between base and head."""
    rng = f"{base_sha}...{head_sha}" if base_sha and head_sha else "HEAD~1...HEAD"

    numstat = _git(repo_root, "diff", "--numstat", rng)
    name_status = _git(repo_root, "diff", "--name-status", rng)
    # One full diff, split per file below (instead of a `git diff` per file).
    patches = _split_patches(_git(repo_root, "diff", rng))

    statuses: dict[str, FileStatus] = {}
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code = parts[0][:1]
        path = parts[-1]
        statuses[path] = _STATUS_MAP.get(code, FileStatus.modified)

    files: list[DiffFile] = []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_s, del_s, path = parts[0], parts[1], parts[-1]
        additions = int(add_s) if add_s.isdigit() else 0
        deletions = int(del_s) if del_s.isdigit() else 0
        files.append(
            DiffFile(
                path=path,
                status=statuses.get(path, FileStatus.modified),
                additions=additions,
                deletions=deletions,
                patch=patches.get(path),
                category=classify(path),
            )
        )
    return files


_DIFF_SPLIT_RE = re.compile(r"(?m)^(?=diff --git )")


def _split_patches(diff_text: str) -> dict[str, Optional[str]]:
    """Split a full unified diff into {path: patch} blocks."""
    patches: dict[str, Optional[str]] = {}
    if not diff_text:
        return patches
    for block in _DIFF_SPLIT_RE.split(diff_text):
        if not block.startswith("diff --git"):
            continue
        path = _path_from_block(block)
        if path:
            patches[path] = block
    return patches


def _path_from_block(block: str) -> Optional[str]:
    lines = block.splitlines()
    for line in lines:
        if line.startswith("+++ b/"):
            return line[6:]
        if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            return line[4:]
    for line in lines:  # pure deletion: no +++ b/ line
        if line.startswith("--- a/"):
            return line[6:]
    m = re.match(r"diff --git a/(.+?) b/(.+)$", lines[0]) if lines else None
    return m.group(2) if m else None
