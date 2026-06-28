#!/usr/bin/env python3
"""Phase 7 sandbox validator.

Best-effort GitHub API harness for validating a real sandbox PR run.

Usage examples:

  GITHUB_TOKEN=... python e2e/validate_sandbox.py verify-pr \
    --repo owner/name --pr 12

  GITHUB_TOKEN=... python e2e/validate_sandbox.py send-command \
    --repo owner/name --pr 12 --body "@codeguardian tests"
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SUMMARY_ANCHOR = "<!-- codeguardian-ai-summary -->"
CHECK_NAME = "CodeGuardian Risk"
ARTIFACT_NAME = "codeguardian-report"
REPLY_MARKER = "<!-- cg-reply:"
API = "https://api.github.com"


class GitHub:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, path: str, *, body: dict | None = None, params: dict | None = None):
        url = f"{API}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = None
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {self.token}",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}

    def comments(self, owner: str, repo: str, pr: int) -> list[dict]:
        out: list[dict] = []
        page = 1
        while True:
            batch = self.request(
                "GET",
                f"/repos/{owner}/{repo}/issues/{pr}/comments",
                params={"per_page": 100, "page": page},
            )
            if not batch:
                return out
            out.extend(batch)
            if len(batch) < 100:
                return out
            page += 1

    def pull(self, owner: str, repo: str, pr: int) -> dict:
        return self.request("GET", f"/repos/{owner}/{repo}/pulls/{pr}")

    def check_runs(self, owner: str, repo: str, head_sha: str) -> list[dict]:
        data = self.request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
            params={"check_name": CHECK_NAME, "per_page": 100},
        )
        return data.get("check_runs", [])

    def artifacts(self, owner: str, repo: str, *, per_page: int = 30) -> list[dict]:
        data = self.request(
            "GET",
            f"/repos/{owner}/{repo}/actions/artifacts",
            params={"name": ARTIFACT_NAME, "per_page": per_page},
        )
        return data.get("artifacts", [])

    def artifact_report_json(self, owner: str, repo: str, artifact_id: int) -> dict | None:
        req = urllib.request.Request(
            f"{API}/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {self.token}",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read()
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                with zf.open("codeguardian-report.json") as fh:
                    return json.load(fh)
        except (KeyError, ValueError, zipfile.BadZipFile):
            return None

    def post_comment(self, owner: str, repo: str, pr: int, body: str) -> dict:
        return self.request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr}/comments",
            body={"body": body},
        )


def split_repo(repo: str) -> tuple[str, str]:
    owner, sep, name = repo.partition("/")
    if not sep:
        raise SystemExit("--repo must look like owner/name")
    return owner, name


def wait_for(predicate, *, timeout_s: int, interval_s: int, label: str):
    started = time.time()
    while time.time() - started < timeout_s:
        value = predicate()
        if value:
            return value
        time.sleep(interval_s)
    raise SystemExit(f"Timed out waiting for {label} after {timeout_s}s")


def command_reply_count(comments: list[dict]) -> int:
    return sum(1 for c in comments if REPLY_MARKER in (c.get("body") or ""))


def latest_report_for_pr(gh: GitHub, owner: str, repo: str, pr: int, artifacts: list[dict]) -> tuple[dict, dict] | tuple[None, None]:
    ordered = sorted(
        [a for a in artifacts if a.get("name") == ARTIFACT_NAME and not a.get("expired")],
        key=lambda a: a.get("created_at", ""),
        reverse=True,
    )
    for artifact in ordered:
        aid = artifact.get("id")
        if not aid:
            continue
        report = gh.artifact_report_json(owner, repo, aid)
        if report and report.get("pr", {}).get("number") == pr:
            return artifact, report
    return None, None


def cmd_verify_pr(args) -> int:
    gh = GitHub(args.token)
    owner, repo = split_repo(args.repo)
    pull = gh.pull(owner, repo, args.pr)
    head_sha = pull["head"]["sha"]

    check_runs = wait_for(
        lambda: gh.check_runs(owner, repo, head_sha),
        timeout_s=args.timeout,
        interval_s=args.interval,
        label="CodeGuardian check run",
    )
    matching = [r for r in check_runs if r.get("name") == CHECK_NAME]
    if not matching:
        raise SystemExit("No CodeGuardian check run found")

    comments = gh.comments(owner, repo, args.pr)
    sticky = [c for c in comments if SUMMARY_ANCHOR in (c.get("body") or "")]
    if args.expect_sticky and not sticky:
        raise SystemExit("Expected sticky summary comment, but none was found")
    if len(sticky) > 1:
        raise SystemExit(f"Expected at most one sticky summary comment, found {len(sticky)}")

    artifacts = gh.artifacts(owner, repo, per_page=max(args.artifact_scan, 30))
    report_artifacts = [a for a in artifacts if a.get("name") == ARTIFACT_NAME and not a.get("expired")]
    latest_artifact, latest_report = latest_report_for_pr(gh, owner, repo, args.pr, report_artifacts)
    if args.expect_artifact and latest_report is None:
        raise SystemExit("Expected a matching report artifact for this PR, but none was found")

    print("verify-pr: ok")
    print(f"- check runs: {len(matching)}")
    print(f"- sticky comments: {len(sticky)}")
    print(f"- available report artifacts: {len(report_artifacts)}")
    if latest_artifact and latest_report:
        print(f"- latest matching artifact id: {latest_artifact.get('id')}")
        print(f"- artifact report pr: {latest_report.get('pr', {}).get('number')}")
    for run in matching[:3]:
        print(f"- check conclusion: {run.get('conclusion')} status={run.get('status')}")
    return 0


def cmd_send_command(args) -> int:
    gh = GitHub(args.token)
    owner, repo = split_repo(args.repo)
    before_comments = gh.comments(owner, repo, args.pr)
    before = {c.get("id") for c in before_comments}
    before_reply_count = command_reply_count(before_comments)
    created = gh.post_comment(owner, repo, args.pr, args.body)
    print(f"posted comment id={created.get('id')}")

    def has_reply():
        comments = gh.comments(owner, repo, args.pr)
        for comment in comments:
            cid = comment.get("id")
            body = comment.get("body") or ""
            if cid not in before and REPLY_MARKER in body:
                return comment
        return None

    reply = wait_for(
        has_reply,
        timeout_s=args.timeout,
        interval_s=args.interval,
        label="CodeGuardian command reply",
    )
    print("command reply: ok")
    after_comments = gh.comments(owner, repo, args.pr)
    after_reply_count = command_reply_count(after_comments)
    if args.expect_single_reply and after_reply_count != before_reply_count + 1:
        raise SystemExit(
            "Expected exactly one new CodeGuardian reply marker after posting the command"
        )
    print(f"- reply markers before: {before_reply_count}")
    print(f"- reply markers after: {after_reply_count}")
    print(reply.get("body", "")[:600])
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate a live CodeGuardian sandbox PR")
    p.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub token (defaults to GITHUB_TOKEN env var)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    verify = sub.add_parser("verify-pr", help="verify check/comment/artifact surfaces")
    verify.add_argument("--repo", required=True)
    verify.add_argument("--pr", required=True, type=int)
    verify.add_argument("--expect-sticky", action="store_true")
    verify.add_argument("--expect-artifact", action="store_true")
    verify.add_argument("--artifact-scan", type=int, default=50)
    verify.add_argument("--timeout", type=int, default=120)
    verify.add_argument("--interval", type=int, default=5)
    verify.set_defaults(func=cmd_verify_pr)

    send = sub.add_parser("send-command", help="post a PR command and wait for reply")
    send.add_argument("--repo", required=True)
    send.add_argument("--pr", required=True, type=int)
    send.add_argument("--body", required=True)
    send.add_argument("--expect-single-reply", action="store_true")
    send.add_argument("--timeout", type=int, default=120)
    send.add_argument("--interval", type=int, default=5)
    send.set_defaults(func=cmd_send_command)
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.token:
        raise SystemExit("Provide --token or set GITHUB_TOKEN")
    try:
        return args.func(args)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API error: {exc.code} {exc.reason}\n{detail}") from exc


if __name__ == "__main__":
    sys.exit(main())
