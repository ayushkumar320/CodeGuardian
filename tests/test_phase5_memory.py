import os
import subprocess

from codeguardian.graph.build import run_analysis
from codeguardian.memory.record import MemoryRecord, Signature
from codeguardian.memory.retrieve import find_similar, similarity
from codeguardian.memory.store import LocalMemoryStore
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
from codeguardian.policy import Memory, Policy


def _report(number, paths, cats=(Category.database,), score=8.0):
    findings = [
        Finding(id=f"CG-{c.value[:3].upper()}-001", category=c, severity=Severity.high,
                confidence=0.8, title="t", summary="s", evidence_files=list(paths),
                blocking=Blocking(guarded=True, strict=True))
        for c in cats
    ]
    return Report(
        pr=PrContext(owner="o", repo="r", number=number, base_sha="a", head_sha=f"sha{number}"),
        mode=Mode.guarded, provider=Provider.deterministic,
        risk=Risk(score=score, level=RiskLevel.high, confidence=0.8, blocking=True),
        affected_areas=["Database"], findings=findings,
    )


def test_history_command_parse_and_handler():
    from codeguardian.commands.handlers import history as history_reply
    from codeguardian.commands.parser import CommandName, parse

    assert parse("@codeguardian has this happened before?").name == CommandName.history
    assert parse("@codeguardian history").name == CommandName.history

    rep = _report(1, ["db/migrations/x.sql"])
    assert "No similar past PRs" in history_reply(rep)
    rep.historical_context = ["Similar to PR #9 (risk 8.0 high)"]
    assert "#9" in history_reply(rep)


def test_record_is_privacy_safe():
    rec = MemoryRecord.from_report(_report(1, ["src/api/profile/route.ts"]))
    dumped = rec.model_dump_json()
    assert "route.ts" not in dumped  # only directory granularity stored
    assert "src/api/profile" in dumped
    assert rec.blocking_finding_ids


def test_local_store_roundtrip(tmp_path):
    store = LocalMemoryStore(str(tmp_path / "memory.jsonl"))
    assert store.load() == []
    store.append(MemoryRecord.from_report(_report(1, ["src/api/profile/route.ts"])))
    store.append(MemoryRecord.from_report(_report(2, ["db/migrations/x.sql"])))
    assert len(store.load()) == 2


def test_similarity_and_retrieval():
    cur = Signature(paths={"src/api/profile"}, categories={"database", "api"})
    near = MemoryRecord.from_report(_report(7, ["src/api/profile/route.ts"], (Category.api, Category.database)))
    far = MemoryRecord.from_report(_report(8, ["src/ui/widgets/x.tsx"], (Category.dependency,)))
    assert similarity(cur, near) > similarity(cur, far)
    matches = find_similar(cur, [near, far], current_pr=99, min_similarity=0.2)
    assert matches and matches[0][0].pr_number == 7


def test_retrieval_excludes_self():
    cur = Signature(paths={"db/migrations"}, categories={"database"})
    same = MemoryRecord.from_report(_report(5, ["db/migrations/x.sql"]))
    assert find_similar(cur, [same], current_pr=5, min_similarity=0.1) == []


def test_history_node_populates_context(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root = str(tmp_path)
    subprocess.run(["git", "-C", root, "init", "-q"], check=True, capture_output=True)
    (tmp_path / "db").mkdir()
    (tmp_path / "db" / "schema.sql").write_text("CREATE TABLE users(id int);\n")
    subprocess.run(["git", "-C", root, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "base"], check=True, capture_output=True)
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    (tmp_path / "db" / "migrations").mkdir()
    (tmp_path / "db" / "migrations" / "001.sql").write_text("DROP TABLE users;\n")
    subprocess.run(["git", "-C", root, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "risky"], check=True, capture_output=True)
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    # Seed memory with a similar past PR touching db/migrations.
    store = LocalMemoryStore(str(tmp_path / "mem.jsonl"))
    store.append(MemoryRecord.from_report(_report(41, ["db/migrations/old.sql"])))

    pr = PrContext(owner="o", repo="r", number=42, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy(mode=Mode.guarded), memory_store=store)
    assert report.historical_context
    assert "#41" in report.historical_context[0]


def test_memory_disabled_by_policy(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    root = str(tmp_path)
    subprocess.run(["git", "-C", root, "init", "-q"], check=True, capture_output=True)
    (tmp_path / "a.ts").write_text("export const x=1;\n")
    subprocess.run(["git", "-C", root, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "base"], check=True, capture_output=True)
    base = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    (tmp_path / "a.ts").write_text("export const x=2;\n")
    subprocess.run(["git", "-C", root, "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "c"], check=True, capture_output=True)
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    store = LocalMemoryStore(str(tmp_path / "mem.jsonl"))
    store.append(MemoryRecord.from_report(_report(1, ["a.ts"], (Category.dependency,))))
    pr = PrContext(owner="o", repo="r", number=2, base_sha=base, head_sha=head)
    report, _ = run_analysis(root, pr, Policy(memory=Memory(enabled=False)), memory_store=store)
    assert report.historical_context == []
