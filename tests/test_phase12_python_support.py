"""Phase 12 (MVP-scope expansion): Python support for the dependency + tests
analyzers, plus path/file classification.

Out of scope here (deliberately deferred): Python typing-breaking-change
detection (Protocol/TypedDict/dataclass), Python web-framework API contract,
SQLAlchemy/Django ORM migration risk.
"""

import os
import subprocess

from codeguardian.analyzers.imports import build_import_graph
from codeguardian.analyzers import tests as tests_analyzer
from codeguardian.graph.build import run_analysis
from codeguardian.models import (
    DiffFile,
    FileCategory,
    FileStatus,
    PrContext,
    RiskLevel,
)
from codeguardian.policy import Policy
from codeguardian.pr.classify import classify


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


# --- classification -----------------------------------------------------------
def test_python_files_classify_as_backend():
    assert classify("src/codeguardian/policy.py") == FileCategory.backend


def test_python_test_files_classify_as_test():
    assert classify("tests/test_foo.py") == FileCategory.test
    assert classify("src/pkg/foo_test.py") == FileCategory.test


# --- import graph -------------------------------------------------------------
def test_python_relative_imports_resolve(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/util.py", "def x(): pass\n")
    _write(root, "pkg/scoreboard.py", "from .util import x\n")
    _write(root, "pkg/sub/__init__.py", "")
    _write(root, "pkg/sub/leaf.py", "from ..util import x\n")
    g = build_import_graph(root)
    assert g.reverse["pkg/util.py"] == {"pkg/scoreboard.py", "pkg/sub/leaf.py"}
    assert g.forward["pkg/scoreboard.py"] == {"pkg/util.py"}


def test_python_absolute_imports_resolve_repo_root_and_src(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/core.py", "VALUE = 1\n")
    _write(root, "app/main.py", "from pkg.core import VALUE\nimport pkg.core\n")
    # `src` layout: pkg under src/
    _write(root, "src/srvc/__init__.py", "")
    _write(root, "src/srvc/db.py", "URL = ''\n")
    _write(root, "app/dao.py", "from srvc.db import URL\n")
    g = build_import_graph(root)
    assert "app/main.py" in g.reverse["pkg/core.py"]
    assert "app/dao.py" in g.reverse["src/srvc/db.py"]


def test_python_external_imports_are_ignored(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/x.py", "import os\nimport requests\nfrom typing import Optional\n")
    g = build_import_graph(root)
    assert g.forward["pkg/x.py"] == set()  # no local target


def test_ts_imports_still_work_alongside_python(tmp_path):
    """Adding Python must not break the TS path."""
    root = str(tmp_path)
    _write(root, "src/util.ts", "export const x = 1;\n")
    _write(root, "src/a.ts", "import { x } from './util';\n")
    _write(root, "pkg/util.py", "X = 1\n")
    _write(root, "pkg/a.py", "from .util import X\n")
    g = build_import_graph(root)
    assert g.reverse["src/util.ts"] == {"src/a.ts"}
    assert g.reverse["pkg/util.py"] == {"pkg/a.py"}


# --- tests analyzer -----------------------------------------------------------
def test_python_candidate_test_paths():
    paths = tests_analyzer._candidate_tests("pkg/util.py")
    assert "pkg/test_util.py" in paths
    assert "pkg/util_test.py" in paths
    assert "pkg/tests/test_util.py" in paths


def test_python_missing_coverage_finding_fires(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/business.py", "def charge(): pass\n")  # no test_business.py
    diff = [DiffFile(
        path="pkg/business.py", status=FileStatus.modified,
        additions=1, deletions=0, patch=None, category=FileCategory.backend,
    )]
    findings = tests_analyzer.analyze(root, diff)
    ids = [f.title for f in findings]
    assert any("No test found" in t for t in ids), findings


def test_python_impacted_tests_finding_fires(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/business.py", "def charge(): pass\n")
    _write(root, "pkg/test_business.py", "from .business import charge\n")
    diff = [DiffFile(
        path="pkg/business.py", status=FileStatus.modified,
        additions=1, deletions=0, patch=None, category=FileCategory.backend,
    )]
    findings = tests_analyzer.analyze(root, diff)
    titles = [f.title for f in findings]
    # impacted-test branch should win over missing-coverage
    assert any("test(s) impacted" in t for t in titles), findings


# --- end-to-end (deterministic) ----------------------------------------------
def test_python_only_repo_produces_dependency_finding(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    root = str(tmp_path)
    _git(root, "init", "-q")
    _write(root, "pkg/__init__.py", "")
    _write(root, "pkg/util.py", "X = 1\n")
    _write(root, "pkg/a.py", "from .util import X\n")
    _write(root, "pkg/b.py", "from .util import X\n")
    _write(root, "pkg/c.py", "from .util import X\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    _write(root, "pkg/util.py", "X = 2\n")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "change")
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    pr = PrContext(owner="o", repo="r", number=1, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy())
    # Three Python files import pkg/util.py -> dependency finding must fire.
    assert any(f.category.value == "dependency" for f in report.active_findings()), \
        [f.title for f in report.findings]
    assert report.risk.level != RiskLevel.low or report.active_findings()
