"""Tests for the post-v1 improvement-plan items (doc/IMPROVEMENT-PLAN.md).

Grouped by plan ID so each block maps back to a backlog item.
"""

from codeguardian.models import (
    Blocking, Category, DiffFile, DiffSummaryFile, FileStatus, Finding, Mode,
    PrContext, Provider, Report, Risk, RiskLevel, Severity,
)
from codeguardian.policy import Policy
from codeguardian import calibrate
from codeguardian import report as report_mod
from codeguardian.commands import handlers
from codeguardian.commands.parser import CommandName, parse
from codeguardian.graph.agents import _build_diff_summary
from codeguardian.pr.diff import split_hunks


def _finding(fid="CG-DEP-001", category=Category.dependency,
             sev=Severity.medium, conf=0.8, evidence=None):
    return Finding(
        id=fid, category=category, severity=sev, confidence=conf,
        title=f"{fid} title", summary="s",
        evidence_files=evidence or ["pkg/board.py"],
        recommended_actions=["Review the change"],
        blocking=Blocking(),
    )


def _report(findings=None, narrative_provider=Provider.deterministic, score=3.4,
            level=RiskLevel.medium, blocking=False):
    return Report(
        pr=PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b"),
        mode=Mode.advisory,
        provider=narrative_provider,
        risk=Risk(score=score, level=level, confidence=0.7, blocking=blocking),
        findings=findings or [],
        affected_areas=["Backend"],
    )


def _diff(path, patch, status=FileStatus.modified):
    return DiffFile(path=path, status=status, additions=1, deletions=0, patch=patch)


# --- P2-6: confidence calibration --------------------------------------------
def test_calibrate_lowers_confidence_for_whitespace_only_change():
    f = _finding(conf=0.8, evidence=["pkg/board.py"])
    patch = (
        "diff --git a/pkg/board.py b/pkg/board.py\n"
        "--- a/pkg/board.py\n+++ b/pkg/board.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def f():\n"
        "+    \n"          # whitespace-only added line
        "     return 1\n"
    )
    calibrate.calibrate_confidence([f], [_diff("pkg/board.py", patch)])
    assert f.confidence == 0.6  # 0.8 - 0.2


def test_calibrate_lowers_confidence_for_comment_only_change():
    f = _finding(conf=0.7, evidence=["pkg/board.py"])
    patch = (
        "diff --git a/pkg/board.py b/pkg/board.py\n"
        "--- a/pkg/board.py\n+++ b/pkg/board.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def f():\n"
        "+    # explain the return\n"
        "     return 1\n"
    )
    calibrate.calibrate_confidence([f], [_diff("pkg/board.py", patch)])
    assert f.confidence == 0.5


def test_calibrate_leaves_substantive_change_untouched():
    f = _finding(conf=0.8, evidence=["pkg/board.py"])
    patch = (
        "diff --git a/pkg/board.py b/pkg/board.py\n"
        "--- a/pkg/board.py\n+++ b/pkg/board.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-def old_name():\n"
        "+def new_name():\n"
    )
    calibrate.calibrate_confidence([f], [_diff("pkg/board.py", patch)])
    assert f.confidence == 0.8  # real signature change — unchanged


def test_calibrate_skips_finding_with_no_evidence_in_diff():
    f = _finding(conf=0.8, evidence=["pkg/untouched.py"])
    patch = "diff --git a/other.py b/other.py\n+    \n"
    calibrate.calibrate_confidence([f], [_diff("other.py", patch)])
    assert f.confidence == 0.8  # can't judge surgicality -> leave it


def test_calibrate_only_when_all_evidence_trivial():
    """A finding spanning a trivial file AND a substantive file is NOT lowered —
    the substantive edit is enough to keep full confidence."""
    f = _finding(conf=0.8, evidence=["pkg/a.py", "pkg/b.py"])
    trivial = "diff --git a/pkg/a.py b/pkg/a.py\n--- a/pkg/a.py\n+++ b/pkg/a.py\n+    # note\n"
    real = "diff --git a/pkg/b.py b/pkg/b.py\n--- a/pkg/b.py\n+++ b/pkg/b.py\n+x = compute()\n"
    calibrate.calibrate_confidence([f], [_diff("pkg/a.py", trivial), _diff("pkg/b.py", real)])
    assert f.confidence == 0.8


# --- P1-5: check title --------------------------------------------------------
def test_check_title_includes_score_and_narrative_snippet():
    r = _report(score=8.0, level=RiskLevel.critical, blocking=True)
    title = report_mod.check_title(r, "**Splits board ops into pkg/board.py**; 2 modules import it.")
    assert title.startswith("8.0/10 critical — blocked")
    assert "Splits board ops" in title
    assert "**" not in title  # markdown stripped


def test_check_title_falls_back_without_narrative():
    r = _report(score=2.0, level=RiskLevel.low)
    title = report_mod.check_title(r, "")
    assert title == "2.0/10 low — allowed"


def test_check_title_is_length_bounded():
    r = _report()
    long_narrative = "word " * 200
    title = report_mod.check_title(r, long_narrative)
    assert len(title) <= 115


# --- P2-5: cost telemetry -----------------------------------------------------
def test_usage_footer_counts_billable_providers():
    r = _report()
    r.provider_usage = [
        "dependency_agent:deterministic",
        "test_impact_agent:deterministic",
        "summary:groq",
    ]
    footer = report_mod.usage_footer(r)
    assert "groq×1" in footer
    assert "deterministic" not in footer  # zero-key steps aren't billable


def test_usage_footer_empty_when_all_deterministic():
    r = _report()
    r.provider_usage = ["dependency_agent:deterministic", "summary:deterministic"]
    assert report_mod.usage_footer(r) == ""


def test_check_summary_shows_footer_only_when_billable():
    r = _report(findings=[_finding()])
    r.provider_usage = ["summary:groq"]
    assert "Model calls this run" in report_mod.check_summary(r, Policy())
    r.provider_usage = ["summary:deterministic"]
    assert "Model calls this run" not in report_mod.check_summary(r, Policy())


# --- P1-6: smart patch budgeting ---------------------------------------------
_TWO_HUNK_PATCH = (
    "diff --git a/pkg/board.py b/pkg/board.py\n"
    "--- a/pkg/board.py\n+++ b/pkg/board.py\n"
    "@@ -1,3 +1,3 @@\n"
    " import os\n-x = 1\n+x = 2\n"
    "@@ -40,2 +40,3 @@\n"
    " def deep():\n+    renamed_symbol()\n"
)


def test_split_hunks_separates_header_and_hunks():
    header, hunks = split_hunks(_TWO_HUNK_PATCH)
    assert "diff --git" in header
    assert len(hunks) == 2
    assert hunks[0].startswith("@@ -1,3 +1,3 @@")
    assert "renamed_symbol" in hunks[1]


def test_build_diff_summary_keeps_hunks_for_flagged_files():
    diff = [DiffFile(path="pkg/board.py", status=FileStatus.modified,
                     additions=2, deletions=1, patch=_TWO_HUNK_PATCH)]
    out = _build_diff_summary(diff, flagged_paths={"pkg/board.py"})
    assert out[0].relevant_hunks  # populated for the flagged file
    assert any("renamed_symbol" in h for h in out[0].relevant_hunks)


def test_build_diff_summary_no_hunks_for_unflagged_files():
    diff = [DiffFile(path="pkg/other.py", status=FileStatus.modified,
                     additions=2, deletions=1, patch=_TWO_HUNK_PATCH)]
    out = _build_diff_summary(diff, flagged_paths=set())
    assert out[0].relevant_hunks == []
    assert out[0].patch_excerpt  # still gets the truncated excerpt


# --- P2-4: /codeguardian show -------------------------------------------------
def _report_with_diff():
    r = _report(findings=[_finding(evidence=["pkg/board.py"])])
    r.diff_summary = [
        DiffSummaryFile(
            path="pkg/board.py", status=FileStatus.added,
            additions=10, deletions=0,
            relevant_hunks=["@@ -0,0 +1,2 @@\n+def empty_board():\n+    return []\n"],
        ),
    ]
    return r


def test_parse_show_command_captures_target():
    c = parse("/codeguardian show pkg/Board.py")
    assert c.name == CommandName.show
    assert c.target == "pkg/Board.py"  # original case preserved


def test_parse_show_without_target():
    c = parse("/codeguardian show")
    assert c.name == CommandName.show
    assert c.target is None


def test_show_renders_hunks_and_findings_for_path():
    reply = handlers.show(_report_with_diff(), "board.py")
    assert "pkg/board.py" in reply
    assert "empty_board" in reply
    assert "```diff" in reply
    assert "CG-DEP-001" in reply  # finding for this path surfaced


def test_show_matches_symbol_inside_hunk():
    reply = handlers.show(_report_with_diff(), "empty_board")
    assert "pkg/board.py" in reply


def test_show_no_match_is_explicit():
    reply = handlers.show(_report_with_diff(), "nonexistent_thing")
    assert "No changed file or symbol matching" in reply


def test_show_without_target_shows_usage():
    assert "Usage:" in handlers.show(_report_with_diff(), None)


# --- P1-2: inline annotations -------------------------------------------------
from codeguardian.policy import NoiseBudget
from codeguardian.pr.diff import first_added_line

_ANNOTATABLE_HUNK = "@@ -0,0 +12,2 @@\n+def empty_board():\n+    return []\n"


def _annotatable_report():
    f = _finding(fid="CG-ARCH-001", category=Category.architecture,
                 sev=Severity.high, conf=0.8, evidence=["pkg/board.py"])
    r = _report(findings=[f])
    r.diff_summary = [DiffSummaryFile(
        path="pkg/board.py", status=FileStatus.added, additions=2, deletions=0,
        relevant_hunks=[_ANNOTATABLE_HUNK],
    )]
    return r


def test_first_added_line_resolves_new_file_line():
    assert first_added_line(_ANNOTATABLE_HUNK) == 12


def test_first_added_line_none_without_addition():
    assert first_added_line("@@ -1,2 +1,1 @@\n-removed only\n") is None


def test_annotations_opt_in_required():
    r = _annotatable_report()
    assert report_mod.annotations_from_report(r, Policy()) == []  # default off


def test_annotations_built_for_qualifying_finding():
    r = _annotatable_report()
    pol = Policy(noise=NoiseBudget(allow_inline_annotations=True))
    anns = report_mod.annotations_from_report(r, pol)
    assert len(anns) == 1
    a = anns[0]
    assert a["path"] == "pkg/board.py"
    assert a["start_line"] == 12
    assert a["annotation_level"] == "failure"  # high severity
    assert "CG-ARCH-001" in a["title"]


def test_annotations_skip_low_confidence_and_multi_file():
    pol = Policy(noise=NoiseBudget(allow_inline_annotations=True))
    # low confidence
    r1 = _annotatable_report()
    r1.findings[0].confidence = 0.5
    assert report_mod.annotations_from_report(r1, pol) == []
    # more than one evidence file -> not localized
    r2 = _annotatable_report()
    r2.findings[0].evidence_files = ["pkg/board.py", "pkg/game.py"]
    assert report_mod.annotations_from_report(r2, pol) == []


def test_publish_check_sends_annotations(monkeypatch):
    from codeguardian.github.client import GitHubClient
    captured = {}

    class _Resp:
        status_code = 200
        headers = {}
        def raise_for_status(self): return None
        def json(self): return {"id": 1}

    def fake_req(method, url, headers=None, params=None, json=None, timeout=None):
        if method == "GET":
            return type("R", (), {"raise_for_status": lambda s: None,
                                  "json": lambda s: {"check_runs": []}, "headers": {},
                                  "status_code": 200})()
        captured["body"] = json
        return _Resp()

    monkeypatch.setattr("codeguardian.http.requests.request", fake_req)
    client = GitHubClient(token="t")
    anns = [{"path": "a.py", "start_line": 1, "end_line": 1,
             "annotation_level": "warning", "title": "t", "message": "m"}]
    client.publish_check("o", "r", "sha", "neutral", "title", "summary", annotations=anns)
    assert captured["body"]["output"]["annotations"][0]["path"] == "a.py"


# --- P1-3: reaction feedback --------------------------------------------------
def test_feedback_footer_in_sticky_comment():
    r = _report(findings=[_finding()])
    body = report_mod.sticky_comment(r, Policy(), "narrative")
    assert "React on this comment" in body


def test_reaction_tally_buckets_reactions():
    reactions = [
        {"content": "+1"}, {"content": "+1"}, {"content": "-1"},
        {"content": "confused"}, {"content": "hooray"}, {"content": "rocket"},
    ]
    tally = report_mod.reaction_tally(reactions)
    assert tally == {"helpful": 2, "not_useful": 1, "confusing": 1, "caught_bug": 1}


def test_list_comment_reactions_parses(monkeypatch):
    from codeguardian.github.client import GitHubClient

    def fake_get(method, url, headers=None, params=None, timeout=None):
        class R:
            def raise_for_status(self): return None
            def json(self): return [{"content": "+1"}, {"content": "hooray"}]
            headers = {}
            status_code = 200
        return R()

    monkeypatch.setattr("codeguardian.http.requests.request", fake_get)
    client = GitHubClient(token="t")
    reactions = client.list_comment_reactions("o", "r", 99)
    assert report_mod.reaction_tally(reactions) == {"helpful": 1, "caught_bug": 1}


# --- P1-1: conversation memory across asks ------------------------------------
from codeguardian.commands.loop import load_recent_asks, reply_marker
from codeguardian.commands import handlers as _handlers
from codeguardian import providers


class _FakeClient:
    def __init__(self, comments):
        self._comments = comments

    def list_issue_comments(self, owner, repo, number):
        return self._comments


def test_load_recent_asks_pairs_question_with_reply():
    comments = [
        {"id": 1, "body": "/codeguardian what changed?"},
        {"id": 2, "body": f"{reply_marker(1)}\nWe split board.py out."},
        {"id": 3, "body": "/codeguardian expand on the second point"},
        {"id": 4, "body": f"{reply_marker(3)}\nThe second point was about imports."},
        {"id": 5, "body": "just a normal human comment, no mention"},
    ]
    pairs = load_recent_asks(_FakeClient(comments), "o", "r", 1)
    assert len(pairs) == 2
    assert pairs[0] == {"q": "what changed?", "a": "We split board.py out."}
    assert pairs[1]["q"] == "expand on the second point"


def test_load_recent_asks_ignores_non_ask_questions():
    comments = [
        {"id": 1, "body": "/codeguardian explain"},  # a known command, not ask
        {"id": 2, "body": f"{reply_marker(1)}\nHere is the explanation."},
    ]
    assert load_recent_asks(_FakeClient(comments), "o", "r", 1) == []


def test_load_recent_asks_caps_to_n():
    comments = []
    for i in range(1, 21, 2):
        comments.append({"id": i, "body": f"/codeguardian question {i}"})
        comments.append({"id": i + 1, "body": f"{reply_marker(i)}\nanswer {i}"})
    pairs = load_recent_asks(_FakeClient(comments), "o", "r", 1, n=3)
    assert len(pairs) == 3
    assert pairs[-1]["q"] == "question 19"  # most recent kept


def test_previous_qa_flows_into_prompt(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    captured = {}
    monkeypatch.setattr(
        providers, "_try_groq",
        lambda prompt, env, **kw: (captured.setdefault("p", prompt), '{"summary": "ok"}')[1],
    )
    prev = [{"q": "what changed?", "a": "we split board.py"}]
    _handlers.ask(_report(findings=[_finding()]), "expand on that", previous_qa=prev)
    assert "previous_qa" in captured["p"]
    assert "we split board.py" in captured["p"]


# --- P1-4: import graph cache -------------------------------------------------
import os as _os
from codeguardian.analyzers import graph_cache
from codeguardian.analyzers.imports import ImportGraph, build_import_graph


def _write(root, rel, content):
    p = _os.path.join(root, rel)
    _os.makedirs(_os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(content)


def test_graph_cache_roundtrip(tmp_path):
    g = ImportGraph(forward={"a.py": {"b.py"}, "b.py": set()},
                    reverse={"b.py": {"a.py"}, "a.py": set()})
    path = str(tmp_path / "graph-cache.json")
    assert graph_cache.save_graph(path, g)
    loaded = graph_cache.load_graph(path)
    assert loaded.forward == {"a.py": {"b.py"}, "b.py": set()}
    # Reverse is derived, not stored, but must match.
    assert loaded.reverse["b.py"] == {"a.py"}


def test_graph_cache_invalidates_on_version_mismatch():
    data = {"cache_version": 1, "analyzer_version": "not-the-real-version",
            "built_at": __import__("time").time(), "forward": {"a.py": []}}
    assert graph_cache.deserialize_graph(data) is None


def test_graph_cache_invalidates_when_aged_out():
    from codeguardian import ANALYZER_VERSION
    old = __import__("time").time() - 100 * 86400
    data = {"cache_version": 1, "analyzer_version": ANALYZER_VERSION,
            "built_at": old, "forward": {"a.py": []}}
    assert graph_cache.deserialize_graph(data, max_age_days=30) is None
    # Fresh enough -> loads.
    data["built_at"] = __import__("time").time()
    assert graph_cache.deserialize_graph(data, max_age_days=30) is not None


def test_patch_graph_matches_full_rebuild(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/a.py", "from .b import x\n")
    _write(root, "pkg/b.py", "y = 1\n")
    _write(root, "pkg/__init__.py", "")
    full_before = build_import_graph(root)

    # Now change a.py to import c instead of b, and add c.py.
    _write(root, "pkg/a.py", "from .c import x\n")
    _write(root, "pkg/c.py", "z = 1\n")
    from codeguardian.models import DiffFile, FileStatus
    changed = [
        DiffFile(path="pkg/a.py", status=FileStatus.modified),
        DiffFile(path="pkg/c.py", status=FileStatus.added),
    ]
    patched = graph_cache.patch_graph(full_before, root, changed)
    full_after = build_import_graph(root)
    # The patched edge a->c must match a true rebuild for the changed files.
    assert patched.forward["pkg/a.py"] == full_after.forward["pkg/a.py"]
    assert "pkg/a.py" in patched.reverse["pkg/c.py"]
    assert "pkg/a.py" not in patched.reverse.get("pkg/b.py", set())


def test_patch_graph_handles_removal(tmp_path):
    root = str(tmp_path)
    _write(root, "pkg/a.py", "from .b import x\n")
    _write(root, "pkg/b.py", "y = 1\n")
    _write(root, "pkg/__init__.py", "")
    g = build_import_graph(root)
    assert "pkg/a.py" in g.reverse["pkg/b.py"]
    from codeguardian.models import DiffFile, FileStatus
    # Remove a.py entirely.
    graph_cache.patch_graph(g, root, [DiffFile(path="pkg/a.py", status=FileStatus.removed)])
    assert "pkg/a.py" not in g.forward
    assert "pkg/a.py" not in g.reverse.get("pkg/b.py", set())


# --- P2-2: Go support (imports + tests) ---------------------------------------
from codeguardian.analyzers import imports as imports_analyzer
from codeguardian.analyzers import tests as tests_analyzer


def _go_repo(tmp_path):
    root = str(tmp_path)
    _write(root, "go.mod", "module github.com/acme/app\n\ngo 1.21\n")
    _write(root, "board/board.go", "package board\n\nfunc Empty() {}\n")
    _write(root, "game/game.go",
           'package game\n\nimport (\n\t"fmt"\n\t"github.com/acme/app/board"\n)\n\nfunc Run() { fmt.Println(board.Empty()) }\n')
    return root


def test_go_module_path_parsed(tmp_path):
    root = _go_repo(tmp_path)
    assert imports_analyzer._go_module_path(root) == "github.com/acme/app"


def test_go_import_graph_resolves_local_package(tmp_path):
    root = _go_repo(tmp_path)
    g = imports_analyzer.build_import_graph(root)
    # game.go imports the board package -> edge to board/board.go.
    assert "board/board.go" in g.forward["game/game.go"]
    # stdlib "fmt" is not a repo file -> no spurious edge.
    assert all(not t.startswith("fmt") for t in g.forward["game/game.go"])
    # reverse blast radius: changing board.go affects game.go.
    assert "game/game.go" in g.reverse["board/board.go"]


def test_go_dependency_finding_from_blast_radius(tmp_path):
    root = _go_repo(tmp_path)
    g = imports_analyzer.build_import_graph(root)
    from codeguardian.models import DiffFile, FileStatus
    changed = [DiffFile(path="board/board.go", status=FileStatus.modified)]
    findings = imports_analyzer.analyze(root, changed, high_risk_paths=[], graph=g)
    assert any("board/board.go" in f.evidence_files for f in findings)


def test_go_test_convention_detected():
    assert tests_analyzer._is_test_path("board/board_test.go") is True
    assert tests_analyzer._is_test_path("board/board.go") is False
    assert tests_analyzer._candidate_tests("board/board.go") == ["board/board_test.go"]


def test_go_missing_test_flagged(tmp_path):
    root = _go_repo(tmp_path)
    g = imports_analyzer.build_import_graph(root)
    from codeguardian.models import DiffFile, FileStatus, FileCategory
    changed = [DiffFile(path="board/board.go", status=FileStatus.modified,
                        category=FileCategory.backend)]
    findings = tests_analyzer.analyze(root, changed, graph=g)
    # board.go has no board_test.go and no importing test -> missing-coverage finding.
    assert any("No test found" in f.title for f in findings)


# --- P2-1: Python public-API surface change -----------------------------------
from codeguardian.analyzers import pytypes as pytypes_analyzer
from codeguardian.analyzers import schema as schema_analyzer
from codeguardian.analyzers.imports import ImportGraph as _IG
from codeguardian.models import DiffFile as _DF, FileStatus as _FS


def test_pytypes_flags_removed_public_def_with_blast_radius():
    patch = (
        "diff --git a/pkg/api.py b/pkg/api.py\n--- a/pkg/api.py\n+++ b/pkg/api.py\n"
        "@@ -1,3 +1,1 @@\n-def public_handler():\n-    return 1\n+def renamed_handler():\n+    return 1\n"
    )
    graph = _IG(forward={}, reverse={"pkg/api.py": {"pkg/caller.py", "pkg/other.py"}})
    findings = pytypes_analyzer.analyze("/root",
        [_DF(path="pkg/api.py", status=_FS.modified, patch=patch)], graph=graph)
    assert len(findings) == 1
    assert "public_handler" in findings[0].title
    assert findings[0].id.startswith("CG-PYAPI")
    assert "pkg/caller.py" in findings[0].evidence_files


def test_pytypes_ignores_private_and_readded_symbols():
    # leading-underscore (private) removal is not flagged
    priv = ("--- a/x.py\n+++ b/x.py\n-def _private():\n+def _private2():\n")
    assert pytypes_analyzer.analyze("/r", [_DF(path="x.py", status=_FS.modified, patch=priv)],
                                    graph=_IG(forward={}, reverse={})) == []
    # a removed-then-readded public name is a reformat, not a removal
    readd = ("--- a/y.py\n+++ b/y.py\n-def keep():\n+def keep():\n+    pass\n")
    assert pytypes_analyzer.analyze("/r", [_DF(path="y.py", status=_FS.modified, patch=readd)],
                                    graph=_IG(forward={}, reverse={})) == []


# --- P2-3: OpenAPI / GraphQL schema diff --------------------------------------
def test_schema_flags_removed_openapi_path():
    patch = (
        "diff --git a/openapi.yaml b/openapi.yaml\n--- a/openapi.yaml\n+++ b/openapi.yaml\n"
        "@@ -10,6 +10,2 @@\n paths:\n-  /users/{id}:\n-    delete:\n-      summary: remove user\n"
    )
    findings = schema_analyzer.analyze("/r", [_DF(path="openapi.yaml", status=_FS.modified, patch=patch)])
    assert len(findings) == 1
    assert findings[0].id.startswith("CG-SCHEMA")
    assert "/users/{id}" in findings[0].summary
    assert findings[0].severity.value == "high"


def test_schema_flags_removed_graphql_type_and_field():
    patch = (
        "diff --git a/schema.graphql b/schema.graphql\n--- a/schema.graphql\n+++ b/schema.graphql\n"
        "@@ -1,6 +1,3 @@\n type User {\n-  email: String\n }\n-type LegacyThing {\n-  id: ID\n-}\n"
    )
    findings = schema_analyzer.analyze("/r", [_DF(path="schema.graphql", status=_FS.modified, patch=patch)])
    assert len(findings) == 1
    summary = findings[0].summary
    assert "LegacyThing" in summary or "email" in summary


def test_schema_ignores_additions_only():
    patch = (
        "--- a/openapi.yaml\n+++ b/openapi.yaml\n@@ -1,1 +1,3 @@\n paths:\n+  /new:\n+    get: {}\n"
    )
    assert schema_analyzer.analyze("/r", [_DF(path="openapi.yaml", status=_FS.modified, patch=patch)]) == []


def test_schema_ignores_non_schema_files():
    patch = "--- a/app.py\n+++ b/app.py\n-  /users:\n"
    assert schema_analyzer.analyze("/r", [_DF(path="app.py", status=_FS.modified, patch=patch)]) == []
