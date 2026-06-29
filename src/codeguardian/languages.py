"""Language detection + the support matrix.

This is the single source of truth for *which* deterministic analyzers run on
*which* language. Adding a new language is intentionally small here:

1. Map its file extensions in ``_EXT_TO_LANG``.
2. List it under the analyzer keys it has deterministic support for in
   ``_SUPPORT`` (``import_graph``, ``test_conventions``, etc.).

Languages with no entry still get the language-agnostic baseline (high-risk
paths, PR-shape findings) — they degrade gracefully instead of going silent.

We deliberately do *not* let the LLM make up language understanding here; if
there is no analyzer for a finding category, no finding fires (strict rule #2).
"""

from __future__ import annotations

from dataclasses import dataclass


# Extension -> human language name. Keep tight: minified/source maps are noise.
_EXT_TO_LANG: dict[str, str] = {
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".py": "Python",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".scala": "Scala",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".swift": "Swift",
    ".m": "Objective-C", ".mm": "Objective-C",
    ".css": "CSS", ".scss": "CSS",
    ".vue": "Vue", ".svelte": "Svelte",
}


# Per-language analyzer support. Keep keys stable; consumers compare strings.
# Note: "architecture" is graph-derived, so any language with "import_graph" gets
# architecture for free.
_SUPPORT: dict[str, set[str]] = {
    "TypeScript": {"import_graph", "test_conventions", "types", "api", "database"},
    "JavaScript": {"import_graph", "test_conventions", "types", "api", "database"},
    "Python":     {"import_graph", "test_conventions"},
    # Everything else: language-agnostic baseline only (high-risk paths, PR-shape).
}


@dataclass(frozen=True)
class LanguageReport:
    """Languages observed in this run, and what we did about them."""

    primary: str | None              # the most-used language by file count
    repo_languages: list[str]        # all languages seen in the repo, by frequency
    changed_languages: list[str]     # languages touched by *this* PR
    supported: dict[str, list[str]]  # lang -> analyzers we have for it
    unsupported_in_pr: list[str]     # languages this PR touches that we don't deeply analyze

    @property
    def fully_unsupported_pr(self) -> bool:
        """True iff every language this PR touches is in the agnostic-only tier."""
        return bool(self.changed_languages) and not any(
            l in _SUPPORT for l in self.changed_languages
        )


def language_of(path: str) -> str | None:
    p = path.lower()
    for ext, lang in _EXT_TO_LANG.items():
        if p.endswith(ext):
            return lang
    return None


def detect(
    *,
    language_summary: dict[str, int],
    changed_paths: list[str],
) -> LanguageReport:
    """Build the language report for a run.

    ``language_summary`` is the extension->count map already produced by
    ``repository_context``; we reuse it instead of re-walking the repo.
    """
    repo_counts: dict[str, int] = {}
    for ext, n in language_summary.items():
        lang = _EXT_TO_LANG.get(ext.lower())
        if lang:
            repo_counts[lang] = repo_counts.get(lang, 0) + n
    repo_languages = sorted(repo_counts, key=lambda l: (-repo_counts[l], l))
    primary = repo_languages[0] if repo_languages else None

    seen_in_pr: list[str] = []
    for p in changed_paths:
        lang = language_of(p)
        if lang and lang not in seen_in_pr:
            seen_in_pr.append(lang)

    supported = {
        lang: sorted(_SUPPORT[lang]) for lang in seen_in_pr if lang in _SUPPORT
    }
    unsupported = [l for l in seen_in_pr if l not in _SUPPORT]
    return LanguageReport(
        primary=primary,
        repo_languages=repo_languages,
        changed_languages=seen_in_pr,
        supported=supported,
        unsupported_in_pr=unsupported,
    )


def supports(language: str, analyzer: str) -> bool:
    """Quick predicate for ``if supports('Python', 'types'): ...``."""
    return analyzer in _SUPPORT.get(language, set())
