"""Phase 4: policy-driven behavior (ignored_findings, service_owners) + explain category."""

import os
import subprocess

from codeguardian.commands.handlers import explain
from codeguardian.commands.parser import parse
from codeguardian.graph.build import run_analysis
from codeguardian.models import (
    Blocking,
    Category,
    Finding,
    Mode,
    PrContext,
    Provider,
    Report,
    Risk,
    RiskLevel,
    Severity,
)
from codeguardian.policy import Architecture, Mode as PMode, Policy, ServiceOwner


def _git(root, *a):
    subprocess.run(["git", "-C", root, *a], check=True, capture_output=True)


def _commit(root, msg):
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", msg)


def _w(root, rel, content):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content)


def _head(root):
    return subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def _risky_repo(tmp_path):
    root = str(tmp_path)
    _git(root, "init", "-q")
    _w(root, "db/schema.sql", "CREATE TABLE users (id int);\n")
    _commit(root, "base")
    base = _head(root)
    _w(root, "db/migrations/001.sql", "DROP TABLE users;\n")
    _commit(root, "risky")
    return root, base, _head(root)


def test_ignored_findings_excluded_from_score(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root, base, head = _risky_repo(tmp_path)
    pr = PrContext(owner="o", repo="r", number=1, base_sha=base, head_sha=head)

    baseline, _ = run_analysis(root, pr, Policy(mode=PMode.guarded))
    assert baseline.risk.blocking is True
    blocker_id = next(f.id for f in baseline.findings if f.blocking.guarded)

    suppressed, _ = run_analysis(
        root, pr, Policy(mode=PMode.guarded, ignored_findings=[blocker_id])
    )
    sup = next(f for f in suppressed.findings if f.id == blocker_id)
    assert sup.suppressed is not None
    assert sup.suppressed.by == "policy"
    # Score should drop now that the blocker is excluded.
    assert suppressed.risk.score < baseline.risk.score


def test_service_owners_recommend_reviewers(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root, base, head = _risky_repo(tmp_path)
    pr = PrContext(owner="o", repo="r", number=2, base_sha=base, head_sha=head)
    policy = Policy(service_owners=[ServiceOwner(paths="**/migrations/**", owners=["@platform/db"])])
    report, _ = run_analysis(root, pr, policy)
    assert "@platform/db" in report.reviewers


def test_explain_category_parses_and_filters():
    cmd = parse("@codeguardian explain database risk")
    assert cmd.category == "database"

    report = Report(
        pr=PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b"),
        mode=Mode.guarded, provider=Provider.deterministic,
        risk=Risk(score=7.0, level=RiskLevel.high, confidence=0.8, blocking=True),
        findings=[
            Finding(id="CG-DB-001", category=Category.database, severity=Severity.high,
                    confidence=0.8, title="db thing", summary="s", evidence_files=["x.sql"]),
            Finding(id="CG-API-001", category=Category.api, severity=Severity.high,
                    confidence=0.8, title="api thing", summary="s", evidence_files=["y.ts"]),
        ],
    )
    out = explain(report, "database")
    assert "CG-DB-001" in out and "CG-API-001" not in out
