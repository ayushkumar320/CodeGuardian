"""Phase 12 (dynamic-across-languages tier): repos in languages we don't deeply
analyze still get *something useful* — PR-shape findings + an honest note about
degraded mode. Strict rule #2 stays in force: no fabricated findings.
"""

import os
import subprocess

from codeguardian.analyzers import pr_shape as pr_shape_analyzer
from codeguardian.graph.build import run_analysis
from codeguardian.languages import LanguageReport, detect, supports
from codeguardian.models import (
    Category,
    DiffFile,
    FileCategory,
    FileStatus,
    PrContext,
)
from codeguardian.policy import Policy, PrShape


def _df(path, additions=1, deletions=0):
    return DiffFile(
        path=path, status=FileStatus.modified,
        additions=additions, deletions=deletions, patch=None,
        category=FileCategory.backend,
    )


# --- language detection / support matrix --------------------------------------
def test_support_matrix_known_languages():
    assert supports("TypeScript", "import_graph")
    assert supports("Python", "import_graph")
    assert supports("Python", "test_conventions")
    # Python deliberately does NOT have types/api/db yet
    assert not supports("Python", "types")
    assert not supports("Python", "database")
    # Go: no entry yet -> nothing supported
    assert not supports("Go", "import_graph")


def test_detect_reports_changed_and_unsupported_languages():
    lr: LanguageReport = detect(
        language_summary={".go": 12, ".py": 3, ".md": 2},
        changed_paths=["cmd/server/main.go", "pkg/util.go", "README.md"],
    )
    assert lr.primary == "Go"
    assert "Go" in lr.repo_languages and "Python" in lr.repo_languages
    assert lr.changed_languages == ["Go"]
    assert lr.unsupported_in_pr == ["Go"]
    assert lr.fully_unsupported_pr is True


def test_detect_partial_support_when_mixed():
    lr = detect(
        language_summary={".ts": 10, ".go": 4},
        changed_paths=["src/util.ts", "cmd/main.go"],
    )
    assert set(lr.changed_languages) == {"TypeScript", "Go"}
    assert lr.unsupported_in_pr == ["Go"]
    assert lr.fully_unsupported_pr is False  # TS is supported


# --- PR-shape analyzer --------------------------------------------------------
def test_large_pr_finding_fires():
    cfg = PrShape(large_pr_files=10)
    diff = [_df(f"src/f{i}.go", additions=2) for i in range(15)]
    findings = pr_shape_analyzer.analyze(diff, cfg)
    titles = [f.title for f in findings]
    assert any("Large PR" in t and "15 files" in t for t in titles), titles
    f = next(x for x in findings if "Large PR" in x.title)
    assert f.category == Category.pr_shape
    assert f.evidence_files  # never empty


def test_deletion_heavy_pr_finding_fires():
    cfg = PrShape(deletion_heavy_min_net_removed=50)
    diff = [
        _df("a.rs", additions=2, deletions=80),   # net -78
        _df("b.rs", additions=1, deletions=2),    # not deletion-heavy
    ]
    findings = pr_shape_analyzer.analyze(diff, cfg)
    titles = [f.title for f in findings]
    assert any("Deletion-heavy" in t for t in titles), titles


def test_small_balanced_pr_produces_no_pr_shape_findings():
    cfg = PrShape()  # defaults: 50 files / 200 net deletions
    diff = [_df("src/foo.go", additions=10, deletions=5)]
    assert pr_shape_analyzer.analyze(diff, cfg) == []


def test_pr_shape_disabled():
    cfg = PrShape(enabled=False, large_pr_files=1)
    diff = [_df("x.go", 10) for _ in range(50)]
    assert pr_shape_analyzer.analyze(diff, cfg) == []


# --- End-to-end on an unsupported-language repo -------------------------------
def _git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def test_go_only_repo_gets_degraded_note_and_pr_shape_findings(tmp_path, monkeypatch):
    """A Go repo with no Python/TS at all: we must (a) not crash, (b) tell the
    user it's degraded mode, (c) still flag a clearly-oversized PR."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    root = str(tmp_path)
    _git(root, "init", "-q")
    # Baseline: a small Go repo
    _write(root, "go.mod", "module example.com/x\n")
    _write(root, "cmd/server/main.go", "package main\nfunc main() {}\n")
    _write(root, "pkg/util.go", "package pkg\nfunc X() int { return 1 }\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    # Change: a deliberately large PR — many new Go files
    for i in range(60):
        _write(root, f"pkg/big{i}.go", "package pkg\n// generated\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "big")
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    pr = PrContext(owner="o", repo="r", number=1, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy())

    # (a) it didn't crash; (b) honest note about degraded mode
    assert any("Language-agnostic" in n for n in report.notes), report.notes
    # (c) pr-shape large-PR finding still fires (language-agnostic)
    assert any(f.category == Category.pr_shape for f in report.active_findings()), \
        [(f.category.value, f.title) for f in report.findings]
