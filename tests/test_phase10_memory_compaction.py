"""Phase 10: memory retention keeps the store bounded."""

from datetime import datetime, timedelta, timezone

from codeguardian.memory.record import MemoryRecord
from codeguardian.memory.store import LocalMemoryStore, compact_records


def _rec(n: int, age_days: int = 0) -> MemoryRecord:
    ts = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return MemoryRecord(
        pr_number=n, head_sha=f"sha{n}", risk_score=1.0, risk_level="low", created_at=ts
    )


def test_compact_caps_to_max_records_keeping_recent():
    recs = [_rec(i) for i in range(10)]
    kept = compact_records(recs, max_records=4, retention_days=0)
    assert [r.pr_number for r in kept] == [6, 7, 8, 9]


def test_compact_drops_old_records():
    recs = [_rec(1, age_days=400), _rec(2, age_days=10), _rec(3, age_days=1)]
    kept = compact_records(recs, max_records=0, retention_days=180)
    assert [r.pr_number for r in kept] == [2, 3]


def test_compact_keeps_unparseable_timestamps():
    r = _rec(1)
    r.created_at = "not-a-date"
    kept = compact_records([r], max_records=0, retention_days=180)
    assert len(kept) == 1


def test_local_store_compacts_on_append(tmp_path):
    path = str(tmp_path / "memory.jsonl")
    store = LocalMemoryStore(path, max_records=3, retention_days=0)
    for i in range(6):
        store.append(_rec(i))
    loaded = store.load()
    assert len(loaded) == 3
    assert [r.pr_number for r in loaded] == [3, 4, 5]
