"""Command planning: parsed command + reports + permission -> Outcome.

Pure and side-effect free so it is fully unit-testable. The thin GitHub I/O
wrapper (entrypoint) executes the Outcome: post the reply, optionally recheck,
optionally record a suppression.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..models import Report
from . import handlers, permissions
from .parser import Command, CommandName, parse as parse_command


def reply_marker(comment_id: int) -> str:
    return f"<!-- cg-reply:{comment_id} -->"


_REPLY_REF_RE = re.compile(r"cg-reply:(\d+)")
_QA_MAX_CHARS = 800  # per side; keep follow-up context from blowing the prompt budget


def _strip_marker(body: str) -> str:
    """Drop the reply marker comment + leading whitespace from a bot reply."""
    return re.sub(r"<!--\s*cg-reply:\d+\s*-->\s*", "", body or "", count=1).strip()


def load_recent_asks(client, owner: str, repo: str, pr_number: int, n: int = 5) -> list[dict]:
    """Reconstruct the last ``n`` `/codeguardian <question>` ↔ bot-reply pairs
    from the PR thread so a follow-up ("expand on the second point") has an
    anchor (P1-1). A bot reply carries ``cg-reply:<id>`` pointing at the
    question comment; we pair the parsed question with the reply body.

    Best-effort and bounded: each side capped at 800 chars, all of it later
    wrapped as untrusted input by the prompt builder.
    """
    comments = client.list_issue_comments(owner, repo, pr_number)
    if not comments:
        return []
    by_id = {c.get("id"): c for c in comments}
    pairs: list[dict] = []
    for c in comments:
        body = c.get("body") or ""
        m = _REPLY_REF_RE.search(body)
        if not m:
            continue
        question_comment = by_id.get(int(m.group(1)))
        if question_comment is None:
            continue
        cmd = parse_command(question_comment.get("body") or "")
        if cmd is None or cmd.name != CommandName.ask or not cmd.question:
            continue
        pairs.append({
            "q": cmd.question[:_QA_MAX_CHARS],
            "a": _strip_marker(body)[:_QA_MAX_CHARS],
        })
    return pairs[-n:]


@dataclass
class Outcome:
    reply: Optional[str] = None
    do_recheck: bool = False
    suppression: Optional[tuple[str, str]] = None  # (finding_id, reason)


def plan(command: Command, reports: list[Report], author_association: str | None,
         previous_qa: Optional[list[dict]] = None) -> Outcome:
    outcome = _plan(command, reports, author_association, previous_qa)
    # Prepend the legacy-mention nudge once, above whatever reply we produced.
    if command.legacy_mention and outcome.reply:
        outcome.reply = f"{handlers.LEGACY_MENTION_WARNING}\n\n{outcome.reply}"
    return outcome


def _plan(command: Command, reports: list[Report], author_association: str | None,
          previous_qa: Optional[list[dict]] = None) -> Outcome:
    latest = reports[0] if reports else None
    previous = reports[1] if len(reports) > 1 else None
    name = command.name

    if name in (CommandName.help, CommandName.unknown):
        return Outcome(reply=handlers.HELP_TEXT)

    if name == CommandName.ask:
        if latest is None:
            return Outcome(reply=handlers.NO_REPORT)
        return Outcome(reply=handlers.ask(latest, command.question or "", previous_qa=previous_qa))

    if name == CommandName.recheck:
        if not permissions.can_recheck(author_association):
            return Outcome(reply="Only maintainers can run `/codeguardian recheck`.")
        return Outcome(reply="Re-running CodeGuardian analysis on the latest commit…", do_recheck=True)

    if name == CommandName.ignore:
        return _plan_ignore(command, latest, author_association)

    # Read-only commands need a report.
    if latest is None:
        return Outcome(reply=handlers.NO_REPORT)

    if name == CommandName.explain:
        return Outcome(reply=handlers.explain(latest, command.category))
    if name == CommandName.tests:
        return Outcome(reply=handlers.tests(latest))
    if name == CommandName.why_blocked:
        return Outcome(reply=handlers.why_blocked(latest))
    if name == CommandName.summary:
        return Outcome(reply=handlers.summary(latest))
    if name == CommandName.compare:
        return Outcome(reply=handlers.compare(latest, previous))
    if name == CommandName.history:
        return Outcome(reply=handlers.history(latest))
    if name == CommandName.show:
        return Outcome(reply=handlers.show(latest, command.target))

    return Outcome(reply=handlers.HELP_TEXT)


def _plan_ignore(command: Command, latest: Optional[Report], assoc: str | None) -> Outcome:
    if not command.finding_id:
        return Outcome(reply="Usage: `/codeguardian ignore <finding-id> reason: <why>`")
    if not command.reason:
        return Outcome(reply="Suppression requires a reason. Add `reason: <why>`.")
    if latest is None:
        return Outcome(reply=handlers.NO_REPORT)

    finding = next((f for f in latest.findings if f.id == command.finding_id), None)
    if finding is None:
        return Outcome(reply=f"I couldn't find finding `{command.finding_id}` in the latest report.")

    is_blocking = finding.blocking.guarded or finding.blocking.strict
    if is_blocking and not permissions.can_suppress_blocking(assoc):
        return Outcome(
            reply=f"`{finding.id}` is a blocking finding — only maintainers can suppress it."
        )
    return Outcome(
        reply=(
            f"Suppressed `{finding.id}` for this PR.\n"
            f"Reason: {command.reason}\n"
            f"It will stay visible in the summary with your name and reason."
        ),
        suppression=(finding.id, command.reason),
    )
