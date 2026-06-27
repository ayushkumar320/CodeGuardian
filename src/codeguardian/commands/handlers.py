"""Deterministic reply text for each read-only command.

Answers come straight from the structured Report (the latest artifact), so they
work with zero model keys. Replies are short and link back to the check/artifact
for full evidence (P3 noise rules).
"""

from __future__ import annotations

from typing import Optional

from ..models import Report
from ..report import merge_status

HELP_TEXT = (
    "**CodeGuardian** predicts what this PR can break before merge.\n"
    "- `@codeguardian explain` — why this risk score\n"
    "- `@codeguardian tests` — tests to run before merge\n"
    "- `@codeguardian why blocked` — the finding blocking merge + the fix\n"
    "- `@codeguardian compare` — what changed since the last run\n"
    "- `@codeguardian has this happened before?` — similar past PRs\n"
    "- `@codeguardian recheck` — re-run the analysis (maintainers)\n"
    "- `@codeguardian ignore <id> reason: …` — suppress a finding (maintainers)\n"
    "- `@codeguardian summary` — repost the short report\n"
)

NO_REPORT = (
    "I don't have an analysis for this PR yet. Push a commit or run "
    "`@codeguardian recheck` to generate one."
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
    return head + f" — {len(active)} finding(s). Use `@codeguardian explain` for detail."


def history(report: Report) -> str:
    if not report.historical_context:
        return "No similar past PRs found in CodeGuardian memory for this change."
    lines = ["**Has this happened before?**"]
    lines += [f"- {c}" for c in report.historical_context]
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
