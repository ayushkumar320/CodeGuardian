"""Parse `/codeguardian <command>` from a PR comment body.

The trigger is ``/codeguardian`` (preferred) or ``@codeguardian`` (back-compat).
The slash form is the recommended one: ``@codeguardian`` is auto-linked by the
GitHub UI to whatever account happens to own that username, which notifies an
unrelated person on every command. The slash form has no such collision.

Returns a Command or None. Only the supported, memorable set is recognized;
anything else that still mentions the trigger becomes an ``unknown`` command so
the loop can reply with help (P3 "refuse ambiguous or unsupported commands").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

MENTION = "/codeguardian"

# Accept the slash form (preferred, no username collision) or the legacy @ form.
_MENTION_RE = re.compile(r"[@/]codeguardian\b", re.IGNORECASE)
_IGNORE_RE = re.compile(
    r"ignore\s+(?P<id>[A-Za-z0-9\-]+)(?:\s+reason:\s*(?P<reason>.+))?",
    re.IGNORECASE | re.DOTALL,
)


class CommandName(str, Enum):
    help = "help"
    explain = "explain"
    tests = "tests"
    why_blocked = "why_blocked"
    recheck = "recheck"
    compare = "compare"
    summary = "summary"
    history = "history"
    ignore = "ignore"
    ask = "ask"        # free-form question answered by the LLM, evidence-only
    unknown = "unknown"  # bare `/codeguardian` with nothing after


_CATEGORY_ALIASES = {
    "database": "database", "db": "database",
    "api": "api",
    "architecture": "architecture", "arch": "architecture",
    "test": "test", "tests": "test",
    "dependency": "dependency", "deps": "dependency", "type": "dependency", "types": "dependency",
}


@dataclass
class Command:
    name: CommandName
    finding_id: Optional[str] = None
    reason: Optional[str] = None
    category: Optional[str] = None  # for `explain <category> risk`
    question: Optional[str] = None  # free-form text for `ask`
    raw: str = ""

    @property
    def is_read_only(self) -> bool:
        return self.name in {
            CommandName.help,
            CommandName.explain,
            CommandName.tests,
            CommandName.why_blocked,
            CommandName.compare,
            CommandName.summary,
            CommandName.history,
            CommandName.ask,
        }


_MAX_QUESTION_CHARS = 1500  # bound prompt-injection volume on free-form input.


def parse(body: str) -> Optional[Command]:
    if not body or not _MENTION_RE.search(body):
        return None
    # Take the text after the first @codeguardian mention.
    after = _MENTION_RE.split(body, maxsplit=1)[1].strip()
    # Bare `/codeguardian` (nothing after) -> help. Anything else flows through.
    if not after:
        return Command(CommandName.help, raw="")
    low = after.lower()

    if low.startswith("why blocked") or low.startswith("why_blocked") or low.startswith("why-blocked"):
        return Command(CommandName.why_blocked, raw=after)
    if low.startswith("has this happened") or low.startswith("history"):
        return Command(CommandName.history, raw=after)
    if low.startswith("ignore"):
        m = _IGNORE_RE.search(after)
        if m:
            reason = (m.group("reason") or "").strip() or None
            return Command(CommandName.ignore, finding_id=m.group("id"), reason=reason, raw=after)
        return Command(CommandName.ignore, raw=after)

    tokens = low.split()
    first = tokens[0] if tokens else ""

    if first == "explain":
        category = next((_CATEGORY_ALIASES[t] for t in tokens[1:] if t in _CATEGORY_ALIASES), None)
        return Command(CommandName.explain, category=category, raw=after)

    simple = {
        "help": CommandName.help,
        "explain": CommandName.explain,
        "tests": CommandName.tests,
        "test": CommandName.tests,
        "recheck": CommandName.recheck,
        "recheck.": CommandName.recheck,
        "compare": CommandName.compare,
        "summary": CommandName.summary,
    }
    if first in simple:
        return Command(simple[first], raw=after)
    # Free-form question — anything that mentioned us but isn't a known command.
    # Capped to defend against prompt-injection-by-volume; the LLM call also
    # wraps the question as untrusted input.
    question = after[:_MAX_QUESTION_CHARS]
    return Command(CommandName.ask, question=question, raw=after)
