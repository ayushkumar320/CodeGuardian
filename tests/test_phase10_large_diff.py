"""Phase 10: large diffs are capped with a clear, user-visible note."""

from codeguardian.graph.nodes import collect_pr_context
from codeguardian.models import DiffFile, FileCategory, FileStatus, PrContext
from codeguardian.policy import Policy


def _diff_file(i: int, size: int) -> DiffFile:
    return DiffFile(
        path=f"src/f{i}.ts",
        status=FileStatus.modified,
        additions=size,
        deletions=0,
        patch=None,
        category=FileCategory.backend,
    )


def test_large_diff_is_capped_and_noted(monkeypatch):
    policy = Policy()
    policy.performance.max_diff_files = 5
    # 20 changed files, ascending size; the cap should keep the 5 largest.
    files = [_diff_file(i, size=i) for i in range(20)]

    import codeguardian.graph.nodes as nodes
    monkeypatch.setattr(nodes, "compute_diff", lambda *a, **k: files)

    pr = PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b")
    out = collect_pr_context({"pr": pr, "repo_root": ".", "policy": policy})

    assert len(out["diff"]) == 5
    kept = {f.additions for f in out["diff"]}
    assert kept == {15, 16, 17, 18, 19}  # top 5 by size
    assert out["notes"], "a truncation note should be present"
    assert "20 files" in out["notes"][0] and "top 5" in out["notes"][0]


def test_small_diff_has_no_note(monkeypatch):
    policy = Policy()
    files = [_diff_file(i, size=1) for i in range(3)]
    import codeguardian.graph.nodes as nodes
    monkeypatch.setattr(nodes, "compute_diff", lambda *a, **k: files)
    pr = PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b")
    out = collect_pr_context({"pr": pr, "repo_root": ".", "policy": policy})
    assert len(out["diff"]) == 3
    assert out["notes"] == []
