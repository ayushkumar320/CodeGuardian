"""Phase 7 regression: the published composite action must run on consumer repos
that are not themselves Python projects.

Defect: `setup-python` with `cache: "pip"` searches the *consumer's* checked-out
repo for requirements.txt / pyproject.toml to key the cache. JS/TS consumer repos
have neither, so the step errored and the whole run failed before CodeGuardian
could produce a report. The action installs from `github.action_path`, so caching
against the consumer's deps was both broken and pointless.
"""

from __future__ import annotations

from pathlib import Path

_ACTION_YML = Path(__file__).resolve().parent.parent / "action.yml"


def test_action_yml_does_not_enable_pip_cache():
    text = _ACTION_YML.read_text()
    assert "cache:" not in text, (
        "setup-python must not enable pip caching: it keys off a dependency file "
        "in the consumer repo, which non-Python consumers do not have, and fails "
        "the run."
    )


def test_action_is_composite():
    assert 'using: "composite"' in _ACTION_YML.read_text()
