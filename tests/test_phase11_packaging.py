"""Phase 11: reproducible packaging — the Action installs from a pinned
lockfile, not by resolving deps from PyPI at run time.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_LOCK = _ROOT / "requirements.lock"
_ACTION = _ROOT / "action.yml"


def test_requirements_lock_exists_and_has_pins():
    assert _LOCK.is_file(), "requirements.lock must be committed for reproducible installs"
    pins = [
        ln for ln in _LOCK.read_text().splitlines()
        if "==" in ln and not ln.lstrip().startswith("#")
    ]
    assert len(pins) >= 4, f"expected pinned deps, found {len(pins)} lines with =="


def test_action_installs_from_lockfile_no_deps():
    text = _ACTION.read_text()
    assert "-r " in text and "requirements.lock" in text, (
        "action.yml must install deps from requirements.lock (Phase 11 reproducibility)"
    )
    assert "--no-deps" in text, (
        "action.yml must install the package with --no-deps so it doesn't re-resolve at run time"
    )
