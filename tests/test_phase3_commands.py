from codeguardian.commands import permissions
from codeguardian.commands.loop import plan, reply_marker
from codeguardian.commands.parser import CommandName, parse
from codeguardian.models import (
    Blocking,
    Category,
    Finding,
    Mode,
    Provider,
    Report,
    Risk,
    RiskLevel,
    PrContext,
    Severity,
)


def _report(findings, score=7.0, level=RiskLevel.high, blocking=True):
    return Report(
        pr=PrContext(owner="o", repo="r", number=1, base_sha="a", head_sha="b"),
        mode=Mode.guarded,
        provider=Provider.deterministic,
        risk=Risk(score=score, level=level, confidence=0.8, blocking=blocking),
        findings=findings,
    )


def _finding(fid="CG-DB-001", blocking=True, sev=Severity.high):
    return Finding(
        id=fid, category=Category.database, severity=sev, confidence=0.8,
        title="t", summary="s", evidence_files=["a.sql"],
        recommended_actions=["add a test"],
        blocking=Blocking(guarded=blocking, strict=blocking),
    )


# --- parser ---------------------------------------------------------------
def test_parse_basic_commands():
    assert parse("@codeguardian explain").name == CommandName.explain
    assert parse("hey @codeguardian why blocked please").name == CommandName.why_blocked
    assert parse("@codeguardian tests").name == CommandName.tests
    assert parse("@codeguardian recheck").name == CommandName.recheck
    assert parse("@codeguardian summary").name == CommandName.summary
    assert parse("@codeguardian compare").name == CommandName.compare


def test_parse_no_mention():
    assert parse("just a normal comment") is None


def test_parse_unknown():
    assert parse("@codeguardian dance").name == CommandName.unknown


def test_parse_ignore_with_reason():
    c = parse("@codeguardian ignore CG-DB-002 reason: column is unused")
    assert c.name == CommandName.ignore
    assert c.finding_id == "CG-DB-002"
    assert "unused" in c.reason


def test_parse_ignore_without_reason():
    c = parse("@codeguardian ignore CG-DB-002")
    assert c.name == CommandName.ignore and c.reason is None


# --- permissions ----------------------------------------------------------
def test_permissions():
    assert permissions.can_recheck("OWNER")
    assert permissions.can_recheck("MEMBER")
    assert not permissions.can_recheck("CONTRIBUTOR")
    assert not permissions.can_suppress_blocking("NONE")


# --- plan -----------------------------------------------------------------
def test_help_needs_no_report():
    out = plan(parse("@codeguardian help"), [], "NONE")
    assert "explain" in out.reply


def test_explain_without_report():
    out = plan(parse("@codeguardian explain"), [], "NONE")
    assert "don't have an analysis" in out.reply


def test_why_blocked_reports_blocker():
    rep = _report([_finding()])
    out = plan(parse("@codeguardian why blocked"), [rep], "NONE")
    assert "CG-DB-001" in out.reply and "blocked by" in out.reply.lower()


def test_recheck_requires_maintainer():
    denied = plan(parse("@codeguardian recheck"), [], "CONTRIBUTOR")
    assert not denied.do_recheck and "maintainers" in denied.reply
    ok = plan(parse("@codeguardian recheck"), [], "OWNER")
    assert ok.do_recheck


def test_ignore_blocking_requires_maintainer():
    rep = _report([_finding(blocking=True)])
    denied = plan(parse("@codeguardian ignore CG-DB-001 reason: safe"), [rep], "CONTRIBUTOR")
    assert denied.suppression is None and "maintainers" in denied.reply
    ok = plan(parse("@codeguardian ignore CG-DB-001 reason: safe"), [rep], "OWNER")
    assert ok.suppression == ("CG-DB-001", "safe")


def test_ignore_requires_reason():
    rep = _report([_finding()])
    out = plan(parse("@codeguardian ignore CG-DB-001"), [rep], "OWNER")
    assert out.suppression is None and "reason" in out.reply.lower()


def test_ignore_unknown_finding():
    rep = _report([_finding()])
    out = plan(parse("@codeguardian ignore CG-XX-999 reason: x"), [rep], "OWNER")
    assert out.suppression is None and "couldn't find" in out.reply


def test_compare_needs_previous():
    rep = _report([_finding()])
    assert "No previous run" in plan(parse("@codeguardian compare"), [rep], "NONE").reply
    prev = _report([_finding("CG-DB-001"), _finding("CG-DB-009")], score=8.0)
    out = plan(parse("@codeguardian compare"), [rep, prev], "NONE")
    assert "Risk:" in out.reply and "Resolved findings: 1" in out.reply


def test_reply_marker_stable():
    assert reply_marker(123) == "<!-- cg-reply:123 -->"
