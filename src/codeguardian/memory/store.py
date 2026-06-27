"""Memory persistence.

Two backends share one interface:
- LocalMemoryStore: a JSONL file (used in tests and as the on-disk format).
- GitBranchMemoryStore: an append-only JSONL file on a dedicated repo branch,
  so memory survives across runs without an external database (artifacts expire).

Records are compact and privacy-safe (see record.py); we never write source.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Protocol

from .record import MemoryRecord

_MEMORY_FILE = "memory.jsonl"


class MemoryStore(Protocol):
    def load(self) -> list[MemoryRecord]: ...
    def append(self, record: MemoryRecord) -> None: ...


class LocalMemoryStore:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> list[MemoryRecord]:
        if not os.path.isfile(self.path):
            return []
        out: list[MemoryRecord] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(MemoryRecord.model_validate_json(line))
                except ValueError:
                    continue
        return out

    def append(self, record: MemoryRecord) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json() + "\n")


class GitBranchMemoryStore:
    """Reads/writes ``memory.jsonl`` on an orphan-ish branch via git. Best-effort:
    any git failure degrades to an empty/no-op so analysis never breaks."""

    def __init__(self, repo_root: str, branch: str):
        self.repo_root = repo_root
        self.branch = branch

    def _git(self, *args: str, check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", self.repo_root, *args],
            capture_output=True, text=True, check=check,
        )

    def load(self) -> list[MemoryRecord]:
        try:
            self._git("fetch", "origin", self.branch)
            blob = self._git("show", f"origin/{self.branch}:{_MEMORY_FILE}")
        except Exception:  # noqa: BLE001
            return []
        if blob.returncode != 0:
            return []
        out: list[MemoryRecord] = []
        for line in blob.stdout.splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(MemoryRecord.model_validate_json(line))
                except ValueError:
                    continue
        return out

    def append(self, record: MemoryRecord) -> None:
        existing = self.load()
        lines = [r.model_dump_json() for r in existing] + [record.model_dump_json()]
        content = "\n".join(lines) + "\n"
        try:
            # Stage the file content onto the memory branch using a worktree-free
            # plumbing flow would be ideal; for MVP we write+commit+push directly.
            path = os.path.join(self.repo_root, _MEMORY_FILE)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            self._git("add", _MEMORY_FILE)
            self._git("-c", "user.email=codeguardian@users.noreply.github.com",
                      "-c", "user.name=CodeGuardian",
                      "commit", "-m", f"memory: PR #{record.pr_number} @ {record.head_sha[:7]}")
            self._git("push", "origin", f"HEAD:{self.branch}")
        except Exception as exc:  # noqa: BLE001
            print(f"CodeGuardian: memory append skipped: {exc}")
