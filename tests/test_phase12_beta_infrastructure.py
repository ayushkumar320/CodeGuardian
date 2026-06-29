"""Phase 12: beta scaffolding — issue templates, support/triage docs, GA list."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def test_issue_templates_exist():
    tpl = _ROOT / ".github" / "ISSUE_TEMPLATE"
    assert (tpl / "false-positive.yml").is_file()
    assert (tpl / "false-negative.yml").is_file()
    assert (tpl / "bug.yml").is_file()
    assert (tpl / "config.yml").is_file()


def test_issue_templates_label_for_triage():
    for name in ("false-positive.yml", "false-negative.yml", "bug.yml"):
        text = (_ROOT / ".github" / "ISSUE_TEMPLATE" / name).read_text()
        assert "needs-triage" in text, f"{name} should auto-label for triage"


def test_support_and_ga_docs_present():
    assert (_ROOT / "SUPPORT.md").is_file()
    assert (_ROOT / "doc" / "GA-CHECKLIST.md").is_file()
    assert (_ROOT / "doc" / "POST-V1-ROADMAP.md").is_file()


def test_default_policy_is_quiet_and_advisory():
    """Phase 12 OOB default: advisory mode, skip-comment on docs-only PRs."""
    from codeguardian.policy import Policy
    from codeguardian.models import Mode

    p = Policy()
    assert p.mode == Mode.advisory
    assert p.noise.skip_comment_for_docs_only is True
