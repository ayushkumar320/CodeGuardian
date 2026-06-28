"""Phase 10: bounded, gitignore-aware repo enumeration."""

import os
import subprocess

from codeguardian.walk import iter_repo_files


def _write(root, rel, content="x"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def test_skips_vendored_and_minified(tmp_path):
    root = str(tmp_path)
    _write(root, "src/a.ts", "export const a = 1;")
    _write(root, "node_modules/dep/index.js", "module.exports = {}")
    _write(root, "dist/bundle.min.js", "var a=1")
    _write(root, "src/x.min.js", "var x=1")
    files = iter_repo_files(root, (".ts", ".js"))
    assert "src/a.ts" in files
    assert all("node_modules" not in f for f in files)
    assert all(not f.endswith(".min.js") for f in files)
    assert all("dist/" not in f for f in files)


def test_respects_gitignore_when_tracked(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "-C", root, "init", "-q"], check=True)
    _write(root, ".gitignore", "ignored/\n")
    _write(root, "src/a.ts", "export const a = 1;")
    _write(root, "ignored/secret.ts", "export const s = 1;")
    subprocess.run(["git", "-C", root, "add", "-A"], check=True, capture_output=True)
    files = iter_repo_files(root, (".ts",))
    assert "src/a.ts" in files
    assert "ignored/secret.ts" not in files  # gitignored -> not tracked -> skipped


def test_max_files_cap(tmp_path):
    root = str(tmp_path)
    for i in range(10):
        _write(root, f"src/f{i}.ts", "export const x = 1;")
    files = iter_repo_files(root, (".ts",), max_files=4)
    assert len(files) == 4


def test_max_file_bytes_skips_large(tmp_path):
    root = str(tmp_path)
    _write(root, "src/small.ts", "export const a = 1;")
    _write(root, "src/big.ts", "x" * 5000)
    files = iter_repo_files(root, (".ts",), max_file_bytes=1000)
    assert "src/small.ts" in files
    assert "src/big.ts" not in files
