"""CodeGuardian Action entrypoint.

Flow: parse event -> load policy -> run LangGraph analysis -> write artifacts ->
publish check -> upsert sticky comment (when policy allows). Exit non-zero only
when the run blocks merge, so it can drive a required GitHub check.
"""

from __future__ import annotations

import os
import sys

from .github.client import GitHubClient
from .github.events import event_name, load_event, parse_pr_context
from .graph.build import run_analysis
from .models import RiskLevel
from .policy import Policy
from .report import (
    check_conclusion,
    check_summary,
    json_artifact,
    markdown_artifact,
    sticky_comment,
)


def _workspace() -> str:
    return os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def _should_comment(report, policy: Policy) -> bool:
    n = policy.noise
    if report.risk.level == RiskLevel.low and not report.active_findings():
        return not n.skip_comment_for_docs_only
    if report.risk.level == RiskLevel.medium and not n.comment_on_medium:
        return False
    return True


def run() -> int:
    repo_root = _workspace()
    event = load_event()
    pr = parse_pr_context(event)

    if pr is None:
        print(f"CodeGuardian: no pull request in event '{event_name()}'. Skipping.")
        return 0

    policy = Policy.load(repo_root)
    report, narrative = run_analysis(repo_root, pr, policy)

    # Artifacts (always written — full evidence trail).
    out_dir = os.environ.get("CODEGUARDIAN_OUT", repo_root)
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "codeguardian-report.json")
    md_path = os.path.join(out_dir, "codeguardian-report.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(json_artifact(report))
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(markdown_artifact(report, policy, narrative))

    # GitHub surfaces.
    client = GitHubClient()
    conclusion = check_conclusion(report)
    summary = check_summary(report, policy)
    title = f"{report.risk.score}/10 {report.risk.level.value} — {'blocked' if report.risk.blocking else 'allowed'}"
    try:
        client.publish_check(pr.owner, pr.repo, pr.head_sha, conclusion, title, summary)
        if _should_comment(report, policy):
            client.upsert_sticky_comment(
                pr.owner, pr.repo, pr.number, sticky_comment(report, policy, narrative)
            )
    except Exception as exc:  # noqa: BLE001 - never crash the Action on GitHub I/O
        print(f"CodeGuardian: GitHub publish failed: {exc}", file=sys.stderr)

    print(f"CodeGuardian: {title} (provider={report.provider.value})")
    print(f"  report: {json_path}")

    # Drive the required check: fail only when policy blocks.
    return 1 if report.risk.blocking else 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
