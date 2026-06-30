# Improvement Plan

Concrete, evidence-backed improvements to CodeGuardian discovered while testing
on `ayushkumar320/clawcode-test` PR #4. Each item names a specific gap in the
current code (with file paths), why it shows up in real PRs, the proposed fix,
and a rough effort estimate.

Strict rules from [CLAUDE.md](../CLAUDE.md) still apply to everything here:
deterministic-first, evidence-cited, quiet by default, zero-key path stays
useful, idempotent, in MVP scope. Items that would expand scope are flagged.

## Methodology

Each gap below was identified by:

1. Reading the actual code paths invoked when a developer comments on a PR
   (`__main__._run_comment` → `commands.parser.parse` → `commands.loop.plan`
   → `commands.handlers.ask` → `providers.answer_question`).
2. Grepping for "if this existed it would be referenced here" markers
   (annotations / PR description / historical context / conversation state /
   incremental cache).
3. Watching what an LLM-augmented `/codeguardian <question>` actually replies
   on PR #4 today, and tracing where the reply could be richer or more correct.

## Priority guide

| Tier | Meaning |
|------|---------|
| **P0** | Small, ship in the next minor release. Fixes friction users hit on the first PR. |
| **P1** | Meaningful work but ≤ 1 day of focused effort each. Aim for the release after v1.0. |
| **P2** | Real investment (multi-day or scope-expansion). Park behind beta-feedback signal. |

---

## P0 — UX wins that are small enough to land before v1.0

### P0-1 · Feed PR title + description into the ask prompt

**Current state.** `PrContext.title` is parsed (`github/events.py:64`) but only
used for the dedupe key. The PR **body / description** is never captured at all.
`providers._build_qa_prompt` only sees findings + diff + the user's question.

**Why it matters.** The PR description is the **developer's stated intent**.
Without it the model has to guess what the change is for; the developer ends up
asking "why is this here?" and getting a literal answer ("it adds a function
called X") instead of an interpretive one ("this implements the session-TTL
contract you described in the PR description").

**Proposal.**
- Extend `PrContext` with `body: str = ""`.
- Pull it in `_parse_pr_event` from `pr["body"]` (already in the GitHub event
  payload), redact via `security.safe_output`, cap at ~2000 chars.
- Add `pr_title` + `pr_description` to the `facts` dict the ask prompt builds.
- System prompt addition: *"If the PR description states the intent, use it to
  frame your answer — but never claim the PR does something the diff doesn't
  show."*

**Effort.** ~2 hours including a regression test that PR-body content makes it
into the prompt.

**Risk.** Low. PR body is already wrapped untrusted; no new injection surface.

---

### P0-2 · Wire historical context into the ask prompt

**Current state.** `report.historical_context` is populated by
`graph.agents.historical_knowledge_agent` (Phase 5 memory). It's shown on the
sticky comment but `providers._build_qa_prompt` doesn't include it.

**Why it matters.** Today, asking *"have we made changes like this before?"*
silently fails — the model invents a generic answer because it doesn't see
memory hits.

**Proposal.** Add `"historical_context": report.historical_context` to the
`facts` dict. Two-line change in `providers.py:_build_qa_prompt`.

**Effort.** ~30 min.

**Risk.** None — already-redacted strings going into an already-prompt.

---

### P0-3 · Pre-filter findings to the question's category

**Current state.** Every ask call sends **all** active findings to the model.
For `/codeguardian explain database risk` we already filter
(`handlers.explain`), but the free-form ask path doesn't.

**Why it matters.** On a PR with 12 findings spread across 4 categories,
asking *"which database changes are risky?"* gives the model 8 irrelevant
findings to wade through, which costs tokens and dilutes the answer.

**Proposal.**
- Lightweight heuristic in `_build_qa_prompt`: scan the question for
  category aliases (reuse `parser._CATEGORY_ALIASES`).
- When one is mentioned, prepend `findings_relevant_to_question:` (filtered)
  ahead of `findings_other:` (the rest). The model still sees everything but
  is biased toward the right subset.

**Effort.** ~1 hour + a test that "database risk?" surfaces DB findings first.

**Risk.** None.

---

### P0-4 · Stop the "dump help menu" failure mode for known-question shapes

**Current state.** After the recent change, unknown text → ask mode (good).
But when **no provider is configured**, ask falls back to a generic "needs a
model" message regardless of what the question was.

**Why it matters.** The zero-key path is supposed to stay useful (strict rule
#3). For very common questions ("what changed?", "what tests should I run?",
"is this safe?") we can route to the existing deterministic handlers
(`handlers.summary`, `handlers.tests`, etc.) without ever calling the LLM.

**Proposal.** A 6-line intent-router in `handlers.ask` for the
no-provider branch:

```python
q = question.lower()
if "test" in q:  return handlers.tests(report)
if "block"in q:  return handlers.why_blocked(report)
if "summar" in q or "what changed" in q or "what is" in q:
    return handlers.summary(report) + "\n\n_(Free-form Q&A needs Groq/HF…)_"
# else current fallback
```

**Effort.** ~30 min including 4 tests.

**Risk.** None — just routes among existing deterministic handlers.

---

### P0-5 · `@codeguardian` sunset warning

**Current state.** Parser still accepts the legacy `@codeguardian` trigger for
back-compat. We know it pings a stranger.

**Why it matters.** Every user on `@`-trigger is generating spam pings until
they switch.

**Proposal.** When parser detects `@codeguardian`, post a one-line warning at
the top of the reply: *"Tip: use `/codeguardian` instead. The `@` form pings
an unrelated GitHub user."* Don't break, just nudge.

**Effort.** ~30 min, 1 test.

**Risk.** None.

---

### P0-6 · One-command installer (`gh codeguardian init`)

**Current state.** Onboarding requires the user to:
1. Open [`examples/`](../examples/), pick a workflow, copy it to
   `.github/workflows/codeguardian.yml`.
2. Optionally set `GROQ_API_KEY` / `HF_TOKEN` via the GitHub UI or `gh secret set`.
3. Commit + push.

Three manual steps, each a friction point. The example workflows already exist
and document the right shape — but the user has to know about them.

**Why it matters.** "Add a YAML file to .github/workflows/" is the single
biggest drop-off in adoption. A one-command installer reduces the entire setup
to ~10 seconds and lets us preselect the right workflow per repo language
(JS/TS / Python / monorepo).

**Proposal.** Ship a `gh` CLI extension at a separate repo
`ayushkumar320/gh-codeguardian`:

```bash
gh extension install ayushkumar320/gh-codeguardian
gh codeguardian init
```

What it does:

1. Verifies we're in a git repo with a GitHub remote.
2. Detects language (presence of `package.json` / `pyproject.toml` / `go.mod`)
   and picks the matching workflow from this repo's `examples/`.
3. Writes `.github/workflows/codeguardian.yml`, pinned to `@v0`.
4. Prompts to optionally set `GROQ_API_KEY` via `gh secret set`.
5. Prints next steps: commit, push, open a PR, try `/codeguardian explain`.

**Why a `gh` extension and not npm/PyPI:**
- Our audience (GitHub-PR workflow) almost always has `gh` installed already;
  no separate runtime requirement.
- `gh` extensions can set repo secrets natively (no separate auth flow).
- Zero new release pipeline — `gh` extensions are just git repos that tag
  releases; no PyPI OIDC, no npm publish, no separate maintainer accounts.
- Trade-off: lower discoverability than npm/PyPI registries. Acceptable
  for v1.0; we can add an `npx codeguardian-init` wrapper later if real
  demand surfaces (the extension's `init` logic is the same).

**Effort.** ~half a day total: ~100 lines of Bash for the extension script,
a small README on the extension repo, a smoke test that wires through
`gh codeguardian init --dry-run` on a fresh tempdir, and a one-line install
note in our own README.

**Risk.** Low. The extension only writes one file and (with consent) one
secret. No runtime change to the Action itself.

---

## P1 — Meaningful work, ≤ 1 day each, post-v1.0

### P1-1 · Conversation memory across asks within one PR

**Current state.** Each `/codeguardian <question>` is one-shot. The reply
marker (`commands.loop.reply_marker`) is per-comment; it dedupes replies but
doesn't carry context.

**Why it matters.** Real users have follow-ups: *"expand on the second
point"*, *"so should I add a test for scoreboard or not?"*. Today these
read as fresh questions with no anchor.

**Proposal.**
- New artifact-side helper `commands.loop.load_recent_asks(pr_number, n=5)`
  that pulls the last N `/codeguardian <question>` ↔ bot-reply pairs from
  the PR comment thread (already paginatable via `GitHubClient`).
- Feed those as a `previous_qa: list[{q, a}]` field in the facts dict.
- Bound: only the last 5 pairs, ≤ 800 chars each, all wrapped untrusted.

**Effort.** ~half a day + tests covering "second question references first".

**Risk.** Medium-low. Each round of Q&A widens the prompt; need a hard cap
on aggregate prompt size (already 18k chars). Need to confirm the reply
marker convention is reliable for fetching prior asks.

---

### P1-2 · Inline annotations for high-confidence, localized findings

**Current state.** `policy.noise.allow_inline_annotations: bool = False`
(opted-out default). No code path actually creates annotations on the check.
The MVP blueprint explicitly mentioned annotations as a real surface and we
defer them everywhere.

**Why it matters.** "10/10 critical" with a sticky comment is good for the
big picture but doesn't put the finding *next to the line*. For surface
bugs (forbidden import on this line, layer violation on that line) annotations
are dramatically clearer.

**Proposal.**
- Only emit annotations for findings where:
  - `severity >= medium`, AND
  - `confidence >= 0.7`, AND
  - the finding has exactly 1 evidence file with a resolvable line number.
- New `GitHubClient.update_check_with_annotations()` (GitHub's API allows up
  to 50 per request).
- Gated by `policy.noise.allow_inline_annotations` — change the default to
  `True` once the heuristic above is tested on a few real PRs.

**Effort.** ~half to a full day. Surface-area work: line resolution from
patches, API plumbing, dedupe against previous runs.

**Risk.** Medium. Annotations are noisier than comments if heuristic is off;
keep the bar high.

---

### P1-3 · Reaction-based feedback on the sticky comment

**Current state.** Phase 12 plan calls for a feedback loop; the only path
today is filing a false-positive / false-negative issue.

**Why it matters.** The bar for a developer to file an issue is high. The
bar to click 👍 or 👎 on the sticky comment is zero. That's the difference
between a beta with 5 feedback datapoints and one with 500.

**Proposal.**
- On every analysis run, the sticky comment gets a small footer:
  *"Was this useful? React with 👍 / 👎 / 😕 (confusing) / 🎯 (caught a real bug)."*
- A periodic GitHub workflow (or a step in the main workflow) reads the
  reactions on past sticky comments via `GET /reactions` and posts a tally
  to the memory branch for later analysis.
- No real-time action; this is a passive metric.

**Effort.** ~half a day.

**Risk.** Low. Pure read of public API; no behavior change on PRs.

---

### P1-4 · Persist + reuse the import graph across runs

**Current state.** Every analysis run walks the repo and rebuilds the import
graph from scratch (`analyzers/imports.build_import_graph`). Phase 10 made it
fast but it's still O(repo).

**Why it matters.** On a 10k-file monorepo this still dominates the run. The
graph is mostly stable; the diff is small.

**Proposal.**
- On every default-branch push, persist the graph as a small JSON sidecar
  on the memory branch (`graph-cache.json`, ~few MB).
- On PR analysis, load the cached graph, then **patch** it for changed files
  (re-parse only those files' imports). Skip the full walk.
- Fallback to a full build if the cache is missing or older than N days.

**Effort.** ~half to a full day + a perf test.

**Risk.** Medium. Cache invalidation is its own problem; mismatch could
produce wrong dependents. Strict: include `ANALYZER_VERSION` in the cache
header and invalidate aggressively when it bumps.

---

### P1-5 · Surface a 1-line "what this PR does" on the check title

**Current state.** Check title is the static `CodeGuardian Risk` (set by
`__main__._publish_check`). Even with a great sticky comment, the merge-box
glance is just a score.

**Why it matters.** Reviewers triage from the merge box. A "10/10 critical:
api/session.py adds new session-TTL surface; 3 findings" line *there*
beats forcing them to expand.

**Proposal.**
- After the summarizer runs, take the first 80 chars of the narrative and
  use it as the check `output.title` (separate field from name).
- Empty title falls back to the current static text.

**Effort.** ~1 hour + a test.

**Risk.** None — `output.title` is independent of `name`, which is what
branch protection matches against.

---

### P1-6 · Smart patch budgeting: pull hunks around symbols in findings

**Current state.** The first N chars of each patch goes into the ask prompt.
A function rename buried 200 lines into a 5k-line patch gets dropped.

**Why it matters.** For mid-to-large PRs, the model loses the actual changed
symbol because the budget runs out on the first hunk.

**Proposal.**
- New `models.DiffSummaryFile.relevant_hunks: list[str]` populated by
  pulling the hunks that touch any symbol named in a finding's
  `evidence_files` or any path under a high-risk pattern. Fall back to the
  current truncation only when no findings exist.

**Effort.** ~half a day; needs careful patch parsing (already have
`pr.diff._split_patches`).

**Risk.** Low.

---

## P2 — Bigger investments, behind beta-feedback signal

### P2-1 · Finish Python analyzer parity

Tracked in [POST-V1-ROADMAP.md](POST-V1-ROADMAP.md). Concretely:

- Python types-breaking-change (Protocol / TypedDict / `@dataclass` field
  renames). Real ~2 day effort: needs an AST-level parser, not regex.
- Python ORM migration risk (Alembic ops detection, Django migrations).
- Python web-framework route shape diff (FastAPI / Flask / Django).

**Effort.** 2-4 days each. **Risk.** Medium per analyzer (false-positive risk
on heuristic-y categories).

---

### P2-2 · Go support (imports + tests, then arch)

A second language unlocks "we support 3 languages" marketing claim and
exercises the language-pack abstraction we built. Imports are tractable
(import paths are URL-like, resolvable against `go.mod`). Tests follow
`_test.go` convention.

**Effort.** ~1-2 days for dep + tests + arch.

---

### P2-3 · OpenAPI / GraphQL schema-diff analyzer

The current API analyzer is route-shape heuristic. A real schema-diff (using
`oasdiff`-style logic against committed `openapi.yaml` / SDL) is a strict
upgrade for any team that ships schemas.

**Effort.** ~2 days. Out of pure MVP scope; ship as an opt-in.

---

### P2-4 · `/codeguardian show <symbol-or-path>` command

A deterministic command that renders the relevant diff hunk inline in a
reply, with the analyzer findings for that file/symbol underneath. Zero LLM;
helps the *zero-key* path produce something visually rich.

**Effort.** ~half a day.

---

### P2-5 · Cost telemetry per PR

Currently no observability into LLM cost per PR. For paid Groq users / HF
pro this matters before scaling.

**Effort.** ~half a day. Adds `report.provider_usage` rendering on the check
summary footer.

---

### P2-6 · Confidence calibration from patch context

Today `Finding.confidence` is set by analyzer-side heuristics
(`analyzers/imports._grade`, etc.) and is independent of how surgical the
diff actually is. A whitespace-only change in a file with 200 dependents is
treated identically to a signature rename in the same file.

**Proposal.** Post-process every finding: if its evidence files are touched
only by additions/deletions that match `^[ \t]*$` or `^[ \t]*//.*$`, reduce
confidence by 0.2. This is genuinely deterministic and explainable.

**Effort.** ~half a day. Real false-positive reduction signal.

---

## Cross-cutting non-goals (explicitly **not** here)

To keep this list honest, here's what I considered and rejected for the
above list — pinning rationale so we don't accidentally pick them up later:

- **Hosted dashboard / SaaS backend.** Strict rule #8 keeps us
  GitHub-Actions-native. Re-visit only with strong demand.
- **Letting the LLM see raw source files beyond the diff.** Strict rule #2
  + threat model. Free-form Q&A already gets the redacted patch excerpts —
  enough signal without giving the model arbitrary read access.
- **A learned ML risk model.** Out of v1 scope, deferred to
  [POST-V1-ROADMAP](POST-V1-ROADMAP.md).
- **Auto-applying fixes / opening fix PRs.** Out of scope by design
  (CodeGuardian *predicts*, doesn't *modify*).
- **Cross-PR conversation memory** (asks on PR #4 informing PR #7).
  Privacy-loaded; would need a separate memory consent model. Defer.

## Decision log

When picking items off this list, record one line here so future-us knows
why a P1 jumped queue over a different P1:

- 2026-06-30 — Shipped P0-1, P0-2, P0-3 as a single batch. All three touch
  `providers._build_qa_prompt` and the `facts` dict it builds, so bundling
  avoided three near-identical PRs against the same function. P0-1 added
  `body` to `PrContext` + redacted/capped parse in `github/events.py`;
  P0-2 surfaces `report.historical_context`; P0-3 uses
  `commands.parser._CATEGORY_ALIASES` to split findings into
  `findings_relevant_to_question` vs `findings_other` when the question
  names a category. Regression tests added in `tests/test_phase12_ask_mode.py`
  and `tests/test_phase7_live_api.py`.
- 2026-06-30 — Shipped P0-4 (zero-key intent router). `handlers.ask` now
  checks `select_provider()` and, on the deterministic (no-key) branch,
  routes common question shapes to existing handlers via
  `_route_no_provider`: "block" → `why_blocked`, "test" → `tests`,
  summary-shaped questions → `summary`, each with a one-line note that
  fuller Q&A needs a key. Anchors are specific ("what is this", not bare
  "what is") so open-ended questions still fall through to the honest
  "needs a model" fallback. 5 tests in `tests/test_phase12_ask_mode.py`.
  Picked over P0-5 because it directly serves strict rule #3 (zero-key path
  stays useful) and shared the warm ask-path context from the P0-1/2/3 batch.
- 2026-06-30 — Shipped P0-5 (`@codeguardian` sunset warning). `parser.parse`
  now records `Command.legacy_mention` from whether the matched trigger
  started with `@` vs `/`; `loop.plan` prepends a one-line nudge
  (`handlers.LEGACY_MENTION_WARNING`) above any reply for the legacy form,
  without breaking it. 3 tests in `tests/test_phase3_commands.py`. With this
  the P0 tier is fully delivered except P0-6 (installer, tracked as a
  separate `gh`-extension repo).
- 2026-06-30 — Cleared the full P1/P2 backlog in four batches (49 new tests
  in `tests/test_improvement_plan.py`):
  - **Batch A** (scoring/report cluster): P1-5 `report.check_title`
    (score+verdict+narrative snippet); P2-6 `calibrate.calibrate_confidence`
    (−0.2 conf for whitespace/comment-only evidence edits, in
    `risk_scoring_agent`); P2-5 `Report.provider_usage` + `report.usage_footer`
    (billable-provider tally on the check).
  - **Batch B**: P1-6 `DiffSummaryFile.relevant_hunks` + `pr.diff.split_hunks`
    (whole hunks for finding-flagged files, preferred by the ask prompt);
    P2-4 `/codeguardian show <path-or-symbol>` (`handlers.show`, parser
    `CommandName.show` + `Command.target`).
  - **Batch C**: P1-2 `report.annotations_from_report` +
    `pr.diff.first_added_line` + `publish_check(annotations=…)` (opt-in via
    `policy.noise.allow_inline_annotations`, high-confidence+localized only);
    P1-3 sticky `FEEDBACK_FOOTER` + `report.reaction_tally` +
    `client.list_comment_reactions`.
  - **Batch D**: P1-1 `loop.load_recent_asks` + `previous_qa` in the ask
    prompt (`client.list_issue_comments`); P1-4 `analyzers/graph_cache.py`
    (sidecar persist + incremental `patch_graph`, env
    `CODEGUARDIAN_GRAPH_CACHE`, `ANALYZER_VERSION`-pinned invalidation).
  - **Languages/schema (first increments, low-FP, removal-only)**: P2-2 Go
    imports+tests in `analyzers/imports.py` + `analyzers/tests.py` (Go arch
    comes free via the shared graph); P2-1 `analyzers/pytypes.py` (Python
    public def/class removal/rename, the Python analog of `types.py`); P2-3
    `analyzers/schema.py` (OpenAPI path/operation + GraphQL type/field
    removals). **Deferred deeper work** (greenlight individually): P2-1's
    AST-level Protocol/TypedDict/dataclass/ORM/route analyzers and P2-3's
    full structural `oasdiff`-style narrowing/required-param diff — both are
    multi-day and FP-prone, so they were scoped to the unambiguous-removal
    slice now rather than shipping noise (core "fewer-but-right" principle).
