"""Deterministic reply text for each read-only command.

Answers come straight from the structured Report (the latest artifact), so they
work with zero model keys. Replies are short and link back to the check/artifact
for full evidence (P3 noise rules).
"""

from __future__ import annotations

from typing import Optional

from ..models import Provider, Report
from ..providers import answer_question, select_provider
from ..report import merge_status

HELP_TEXT = (
    "**CodeGuardian** predicts what this PR can break before merge.\n"
    "- `/codeguardian <your question>` — ask anything in plain English\n"
    "- `/codeguardian explain` — why this risk score\n"
    "- `/codeguardian tests` — tests to run before merge\n"
    "- `/codeguardian why blocked` — the finding blocking merge + the fix\n"
    "- `/codeguardian show <path-or-symbol>` — the changed hunks + findings for it\n"
    "- `/codeguardian compare` — what changed since the last run\n"
    "- `/codeguardian has this happened before?` — similar past PRs\n"
    "- `/codeguardian recheck` — re-run the analysis (maintainers)\n"
    "- `/codeguardian ignore <id> reason: …` — suppress a finding (maintainers)\n"
    "- `/codeguardian summary` — repost the short report\n"
)

NO_REPORT = (
    "I don't have an analysis for this PR yet. Push a commit or run "
    "`/codeguardian recheck` to generate one."
)

# Nudge shown above replies triggered via the deprecated `@codeguardian` form,
# which auto-links to an unrelated GitHub user and pings them (P0-5).
LEGACY_MENTION_WARNING = (
    "> ⚠️ Tip: use `/codeguardian` instead of `@codeguardian`. "
    "The `@` form pings an unrelated GitHub user."
)


def _level(report: Report) -> str:
    return f"{report.risk.score}/10 {report.risk.level.value}"


def explain(report: Report, category: Optional[str] = None) -> str:
    active = report.active_findings()
    if category:
        active = [f for f in active if f.category.value == category]
        if not active:
            return f"No {category} findings in this PR."
        lines = [f"**{category.title()} risk** (overall {_level(report)}):", "", "Findings:"]
        for f in active[:5]:
            lines.append(
                f"- `{f.id}` {f.severity.value} — {f.title}\n"
                f"  Evidence: {', '.join(f.evidence_files[:5])}\n"
                f"  Action: {(f.recommended_actions or ['—'])[0]}"
            )
        return "\n".join(lines)
    if not active:
        return f"Risk {_level(report)}. No findings — this looks safe to merge."
    lines = [
        f"**Risk {_level(report)}** · {merge_status(report)}",
        "Affected: " + (", ".join(report.affected_areas) or "changed files"),
        "",
        "Top findings:",
    ]
    for f in active[:3]:
        lines.append(f"- `{f.id}` {f.category.value} · {f.severity.value} — {f.title}")
    lines.append("\nFull evidence is in the latest run artifact.")
    return "\n".join(lines)


def tests(report: Report) -> str:
    recs: list[str] = []
    for f in report.active_findings():
        if f.category.value == "test":
            recs.extend(f.recommended_actions)
    # Also surface any "add a regression test" actions from other categories.
    for f in report.active_findings():
        for a in f.recommended_actions:
            if "test" in a.lower() and a not in recs:
                recs.append(a)
    if not recs:
        return "No specific tests recommended — changed code already has nearby tests."
    lines = ["**Recommended tests before merge:**"]
    lines += [f"{i}. {r}" for i, r in enumerate(dict.fromkeys(recs), 1)]
    return "\n".join(lines)


def why_blocked(report: Report) -> str:
    if not report.risk.blocking:
        return (
            f"This PR is **not blocked** (risk {_level(report)}, {report.mode.value} mode). "
            "It can merge under the current policy."
        )
    blockers = [
        f
        for f in report.active_findings()
        if (f.blocking.guarded or f.blocking.strict)
    ]
    if not blockers:
        return f"Blocked by policy at risk {_level(report)}."
    lines = ["**This PR is blocked by:**"]
    for f in blockers:
        fix = (f.recommended_actions or ["—"])[0]
        lines.append(
            f"- `{f.id}` {f.category.value} · {f.severity.value}\n"
            f"  {f.title}\n"
            f"  Evidence: {', '.join(f.evidence_files[:5])}\n"
            f"  Smallest fix: {fix}"
        )
    return "\n".join(lines)


def summary(report: Report) -> str:
    active = report.active_findings()
    head = f"**CodeGuardian Risk: {_level(report)}** · {merge_status(report)}"
    if not active:
        return head + " — no findings."
    return head + f" — {len(active)} finding(s). Use `/codeguardian explain` for detail."


def history(report: Report) -> str:
    if not report.historical_context:
        return "No similar past PRs found in CodeGuardian memory for this change."
    lines = ["**Has this happened before?**"]
    lines += [f"- {c}" for c in report.historical_context]
    return "\n".join(lines)


# Common question shapes we can answer deterministically with no model key
# (strict rule #3). Matched in order — first hit wins — so more specific
# intents ("why blocked") are checked before broader ones ("what is this").
_NO_KEY_NOTE = (
    "\n\n_Answered from the structured analysis — free-form Q&A gets richer "
    "with a model key (`GROQ_API_KEY` / `HF_TOKEN`)._"
)


def _route_no_provider(report: Report, question: str) -> Optional[str]:
    """Route common questions to deterministic handlers when no LLM is
    configured. Returns the routed reply, or None to use the generic fallback.

    Conservative on purpose: every branch lands on a handler whose answer is
    still relevant to the question's topic, and the appended note makes clear
    that fuller Q&A needs a key — so a near-miss still helps rather than misleads.
    """
    q = question.lower()
    if "block" in q:
        return why_blocked(report) + _NO_KEY_NOTE
    if "test" in q:
        return tests(report) + _NO_KEY_NOTE
    if (
        "what changed" in q
        or "what's changed" in q
        or "summar" in q
        or "what is this" in q
        or "what does this" in q
        or "is this safe" in q
        or "safe to merge" in q
    ):
        return summary(report) + _NO_KEY_NOTE
    return None


def ask(report: Report, question: str, previous_qa: Optional[list[dict]] = None) -> str:
    """Free-form Q&A. The LLM may only describe what analyzers already found
    (strict rule #2). When no provider is configured, routes common question
    shapes to deterministic handlers (strict rule #3) and otherwise falls back
    to a useful message pointing at structured commands.

    ``previous_qa`` carries prior question/answer pairs in this PR thread so a
    follow-up has context (P1-1); ignored on the no-provider path.
    """
    if not question.strip():
        return "What would you like to know? Try `/codeguardian explain` for the standard summary."
    if select_provider() == Provider.deterministic:
        routed = _route_no_provider(report, question)
        if routed is not None:
            return routed
    result = answer_question(report, question, previous_qa=previous_qa)
    # The result text already has the deterministic fallback when no key is
    # configured, so we just return it as-is.
    return result.text


_SHOW_MAX_FILES = 3
_SHOW_MAX_CHARS_PER_FILE = 3000


def show(report: Report, target: Optional[str]) -> str:
    """Deterministic `/codeguardian show <path-or-symbol>`: render the changed
    hunks for matching files plus any findings that point at them. Zero LLM —
    gives the no-key path something visually rich (P2-4).
    """
    if not target:
        return "Usage: `/codeguardian show <path-or-symbol>` — e.g. `show src/board.py` or `show empty_board`."
    needle = target.lower()
    matches = []
    for d in report.diff_summary:
        hunk_text = "\n".join(d.relevant_hunks) or (d.patch_excerpt or "")
        if needle in d.path.lower() or needle in hunk_text.lower():
            matches.append((d, hunk_text))
    if not matches:
        return f"No changed file or symbol matching `{target}` in this PR's diff."

    lines = [f"**Showing `{target}`** ({len(matches)} match(es) in the diff):"]
    for d, hunk_text in matches[:_SHOW_MAX_FILES]:
        body = hunk_text[:_SHOW_MAX_CHARS_PER_FILE]
        if len(hunk_text) > _SHOW_MAX_CHARS_PER_FILE:
            body += "\n…(truncated)"
        lines += [
            "",
            f"### `{d.path}` · {d.status.value} (+{d.additions}/-{d.deletions})",
            "```diff",
            body.strip() or "(no hunk text available)",
            "```",
        ]
        related = [
            f for f in report.active_findings() if d.path in f.evidence_files
        ]
        if related:
            lines.append("Findings here:")
            for f in related:
                lines.append(
                    f"- `{f.id}` {f.category.value} · {f.severity.value} — {f.title}"
                )
    if len(matches) > _SHOW_MAX_FILES:
        lines += ["", f"_…and {len(matches) - _SHOW_MAX_FILES} more match(es)._"]
    return "\n".join(lines)


def compare(current: Report, previous: Optional[Report]) -> str:
    if previous is None:
        return "No previous run to compare against yet."
    cur_ids = {f.id for f in current.active_findings()}
    prev_ids = {f.id for f in previous.active_findings()}
    new = cur_ids - prev_ids
    resolved = prev_ids - cur_ids
    delta = round(current.risk.score - previous.risk.score, 1)
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
    lines = [
        f"**Risk:** {previous.risk.score} → {current.risk.score} ({arrow} {abs(delta)})",
        f"New findings: {len(new)}" + (f" ({', '.join(sorted(new))})" if new else ""),
        f"Resolved findings: {len(resolved)}"
        + (f" ({', '.join(sorted(resolved))})" if resolved else ""),
        f"Remaining blockers: {sum(1 for f in current.active_findings() if f.blocking.guarded or f.blocking.strict)}",
    ]
    return "\n".join(lines)
