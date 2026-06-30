"""Parse the GitHub Actions event payload into a PrContext / CommentEvent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from ..models import PrContext
from ..security import safe_output

_MAX_BODY_CHARS = 2000

COMMENT_EVENTS = {"issue_comment", "pull_request_review_comment"}


@dataclass
class CommentEvent:
    pr_number: int
    comment_id: int
    body: str
    author: str
    author_association: str
    is_bot: bool
    in_review_thread: bool  # pull_request_review_comment vs issue_comment


def load_event(env: Optional[dict] = None) -> dict:
    env = env or os.environ
    path = env.get("GITHUB_EVENT_PATH")
    if not path or not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_pr_context(event: dict, env: Optional[dict] = None) -> Optional[PrContext]:
    env = env or os.environ
    repo_full = env.get("GITHUB_REPOSITORY", "/")
    owner, _, repo = repo_full.partition("/")

    pr = event.get("pull_request")
    if not pr and "issue" in event:
        pr = event["issue"].get("pull_request") and event["issue"]
    if not pr:
        return None

    number = pr.get("number") or event.get("number")
    base = pr.get("base", {})
    head = pr.get("head", {})
    installation = event.get("installation", {}).get("id")
    head_repo = head.get("repo") or {}
    base_repo = base.get("repo") or {}
    head_full = head_repo.get("full_name", "")
    base_full = base_repo.get("full_name", "")

    if number is None:
        return None

    return PrContext(
        owner=owner,
        repo=repo,
        number=int(number),
        base_sha=base.get("sha", ""),
        head_sha=head.get("sha", env.get("GITHUB_SHA", "")),
        title=pr.get("title", ""),
        body=safe_output((pr.get("body") or "")[:_MAX_BODY_CHARS]),
        installation_id=installation,
        is_fork=bool(head_full and base_full and head_full != base_full),
        head_ref=head.get("ref", ""),
        head_repo_clone_url=head_repo.get("clone_url", ""),
    )


def event_name(env: Optional[dict] = None) -> str:
    env = env or os.environ
    return env.get("GITHUB_EVENT_NAME", "")


def parse_comment_event(event: dict) -> Optional[CommentEvent]:
    comment = event.get("comment")
    if not comment:
        return None
    # issue_comment carries the PR under "issue"; review comments under "pull_request".
    issue = event.get("issue") or {}
    pr = event.get("pull_request") or {}
    if issue and "pull_request" not in issue and not pr:
        return None  # a plain issue comment, not a PR
    number = issue.get("number") or pr.get("number")
    if number is None:
        return None
    user = comment.get("user") or {}
    return CommentEvent(
        pr_number=int(number),
        comment_id=int(comment.get("id", 0)),
        body=comment.get("body", "") or "",
        author=user.get("login", ""),
        author_association=comment.get("author_association", "NONE"),
        is_bot=(user.get("type", "") == "Bot"),
        in_review_thread=bool(pr) and "issue" not in event,
    )
