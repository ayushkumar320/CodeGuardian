"""Similarity retrieval over memory records.

Default: deterministic keyword/path/category Jaccard similarity — works with zero
model keys. If HF embeddings are configured, an embedding cosine can refine
ranking, but retrieval never *requires* it (P5 fallback rule).
"""

from __future__ import annotations

from .record import MemoryRecord, Signature


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def similarity(current: Signature, record: MemoryRecord) -> float:
    rec_sig = record.signature()
    path_sim = _jaccard(current.paths, rec_sig.paths)
    cat_sim = _jaccard(current.categories, rec_sig.categories)
    return round(0.6 * path_sim + 0.4 * cat_sim, 3)


def find_similar(
    current: Signature,
    records: list[MemoryRecord],
    current_pr: int,
    max_results: int = 3,
    min_similarity: float = 0.34,
) -> list[tuple[MemoryRecord, float]]:
    scored: list[tuple[MemoryRecord, float]] = []
    seen_pr: set[int] = set()
    for r in records:
        if r.pr_number == current_pr:
            continue  # don't match the PR against itself
        s = similarity(current, r)
        if s >= min_similarity:
            scored.append((r, s))
    scored.sort(key=lambda t: t[1], reverse=True)
    # De-dup by PR (keep best score per PR).
    out: list[tuple[MemoryRecord, float]] = []
    for r, s in scored:
        if r.pr_number in seen_pr:
            continue
        seen_pr.add(r.pr_number)
        out.append((r, s))
        if len(out) >= max_results:
            break
    return out


def context_lines(matches: list[tuple[MemoryRecord, float]]) -> list[str]:
    lines: list[str] = []
    for r, s in matches:
        outcome = ""
        if r.merged is True:
            outcome = " · merged"
        elif r.merged is False:
            outcome = " · not merged"
        cats = ", ".join(r.finding_categories) or "no findings"
        note = f" — {r.outcome_notes}" if r.outcome_notes else ""
        lines.append(
            f"Similar to PR #{r.pr_number} (risk {r.risk_score} {r.risk_level}; "
            f"{cats}{outcome}; similarity {s:.0%}){note}"
        )
    return lines
