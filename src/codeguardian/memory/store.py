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
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .record import MemoryRecord

_MEMORY_FILE = "memory.jsonl"


def compact_records(
    records: list[MemoryRecord], max_records: int, retention_days: int
) -> list[MemoryRecord]:
    """Apply retention to keep the memory branch bounded (Phase 10).

    Drops records older than ``retention_days`` (when > 0), then keeps the
    ``max_records`` most recent by ``created_at``. Order is preserved otherwise.
    """
    kept = records
    if retention_days and retention_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        out = []
        for r in kept:
            try:
                ts = datetime.fromisoformat(r.created_at)
            except (ValueError, TypeError):
                out.append(r)  # unparseable timestamp -> keep, don't lose data
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                out.append(r)
        kept = out
    if max_records and max_records > 0 and len(kept) > max_records:
        kept = kept[-max_records:]
    return kept


class MemoryStore(Protocol):
    def load(self) -> list[MemoryRecord]: ...
    def append(self, record: MemoryRecord) -> None: ...


class LocalMemoryStore:
    def __init__(self, path: str, max_records: int = 0, retention_days: int = 0):
        self.path = path
        self.max_records = max_records
        self.retention_days = retention_days

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
        records = self.load() + [record]
        if self.max_records or self.retention_days:
            compacted = compact_records(records, self.max_records, self.retention_days)
            if len(compacted) != len(records):  # rewrite only when compaction trims
                with open(self.path, "w", encoding="utf-8") as fh:
                    for r in compacted:
                        fh.write(r.model_dump_json() + "\n")
                return
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json() + "\n")


class GitBranchMemoryStore:
    """Reads/writes ``memory.jsonl`` on an orphan-ish branch via git. Best-effort:
    any git failure degrades to an empty/no-op so analysis never breaks."""

    def __init__(self, repo_root: str, branch: str, max_records: int = 0, retention_days: int = 0):
        self.repo_root = repo_root
        self.branch = branch
        self.max_records = max_records
        self.retention_days = retention_days

    def _git(self, *args: str, check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", self.repo_root, *args],
            capture_output=True, text=True, check=check,
        )

    @staticmethod
    def _git_at(cwd: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)

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
        # Only mutate git inside GitHub Actions — never touch a developer's repo
        # during a local run.
        if os.environ.get("GITHUB_ACTIONS") != "true":
            print("CodeGuardian: memory write skipped (not running in GitHub Actions).")
            return

        existing = self.load()
        records = compact_records(
            existing + [record], self.max_records, self.retention_days
        )
        content = "\n".join(r.model_dump_json() for r in records) + "\n"
        msg = f"memory: PR #{record.pr_number} @ {record.head_sha[:7]}"

        # Commit on an isolated worktree so the checked-out branch is never
        # modified. Best-effort: any failure is logged and skipped.
        wt = tempfile.mkdtemp(prefix="cg-memory-")
        try:
            has_remote = self._git("rev-parse", "--verify", f"origin/{self.branch}").returncode == 0
            if has_remote:
                self._git("worktree", "add", "-B", self.branch, wt, f"origin/{self.branch}")
            else:
                self._git("worktree", "add", "--detach", wt)
                self._git_at(wt, "checkout", "--orphan", self.branch)
                self._git_at(wt, "reset", "--hard")
            with open(os.path.join(wt, _MEMORY_FILE), "w", encoding="utf-8") as fh:
                fh.write(content)
            self._git_at(wt, "add", _MEMORY_FILE)
            self._git_at(wt, "-c", "user.email=codeguardian@users.noreply.github.com",
                         "-c", "user.name=CodeGuardian", "commit", "-m", msg)
            self._git_at(wt, "push", "origin", f"{self.branch}:{self.branch}")
        except Exception as exc:  # noqa: BLE001
            print(f"CodeGuardian: memory append skipped: {exc}")
        finally:
            self._git("worktree", "remove", "--force", wt)
