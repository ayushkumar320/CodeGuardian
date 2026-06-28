from __future__ import annotations

import io
import importlib.util
import json
from pathlib import Path
import zipfile

_MODULE = Path(__file__).resolve().parents[1] / "e2e" / "validate_sandbox.py"
_SPEC = importlib.util.spec_from_file_location("validate_sandbox", _MODULE)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

command_reply_count = _MOD.command_reply_count
latest_report_for_pr = _MOD.latest_report_for_pr


def _zip_report(pr_number: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("codeguardian-report.json", json.dumps({"pr": {"number": pr_number}}))
    return buf.getvalue()


def test_command_reply_count_counts_markers():
    comments = [
        {"body": "x"},
        {"body": "<!-- cg-reply:1 -->\nreply"},
        {"body": "<!-- cg-reply:2 -->\nreply"},
    ]
    assert command_reply_count(comments) == 2


def test_latest_report_for_pr_picks_matching_artifact():
    class FakeGitHub:
        def artifact_report_json(self, owner, repo, artifact_id):
            return {
                9: {"pr": {"number": 3}},
                10: {"pr": {"number": 7}},
            }.get(artifact_id)

    artifacts = [
        {"id": 9, "name": "codeguardian-report", "created_at": "2026-06-27T00:00:00Z"},
        {"id": 10, "name": "codeguardian-report", "created_at": "2026-06-28T00:00:00Z"},
    ]
    artifact, report = latest_report_for_pr(FakeGitHub(), "o", "r", 7, artifacts)
    assert artifact["id"] == 10
    assert report == {"pr": {"number": 7}}


def test_latest_report_for_pr_ignores_expired_and_mismatched():
    class FakeGitHub:
        def artifact_report_json(self, owner, repo, artifact_id):
            return {11: {"pr": {"number": 1}}}.get(artifact_id)

    artifacts = [
        {"id": 11, "name": "codeguardian-report", "created_at": "2026-06-28T00:00:00Z", "expired": True},
        {"id": 12, "name": "codeguardian-report", "created_at": "2026-06-27T00:00:00Z", "expired": False},
    ]
    artifact, report = latest_report_for_pr(FakeGitHub(), "o", "r", 9, artifacts)
    assert artifact is None
    assert report is None
