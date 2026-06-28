"""Build the GitHub-facing report surfaces from a Report (progressive disclosure).

- check summary: "Can I merge?" (short, merge-page output contract)
- sticky comment: "Why, and what do I do?" (concise, expandable)
- artifacts: full JSON + Markdown evidence
"""

from __future__ import annotations

from . import SUMMARY_ANCHOR
from .models import Mode, Report, RiskLevel
from .policy import Policy

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
    ]
    return "\n".join(lines)


def markdown_artifact(report: Report, policy: Policy, narrative: str) -> str:
    return sticky_comment(report, policy, narrative).replace(SUMMARY_ANCHOR + "\n", "")


def json_artifact(report: Report) -> str:
    return report.model_dump_json(indent=2)
