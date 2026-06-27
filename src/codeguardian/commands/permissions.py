"""Permission checks based on GitHub author_association.

GitHub returns one of: OWNER, MEMBER, COLLABORATOR, CONTRIBUTOR, FIRST_TIMER,
FIRST_TIME_CONTRIBUTOR, NONE. We treat the first three as maintainers.
"""

from __future__ import annotations

_MAINTAINER = {"OWNER", "MEMBER", "COLLABORATOR"}


def is_maintainer(author_association: str | None) -> bool:
    return (author_association or "").upper() in _MAINTAINER


def can_recheck(author_association: str | None) -> bool:
    # Recheck consumes CI minutes; restrict to maintainers (abuse prevention).
    return is_maintainer(author_association)


def can_suppress_blocking(author_association: str | None) -> bool:
    return is_maintainer(author_association)
