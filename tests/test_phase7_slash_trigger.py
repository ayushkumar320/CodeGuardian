"""Phase 7 regression: command trigger must not collide with a GitHub username.

`@codeguardian` is auto-linked by the GitHub UI to whatever account owns that
username, notifying an unrelated person on every command. The preferred trigger
is the slash form `/codeguardian`, which has no such collision. The legacy `@`
form is still accepted for back-compat.
"""

from __future__ import annotations

from codeguardian.commands.handlers import HELP_TEXT
from codeguardian.commands.parser import CommandName, parse


def test_slash_trigger_is_recognized():
    cmd = parse("/codeguardian explain")
    assert cmd is not None and cmd.name == CommandName.explain


def test_legacy_at_trigger_still_works():
    cmd = parse("@codeguardian explain")
    assert cmd is not None and cmd.name == CommandName.explain


def test_slash_trigger_parses_args_like_at():
    cmd = parse("/codeguardian ignore CG-DB-001 reason: false positive")
    assert cmd is not None and cmd.name == CommandName.ignore
    assert cmd.finding_id == "CG-DB-001"
    assert cmd.reason == "false positive"


def test_no_trigger_returns_none():
    assert parse("just a normal comment") is None


def test_help_text_advertises_slash_not_at():
    assert "/codeguardian" in HELP_TEXT
    assert "@codeguardian" not in HELP_TEXT
