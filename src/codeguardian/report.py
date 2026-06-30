"""Build the GitHub-facing report surfaces from a Report (progressive disclosure).

- check summary: "Can I merge?" (short, merge-page output contract)
- sticky comment: "Why, and what do I do?" (concise, expandable)
- artifacts: full JSON + Markdown evidence
"""

from __future__ import annotations

from . import SUMMARY_ANCHOR
from .models import Mode, Provider, Report, RiskLevel, Severity
from .policy import Policy
from .pr.diff import first_added_line

_LEVEL_LABEL = {
    RiskLevel.low: "Low",
    RiskLevel.medium: "Medium",
    RiskLevel.high: "High",
    RiskLevel.critical: "Critical",
}


def merge_status(report: Report) -> str:
    if report.degraded and not report.risk.blocking:
        return "Allowed with degraded analysis"
    if report.risk.blocking:
        return f"Blocked by policy ({report.mode.value})"
    if report.risk.level == RiskLevel.medium:
        return "Allowed with warning"
    if report.risk.level in (RiskLevel.high, RiskLevel.critical):
        return "Allowed (advisory) — action strongly recommended"
    return "Allowed"


def check_conclusion(report: Report) -> str:
    """Map to a GitHub check conclusion (Phase 0 contract A2)."""
    if report.risk.blocking:
        return "failure"
    if report.risk.level in (RiskLevel.high, RiskLevel.critical):
        return "action_required" if report.mode == Mode.advisory else "failure"
    if report.risk.level == RiskLevel.medium:
        return "neutral"
    return "success"


def _header(report: Report) -> str:
    return (
        f"CodeGuardian Risk: {report.risk.score} / 10 "
        f"{_LEVEL_LABEL[report.risk.level]}"
    )


_CHECK_TITLE_MAX = 110  # GitHub allows long titles; keep the merge-box glance tight.


def _narrative_snippet(narrative: str, budget: int) -> str:
    """First sentence-ish of the narrative, stripped of markdown, trimmed to
    ``budget`` chars on a word boundary. Empty in -> empty out."""
    if not narrative:
        return ""
    # First non-empty line; drop common markdown markers so the title reads clean.
    line = next((ln.strip() for ln in narrative.splitlines() if ln.strip()), "")
    for token in ("**", "`", "#", ">", "- "):
        line = line.replace(token, "")
    line = line.strip()
    if len(line) <= budget:
        return line
    clipped = line[:budget].rsplit(" ", 1)[0]
    return (clipped or line[:budget]).rstrip(",.;:") + "…"


def check_title(report: Report, narrative: str) -> str:
    """The check ``output.title`` (distinct from the check *name*, which branch
    protection matches against). Lead with the at-a-glance score + merge verdict,
    then append a 1-line 'what this PR does' snippet from the summary (P1-5).
    Falls back to just the score line when there's no usable narrative.
    """
    verdict = "blocked" if report.risk.blocking else "allowed"
    base = f"{report.risk.score}/10 {report.risk.level.value} — {verdict}"
    snippet = _narrative_snippet(narrative, _CHECK_TITLE_MAX - len(base) - 2)
    return f"{base}: {snippet}" if snippet else base


def usage_footer(report: Report) -> str:
    """One-line per-PR provider tally (P2-5). Counts how many steps each
    provider served. Returns '' when everything ran deterministically (no
    model calls), so the zero-key path stays clean and quiet."""
    counts: dict[str, int] = {}
    for tag in report.provider_usage:
        provider = tag.split(":", 1)[-1]
        counts[provider] = counts.get(provider, 0) + 1
    billable = {p: n for p, n in counts.items() if p != Provider.deterministic.value}
    if not billable:
        return ""
    parts = ", ".join(f"{p}×{n}" for p, n in sorted(billable.items()))
    return f"Model calls this run: {parts}"


def check_summary(report: Report, policy: Policy) -> str:
    active = report.active_findings()
    lines = [
        f"## {_header(report)}",
        "",
        f"**Merge status:** {merge_status(report)}",
    ]
    if report.affected_areas:
        lines += ["", "**Affected areas:** " + ", ".join(report.affected_areas)]
    if report.degraded:
        lines += ["", "**Run health:** degraded — one or more analyzers or integrations failed."]
    for note in report.notes:
        lines += ["", f"> {note}"]

    top = active[: policy.noise.max_findings_check]
    if top:
        lines += ["", "**Top findings:**"]
        lines += [f"{i}. {f.title}" for i, f in enumerate(top, 1)]
    if report.actions:
        lines += ["", "**Recommended actions:**"]
        lines += [f"{i}. {a}" for i, a in enumerate(report.actions[:3], 1)]

    lines += [
        "",
        "**Ask in this PR:** `/codeguardian why blocked` · `/codeguardian tests` · `/codeguardian explain`",
        "",
        f"_{report.mode.value} mode · {report.provider.value}_",
    ]
    footer = usage_footer(report)
    if footer:
        lines += ["", f"_{footer}_"]
    if report.deterministic_notice:
        lines += ["", f"> {report.deterministic_notice}"]
    if report.errors:
        lines += ["", "<details><summary>Errors</summary>", ""]
        lines += [f"- {e}" for e in report.errors[:10]]
        lines += ["", "</details>"]
    return "\n".join(lines)


def sticky_comment(report: Report, policy: Policy, narrative: str) -> str:
    active = report.active_findings()

    # Docs-only / low-risk quiet path.
    if report.risk.level == RiskLevel.low and not active:
        return (
            f"{SUMMARY_ANCHOR}\n"
            f"**{_header(report)}** — low-risk change. No action recommended."
        )

    lines = [
        SUMMARY_ANCHOR,
        "## CodeGuardian AI — Risk Report",
        "",
        f"**Risk: {report.risk.score} / 10 · {_LEVEL_LABEL[report.risk.level]}**  ·  "
        f"**Merge: {merge_status(report)}**",
    ]
    if report.degraded:
        lines += ["", "> This run is degraded. Some analyzers or integrations failed, so the result may be incomplete."]
    for note in report.notes:
        lines += ["", f"> {note}"]
    if report.affected_areas:
        lines.append("Affected: " + " · ".join(report.affected_areas))
    if narrative:
        lines += ["", narrative]

    if report.actions:
        lines += ["", "**Top actions**"]
        lines += [f"{i}. {a}" for i, a in enumerate(report.actions[:3], 1)]
    if report.reviewers:
        lines += ["", "**Recommended reviewers:** " + ", ".join(report.reviewers)]
    if report.historical_context:
        lines += ["", "**Has this happened before?**"]
        lines += [f"- {c}" for c in report.historical_context]

    shown = active[: policy.noise.max_findings_comment]
    if shown:
        lines += ["", "<details><summary>Findings & evidence</summary>", ""]
        for f in shown:
            block = (
                f"- `{f.id}` {f.category.value} · {f.severity.value} · "
                f"confidence {f.confidence:.2f}\n"
                f"  Evidence: {', '.join(f.evidence_files[:5])}\n"
                f"  Action: {(f.recommended_actions or ['—'])[0]} · "
                f"Blocking: {'yes' if (f.blocking.guarded or f.blocking.strict) else 'no'}"
            )
            lines.append(block)
        lines += ["", "</details>"]

    suppressed = [f for f in report.findings if f.suppressed]
    if suppressed:
        lines += ["", "<details><summary>Suppressed findings</summary>", ""]
        for f in suppressed:
            lines.append(f"- `{f.id}` — {f.suppressed.reason} (by {f.suppressed.by})")
        lines += ["", "</details>"]
    if report.errors:
        lines += ["", "<details><summary>Errors</summary>", ""]
        lines += [f"- {e}" for e in report.errors[:10]]
        lines += ["", "</details>"]

    lines += [
        "",
        "---",
        "Ask in this PR: `/codeguardian why blocked` · `tests` · `explain`",
        f"_{report.mode.value} mode · {report.provider.value} · full report attached as a run artifact._",
        "",
        FEEDBACK_FOOTER,
    ]
    return "\n".join(lines)


# One-click feedback (P1-3): a reaction on the sticky comment is a zero-effort
# signal compared to filing a false-positive issue.
FEEDBACK_FOOTER = (
    "_Was this useful? React on this comment: 👍 helpful · 👎 not useful · "
    "😕 confusing · 🎯 caught a real bug._"
)

# GitHub reaction "content" values mapped to the feedback meaning we render.
_REACTION_MEANING = {
    "+1": "helpful",
    "-1": "not_useful",
    "confused": "confusing",
    "hooray": "caught_bug",
    "eyes": "caught_bug",
}


def reaction_tally(reactions: list[dict]) -> dict[str, int]:
    """Aggregate a sticky comment's reactions into feedback buckets (P1-3).
    Unrecognized reaction types are ignored. Pure — the caller decides where
    the tally is persisted (e.g. the memory branch)."""
    out: dict[str, int] = {}
    for r in reactions:
        meaning = _REACTION_MEANING.get(r.get("content", ""))
        if meaning:
            out[meaning] = out.get(meaning, 0) + 1
    return out


# --- Inline annotations (P1-2) ------------------------------------------------
# Bar for putting a finding *on the line*: high-confidence + localized only
# (strict rule #5). GitHub caps annotations at 50 per check-run request.
_ANNOTATION_MIN_CONFIDENCE = 0.7
_ANNOTATION_MAX = 50
_ANNOTATION_LEVEL = {
    Severity.low: "notice",
    Severity.medium: "warning",
    Severity.high: "failure",
    Severity.critical: "failure",
}


def annotations_from_report(report: Report, policy: Policy) -> list[dict]:
    """Build GitHub check annotations for the small set of findings that are
    confident *and* localized enough to sit on a line (P1-2). Opt-in via
    ``policy.noise.allow_inline_annotations``. Only findings with:
      - severity >= medium, AND
      - confidence >= 0.7, AND
      - exactly one evidence file that resolves to a changed line
    qualify; everything else stays in the sticky comment to keep the PR quiet.
    """
    if not policy.noise.allow_inline_annotations:
        return []
    patch_by_path = {d.path: d for d in report.diff_summary}
    out: list[dict] = []
    for f in report.active_findings():
        if f.severity == Severity.low or f.confidence < _ANNOTATION_MIN_CONFIDENCE:
            continue
        if len(f.evidence_files) != 1:
            continue
        path = f.evidence_files[0]
        d = patch_by_path.get(path)
        if d is None:
            continue
        patch = "\n".join(d.relevant_hunks) or d.patch_excerpt
        line = first_added_line(patch)
        if line is None:
            continue
        out.append({
            "path": path,
            "start_line": line,
            "end_line": line,
            "annotation_level": _ANNOTATION_LEVEL[f.severity],
            "title": f"{f.id}: {f.title}"[:255],
            "message": ((f.recommended_actions or [f.summary])[0] or f.title)[:640],
        })
        if len(out) >= _ANNOTATION_MAX:
            break
    return out


# --- Model-key requirement ----------------------------------------------------
# CodeGuardian requires a model provider key (Groq or Hugging Face). Without one
# it does not analyze (except fork PRs, which can't carry secrets and degrade).
KEY_REQUIRED_TITLE = "CodeGuardian needs a model key"


def key_required_check_summary() -> str:
    return (
        "## CodeGuardian needs a model key\n\n"
        "CodeGuardian requires a model provider key to run. No `GROQ_API_KEY` "
        "or `HF_TOKEN` is configured for this repository, so the analysis was "
        "skipped.\n\n"
        "**To enable CodeGuardian:** add one of these as a repository secret "
        "(Settings → Secrets and variables → Actions):\n"
        "- `GROQ_API_KEY` — fast summaries (recommended)\n"
        "- `HF_TOKEN` — Hugging Face fallback\n\n"
        "Then re-run the workflow or push a new commit."
    )


def key_required_comment() -> str:
    return (
        f"{SUMMARY_ANCHOR}\n"
        "## CodeGuardian needs a model key\n\n"
        "I'm installed on this PR but no model provider key is configured, so I "
        "can't run. Add **`GROQ_API_KEY`** or **`HF_TOKEN`** as a repository "
        "secret (Settings → Secrets and variables → Actions), then push a commit "
        "or comment `/codeguardian recheck`."
    )


def markdown_artifact(report: Report, policy: Policy, narrative: str) -> str:
    return sticky_comment(report, policy, narrative).replace(SUMMARY_ANCHOR + "\n", "")


def json_artifact(report: Report) -> str:
    return report.model_dump_json(indent=2)
