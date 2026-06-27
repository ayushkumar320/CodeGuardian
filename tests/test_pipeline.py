"""End-to-end pipeline test using a real git repo fixture (zero model keys)."""

import os
import subprocess

from codeguardian.graph.build import run_analysis
from codeguardian.models import PrContext, Provider, RiskLevel
from codeguardian.policy import Policy
from codeguardian.report import check_conclusion


def _git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


def _commit_all(root, msg):
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", msg)


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _init_repo(tmp_path):
    root = str(tmp_path)
    _git(root, "init", "-q")
    _write(root, "src/util.ts", "export const x = 1;\n")
    _write(root, "src/a.ts", "import { x } from './util';\n")
    _commit_all(root, "base")
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    return root, base


def test_docs_only_is_low_and_quiet(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root, base = _init_repo(tmp_path)
    _write(root, "README.md", "# hello\n")
    _commit_all(root, "docs")
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    pr = PrContext(owner="o", repo="r", number=1, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy())
    assert report.risk.level == RiskLevel.low
    assert report.provider == Provider.deterministic
    assert check_conclusion(report) == "success"
    assert report.deterministic_notice is not None


def test_source_change_produces_findings(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root, base = _init_repo(tmp_path)
    _write(root, "src/util.ts", "export const x = 2;\n")
    _commit_all(root, "change util")
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    pr = PrContext(owner="o", repo="r", number=2, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy())
    assert report.findings, "expected at least one finding"
    assert all(f.evidence_files for f in report.findings)
