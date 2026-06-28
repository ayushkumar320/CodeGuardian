"""CodeGuardian Action entrypoint.

Dispatches by GitHub event:
- pull_request* -> run analysis, publish check + sticky comment + artifacts.
- issue_comment / pull_request_review_comment -> @codeguardian conversation loop.

Exit non-zero only when a pull_request analysis blocks merge, so it can drive a
required GitHub check.
"""

from __future__ import annotations

import os
import subprocess
import sys

from .commands import loop as cmd_loop
from .commands.parser import Command, CommandName, parse as parse_command
from .github.client import GitHubClient
from .github.events import (
    COMMENT_EVENTS,
    event_name,
    load_event,
    parse_comment_event,
    parse_pr_context,
)
from .graph.build import run_analysis
from .memory.record import MemoryRecord
from .memory.store import GitBranchMemoryStore
from .models import PrContext, Provider, Report, RiskLevel, Suppression
from .policy import Policy
from .providers import deterministic_summary
from .report import (
    check_conclusion,
    check_summary,
    json_artifact,
    markdown_artifact,
    sticky_comment,
)
from .log import get_logger
from .scoring import score

_log = get_logger()


def _workspace() -> str:
    return os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def _out_dir() -> str:
    d = os.environ.get("CODEGUARDIAN_OUT", _workspace())
    os.makedirs(d, exist_ok=True)
    return d


def _should_comment(report: Report, policy: Policy) -> bool:
    n = policy.noise
    if report.risk.level == RiskLevel.low and not report.active_findings():
        return not n.skip_comment_for_docs_only
    if report.risk.level == RiskLevel.medium and not n.comment_on_medium:
        return False
    return True


def _write_artifacts(report: Report, policy: Policy, narrative: str) -> str:
    out = _out_dir()
    json_path = os.path.join(out, "codeguardian-report.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(json_artifact(report))
    with open(os.path.join(out, "codeguardian-report.md"), "w", encoding="utf-8") as fh:
        fh.write(markdown_artifact(report, policy, narrative))
    return json_path


def _write_job_summary(report: Report) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [
        "# CodeGuardian",
        "",
        f"- Risk: **{report.risk.score} / 10 {report.risk.level.value}**",
        f"- Merge: **{check_conclusion(report)}**",
        f"- Provider: **{report.provider.value}**",
    ]
    if report.degraded:
        lines.append("- Run health: **degraded**")
    if report.actions:
        lines += ["", "## Top actions"]
        lines += [f"{i}. {a}" for i, a in enumerate(report.actions[:3], 1)]
    if report.errors:
        lines += ["", "## Errors"]
        lines += [f"- {e}" for e in report.errors[:10]]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _internal_error_report(pr: PrContext, policy: Policy, message: str) -> Report:
    return Report(
        pr=pr,
        mode=policy.mode,
        provider=Provider.deterministic,
        risk=score([], policy),
        errors=[message],
        degraded=True,
        deterministic_notice="CodeGuardian hit an internal error and returned a degraded result.",
    )


def _memory_store(repo_root: str, policy: Policy):
    if not policy.memory.enabled:
        return None
    return GitBranchMemoryStore(
        repo_root,
        policy.memory.branch,
        max_records=policy.memory.max_records,
        retention_days=policy.memory.retention_days,
    )


def _can_publish(pr: PrContext) -> bool:
    # Fork-originated pull_request runs get a read-only token and no secrets.
    # Skip write attempts entirely so the run degrades quietly instead of
    # emitting predictable permission failures.
    return not pr.is_fork


def _analyze_and_publish(repo_root: str, pr: PrContext, policy: Policy) -> Report:
    store = _memory_store(repo_root, policy) if _can_publish(pr) else None
    report, narrative = run_analysis(repo_root, pr, policy, memory_store=store)
    json_path = _write_artifacts(report, policy, narrative)

    # Persist a compact memory record for future PRs (best-effort).
    if store is not None:
        try:
            store.append(MemoryRecord.from_report(report))
        except Exception as exc:  # noqa: BLE001
            _log.warning("memory write skipped: %s", exc)

    client = GitHubClient()
    title = f"{report.risk.score}/10 {report.risk.level.value} — {'blocked' if report.risk.blocking else 'allowed'}"
    if not _can_publish(pr):
        print("CodeGuardian: fork PR detected; skipping check/comment/memory writes.")
        _write_job_summary(report)
        print(f"CodeGuardian: {title} (provider={report.provider.value})  report: {json_path}")
        return report
    try:
        client.publish_check(
            pr.owner, pr.repo, pr.head_sha, check_conclusion(report), title,
            check_summary(report, policy),
        )
        if _should_comment(report, policy):
            client.upsert_sticky_comment(
                pr.owner, pr.repo, pr.number, sticky_comment(report, policy, narrative)
            )
    except Exception as exc:  # noqa: BLE001 - never crash on GitHub I/O
        _log.warning("GitHub publish failed: %s", exc)

    _write_job_summary(report)
    print(f"CodeGuardian: {title} (provider={report.provider.value})  report: {json_path}")
    return report


# --- pull_request path ----------------------------------------------------
def _run_pull_request(event: dict, repo_root: str) -> int:
    pr = parse_pr_context(event)
    if pr is None:
        print(f"CodeGuardian: no pull request in event '{event_name()}'. Skipping.")
        return 0
    policy = Policy.load(repo_root)
    report = _analyze_and_publish(repo_root, pr, policy)
    return 1 if report.risk.blocking else 0


# --- comment (conversation loop) path -------------------------------------
def _run_comment(event: dict, repo_root: str) -> int:
    ce = parse_comment_event(event)
    if ce is None:
        return 0
    command = parse_command(ce.body)
    if command is None:
        return 0  # no @codeguardian mention
    if ce.is_bot:
        print("CodeGuardian: ignoring bot comment.")
        return 0

    repo_full = os.environ.get("GITHUB_REPOSITORY", "/")
    owner, _, repo = repo_full.partition("/")
    client = GitHubClient()

    marker = cmd_loop.reply_marker(ce.comment_id)
    if client.already_replied(owner, repo, ce.pr_number, marker):
        print(f"CodeGuardian: already handled comment {ce.comment_id}.")
        return 0

    policy = Policy.load(repo_root)
    raw_reports = client.latest_reports(owner, repo, ce.pr_number, limit=2)
    reports = [Report.model_validate(r) for r in raw_reports]

    outcome = cmd_loop.plan(command, reports, ce.author_association)

    if outcome.do_recheck:
        _post_reply(client, owner, repo, ce.pr_number, marker, outcome.reply)
        _recheck(client, owner, repo, ce.pr_number, repo_root, policy)
        return 0

    if outcome.suppression and reports:
        _apply_suppression(client, owner, repo, ce, reports[0], policy, outcome.suppression)

    _post_reply(client, owner, repo, ce.pr_number, marker, outcome.reply)
    return 0


def _post_reply(client: GitHubClient, owner: str, repo: str, number: int,
                marker: str, body: str | None) -> None:
    if not body:
        return
    try:
        client.reply(owner, repo, number, f"{marker}\n{body}")
    except Exception as exc:  # noqa: BLE001
        _log.warning("reply failed: %s", exc)


def _recheck(client: GitHubClient, owner: str, repo: str, number: int,
             repo_root: str, policy: Policy) -> None:
    pull = client.get_pull(owner, repo, number)
    if not pull:
        return
    head_sha = pull.get("head", {}).get("sha", "")
    base_sha = pull.get("base", {}).get("sha", "")
    head_ref = pull.get("head", {}).get("ref", "")
    head_repo = pull.get("head", {}).get("repo") or {}
    head_clone = head_repo.get("clone_url", "")
    base_repo = pull.get("base", {}).get("repo") or {}
    is_fork = bool(head_repo.get("full_name") and base_repo.get("full_name")
                   and head_repo.get("full_name") != base_repo.get("full_name"))
    # Fetch the PR head so the diff is available in this (comment-triggered) job.
    try:
        if head_clone and head_ref:
            subprocess.run(
                [
                    "git", "-C", repo_root, "fetch", "--no-tags", head_clone,
                    f"+refs/heads/{head_ref}:refs/remotes/codeguardian-pr/{number}",
                ],
                check=False, capture_output=True,
            )
        else:
            subprocess.run(
                ["git", "-C", repo_root, "fetch", "origin", f"pull/{number}/head"],
                check=False, capture_output=True,
            )
        if base_sha:
            subprocess.run(
                ["git", "-C", repo_root, "fetch", "origin", base_sha],
                check=False, capture_output=True,
            )
    except OSError:
        pass
    pr = PrContext(
        owner=owner, repo=repo, number=number,
        base_sha=base_sha, head_sha=head_sha, title=pull.get("title", ""),
        is_fork=is_fork, head_ref=head_ref, head_repo_clone_url=head_clone,
    )
    _analyze_and_publish(repo_root, pr, policy)


def _apply_suppression(client: GitHubClient, owner: str, repo: str, ce,
                       report: Report, policy: Policy, suppression: tuple[str, str]) -> None:
    finding_id, reason = suppression
    for f in report.findings:
        if f.id == finding_id:
            f.suppressed = Suppression(by=ce.author, reason=reason)
    # Recompute score without the suppressed finding (scoring ignores suppressed).
    report.risk = score(report.findings, policy)
    narrative = deterministic_summary(report)
    _write_artifacts(report, policy, narrative)  # uploaded as a fresh artifact
    try:
        client.upsert_sticky_comment(
            owner, repo, ce.pr_number, sticky_comment(report, policy, narrative)
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("sticky update failed: %s", exc)


def run() -> int:
    repo_root = _workspace()
    event = load_event()
    name = event_name()
    try:
        if name in COMMENT_EVENTS:
            return _run_comment(event, repo_root)
        return _run_pull_request(event, repo_root)
    except Exception as exc:  # noqa: BLE001
        pr = parse_pr_context(event)
        if pr is None:
            _log.error("internal error before PR context was available: %s", exc)
            return 0
        policy = Policy.load(repo_root)
        report = _internal_error_report(pr, policy, f"internal: {exc}")
        narrative = "CodeGuardian hit an internal error before analysis completed."
        _write_artifacts(report, policy, narrative)
        _write_job_summary(report)
        client = GitHubClient()
        if _can_publish(pr):
            try:
                client.publish_check(
                    pr.owner,
                    pr.repo,
                    pr.head_sha,
                    "neutral",
                    "internal error — degraded",
                    check_summary(report, policy),
                )
                if _should_comment(report, policy):
                    client.upsert_sticky_comment(
                        pr.owner, pr.repo, pr.number, sticky_comment(report, policy, narrative)
                    )
            except Exception as publish_exc:  # noqa: BLE001
                _log.error("failed to publish internal-error result: %s", publish_exc)
        _log.error("internal error handled gracefully: %s", exc)
        return 0


def main() -> None:
    if "--selfcheck" in sys.argv[1:]:
        from .selfcheck import run_selfcheck

        sys.exit(run_selfcheck())
    sys.exit(run())


if __name__ == "__main__":
    main()
