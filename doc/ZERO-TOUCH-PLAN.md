# Zero-Touch Activation & Production-Grade Review — Implementation Plan

Status: **planned** (2026-06-30). This is the v1.1 initiative that turns
CodeGuardian from a *passive* per-push check into an **active pre-merge review
cockpit** the repo owner activates once. Companion to
[IMPROVEMENT-PLAN.md](IMPROVEMENT-PLAN.md) (which stays the smaller P0/P1/P2
backlog); this doc owns the larger workflow change.

All four strict-rule guardrails still bind: deterministic-first, every finding
cites evidence, quiet by default, zero-key still works, idempotent. Nothing here
makes a model key a hard dependency.

## Decisions (locked)

- **Provider:** keep Groq → HF → deterministic (no new provider). Quality is
  raised by upgrading the Groq *model tier*, not by adding Claude.
- **Review surface:** a single pinned **Risk Dashboard issue** ranking all open
  PRs, plus the existing per-PR check + sticky comment.
- **Code-quality dimension:** wrap the repo's **own** linters/type-checkers,
  scoped to changed lines, surfacing only new high-confidence errors.

---

## Workstream A — One-command activation

**Deliverable:** `scripts/codeguardian-init.sh`, run from project root.
Idempotent; no manual GitHub-UI steps.

1. **Preflight** — git repo + GitHub remote present; `gh` installed and authed
   (used for secrets + push without a separate auth dance).
2. **Detect stack** — `package.json` / `pyproject.toml` / `go.mod` / monorepo
   markers → choose the matching template in [`examples/`](../examples/).
3. **Generate workflow** — write `.github/workflows/codeguardian.yml` **only if
   absent**. If it exists and differs, print a diff and ask — never clobber a
   hand-tuned workflow.
4. **Secrets (optional)** — offer `gh secret set GROQ_API_KEY` / `HF_TOKEN`;
   skip cleanly if declined (deterministic path still runs).
5. **Commit + open a PR** with the workflow, so activation itself goes through
   review.
6. **Backfill** — enumerate open PRs and dispatch analysis on each (Workstream B).

**Code change:** `__main__.run()` must handle the `workflow_dispatch` event.
Today it falls through `parse_pr_context` → `None` → "skipping." Add a dispatch
handler reading an input (`pr_number`, or `all`), fetch open PRs via the API,
and run the existing `_analyze_and_publish` per PR. This is what makes "activate
on all *active* PRs" real (the `pull_request` trigger only covers future pushes).

Files: `scripts/codeguardian-init.sh` (new), `src/codeguardian/__main__.py`
(dispatch handling), `src/codeguardian/github/client.py` (`list_open_pulls`),
one `examples/*.yml` input wiring (`workflow_dispatch.inputs.pr_number`).

## Workstream B — Review all active PRs from one place

- **Backfill:** `workflow_dispatch` + `all` → loop open PRs → analyze each.
  Idempotent via the existing head-SHA dedupe key.
- **Risk Dashboard:** one **pinned issue** (`<!-- cg-dashboard -->` anchor),
  upserted on every run, listing each open PR ranked by merge-risk score with a
  one-line "what could break" + link. Reuses the sticky-comment
  find-by-anchor/update-in-place pattern, so it stays idempotent and quiet. The
  owner triages the whole queue from one place.

Files: `src/codeguardian/report.py` (`risk_dashboard` renderer),
`src/codeguardian/github/client.py` (`upsert_pinned_issue`, `list_open_pulls`),
`src/codeguardian/__main__.py` (refresh dashboard after each analysis).

## Workstream C — Code-quality dimension (on-thesis, not a linter clone)

CodeGuardian must not become a generic reviewer. So "quality" means
*risk-relevant* quality, surfaced the CodeGuardian way:

- Run the repo's **own** tools on changed files — `ruff`/`mypy` (Py),
  `eslint`/`tsc` (JS/TS), `go vet` (Go) — as a new deterministic evidence source
  feeding a new `Category.quality`.
- **Quiet:** surface only (a) errors not style nits, (b) on diff-touched lines,
  ideally (c) newly introduced by this PR. "This change adds a real defect," not
  "your repo has 4,000 warnings."
- **Opt-in / auto-detected:** if a tool isn't installed, the analyzer no-ops
  (zero-key, never a hard dependency).

Files: `src/codeguardian/analyzers/quality.py` (new), `models.Category.quality`,
a `quality_agent` node in `graph/build.py` + `graph/agents.py`,
`policy.Quality` config block (enable/disable per tool).

## Workstream D — Production-grade response quality

Root cause of "not production grade": the model tier (`llama-3.1-8b-instant`).
Fix without adding a provider:

- **Upgrade the Groq model** to a 70B-class option (e.g.
  `llama-3.3-70b-versatile`), configurable via env/policy (`policy.model.groq_model`).
- **Harden synthesis:** stronger system prompts, strict JSON-shape validation
  (extend `validate_summary`), and a richer deterministic fallback so even the
  zero-key path reads well.
- Deterministic-first preserved — the model still only synthesizes evidence.

Files: `src/codeguardian/providers.py` (model constant → configurable;
prompt + validation), `policy.Model` (add `groq_model`).

---

## Sequencing

1. **D** (Groq model tier + prompt hardening) — small, immediate quality lift.
2. **A + B** (init script + `workflow_dispatch` backfill + dashboard) — the
   zero-touch activation + cockpit.
3. **C** (quality analyzer) — new dimension behind the quiet-by-default bar.

## Risks & guardrails

- **Backfill stampede:** analyzing every open PR at once can burn Actions
  minutes. Mitigate with a concurrency cap + the head-SHA dedupe (skip PRs whose
  head already has a current check).
- **Dashboard churn:** update-in-place only; never open a second dashboard issue.
- **Quality-analyzer noise:** the single biggest risk to the product's "quiet"
  promise. Hard-gate to new + error-level + diff-line findings; ship disabled and
  enable per-tool after dogfooding.
- **Bigger Groq model latency/cost:** keep it configurable; document the tradeoff.
