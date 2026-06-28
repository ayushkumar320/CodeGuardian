"""Phase 10: the PR diff is computed with a single `git diff`, split per file."""

import os
import subprocess

import codeguardian.pr.diff as diffmod
from codeguardian.pr.diff import compute_diff


def _git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


def _write(root, rel, content):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _repo(tmp_path):
    root = str(tmp_path)
    _git(root, "init", "-q")
    _write(root, "a.ts", "export const a = 1;\n")
    _write(root, "b.ts", "export const b = 1;\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    _write(root, "a.ts", "export const a = 2;\n")
    _write(root, "b.ts", "export const b = 2;\n")
    _write(root, "c.ts", "export const c = 3;\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "change")
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    return root, base, head


def test_per_file_patches_are_split_correctly(tmp_path):
    root, base, head = _repo(tmp_path)
    files = {f.path: f for f in compute_diff(root, base, head)}
    assert set(files) == {"a.ts", "b.ts", "c.ts"}
    # each file's patch contains its own header and not another file's
    assert "a.ts" in files["a.ts"].patch and "b.ts" not in files["a.ts"].patch
    assert "+export const c = 3;" in files["c.ts"].patch


def test_single_full_diff_call_not_per_file(tmp_path, monkeypatch):
    root, base, head = _repo(tmp_path)
    calls = []
    real = diffmod._git

    def spy(repo_root, *args):
        calls.append(args)
        return real(repo_root, *args)

    monkeypatch.setattr(diffmod, "_git", spy)
    compute_diff(root, base, head)
    # exactly one full `git diff <rng>` (no `--` path-scoped diffs)
    full_diffs = [a for a in calls if a[:1] == ("diff",) and "--" not in a and "--numstat" not in a and "--name-status" not in a]
    assert len(full_diffs) == 1, full_diffs
    assert not any("--" in a for a in calls), "no per-file path-scoped git diff expected"
