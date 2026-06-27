"""Path glob matching with sane `**/` semantics.

`fnmatch` has no globstar: a leading `**/` won't match a top-level path because
it still requires a `/` before the next segment. Users expect `**/prisma/**` to
match `prisma/schema.prisma`. We approximate globstar by also trying the pattern
with a leading `**/` removed (zero leading directories).
"""

from __future__ import annotations

import fnmatch


def glob_match(path: str, pattern: str) -> bool:
    p = path.lower()
    pat = pattern.lower()
    if fnmatch.fnmatch(p, pat):
        return True
    # `**/x` should also match `x` (zero leading dirs).
    if pat.startswith("**/") and fnmatch.fnmatch(p, pat[3:]):
        return True
    # `x/**` should also match `x` (zero trailing segments).
    if pat.endswith("/**") and fnmatch.fnmatch(p, pat[:-3]):
        return True
    return False


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_match(path, pat) for pat in patterns)
