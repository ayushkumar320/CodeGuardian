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
