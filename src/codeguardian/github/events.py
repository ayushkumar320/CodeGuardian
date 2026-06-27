"""Parse the GitHub Actions event payload into a PrContext."""

from __future__ import annotations

import json
import os
from typing import Optional

from ..models import PrContext


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

    if number is None:
        return None

    return PrContext(
        owner=owner,
        repo=repo,
        number=int(number),
        base_sha=base.get("sha", ""),
        head_sha=head.get("sha", env.get("GITHUB_SHA", "")),
        title=pr.get("title", ""),
        installation_id=installation,
    )


def event_name(env: Optional[dict] = None) -> str:
    env = env or os.environ
    return env.get("GITHUB_EVENT_NAME", "")
