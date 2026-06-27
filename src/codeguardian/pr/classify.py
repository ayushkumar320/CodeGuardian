"""Classify changed files into risk categories (deterministic)."""

from __future__ import annotations

from ..globs import matches_any  # re-exported for callers
from ..models import FileCategory

_DOCS_EXT = (".md", ".mdx", ".rst", ".txt")
_DOCS_NAMES = ("license", "notice", "authors", "codeowners")
_CONFIG_EXT = (".json", ".yml", ".yaml", ".toml", ".ini", ".env", ".lock")
_CONFIG_NAMES = (
    "package.json",
    "tsconfig.json",
    "dockerfile",
    ".gitignore",
    ".eslintrc",
)
_TEST_MARKERS = (".test.", ".spec.", "__tests__/", "/tests/", "/test/")
_DB_MARKERS = ("migration", "migrations/", "schema.prisma", ".sql")
_TYPES_MARKERS = (".types.ts", ".d.ts", "/types/")
_FRONTEND_EXT = (".tsx", ".jsx", ".css", ".scss", ".vue", ".svelte")
_BACKEND_EXT = (".ts", ".js", ".mjs", ".cjs")


def classify(path: str) -> FileCategory:
    p = path.lower()
    name = p.rsplit("/", 1)[-1]

    if any(m in p for m in _TEST_MARKERS):
        return FileCategory.test
    if any(m in p for m in _DB_MARKERS):
        return FileCategory.database
    if any(m in p for m in _TYPES_MARKERS):
        return FileCategory.types
    if p.endswith(_DOCS_EXT) or name in _DOCS_NAMES:
        return FileCategory.docs
    if name in _CONFIG_NAMES or p.endswith(_CONFIG_EXT):
        return FileCategory.config
    if p.endswith(_FRONTEND_EXT):
        return FileCategory.frontend
    if p.endswith(_BACKEND_EXT):
        return FileCategory.backend
    return FileCategory.other


def is_docs_only(categories: list[FileCategory]) -> bool:
    return bool(categories) and all(c == FileCategory.docs for c in categories)
