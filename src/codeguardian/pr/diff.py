"""Compute the PR diff from git.

Runs `git diff --numstat` and `git diff` between base and head SHAs inside the
checked-out repo. Falls back gracefully if git data is unavailable.
"""

from __future__ import annotations

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
        patch = _file_patch(repo_root, rng, path)
        files.append(
            DiffFile(
                path=path,
                status=statuses.get(path, FileStatus.modified),
                additions=additions,
                deletions=deletions,
                patch=patch,
                category=classify(path),
            )
        )
    return files


def _file_patch(repo_root: str, rng: str, path: str) -> Optional[str]:
    out = _git(repo_root, "diff", rng, "--", path)
    return out or None
