"""Phase 2: parallel agent graph + provider output validation."""

import os
import subprocess

from codeguardian.graph.build import run_analysis
from codeguardian.models import PrContext, Provider
from codeguardian.policy import Architecture, ForbiddenImport, Mode, Policy
from codeguardian.providers import validate_summary


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


def test_validate_summary_schema():
    assert validate_summary('{"summary": "all good"}') == "all good"
    assert validate_summary('noise {"summary":"ok"} trailing') == "ok"
    assert validate_summary('{"wrong": "x"}') is None
    assert validate_summary("not json") is None
    assert validate_summary('{"summary": ""}') is None
    assert validate_summary(None) is None


def test_graph_collects_multidomain_evidence(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root = str(tmp_path)
    _git(root, "init", "-q")
    _w(root, "src/api/profile/route.ts", "export async function GET(){ return 1 }\n")
    _w(root, "prisma/schema.prisma", "model User { id Int }\n")
    _commit(root, "base")
    base = _head(root)

    # Destructive migration + API handler removed.
    _w(root, "src/api/profile/route.ts", "// handler removed\n")
    _w(root, "db/migrations/001.sql", "DROP TABLE users;\n")
    _commit(root, "risky")
    head = _head(root)

    pr = PrContext(owner="o", repo="r", number=3, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy(mode=Mode.guarded))

    categories = {f.category.value for f in report.findings}
    assert "api" in categories
    assert "database" in categories
    assert report.provider == Provider.deterministic
    assert report.risk.blocking is True
    assert all(f.evidence_files for f in report.findings)


def test_architecture_agent_runs_in_graph(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root = str(tmp_path)
    _git(root, "init", "-q")
    _w(root, "src/components/Button.tsx", "export const B = 1;\n")
    _commit(root, "base")
    base = _head(root)
    _w(root, "src/components/Button.tsx", "import { db } from '../server/db';\nexport const B = 2;\n")
    _commit(root, "violate")
    head = _head(root)

    policy = Policy(architecture=Architecture(forbidden_imports=[
        ForbiddenImport(paths="**/components/**", cannot_import="server")
    ]))
    pr = PrContext(owner="o", repo="r", number=4, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, policy)
    assert any(f.category.value == "architecture" for f in report.findings)
