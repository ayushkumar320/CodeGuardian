# Phase 0 — Product Contract (Realized Deliverable)

> This is the **filled-in product contract** produced from the Phase 0 spec in
> [phase-0-product-foundation.md](phase-0-product-foundation.md). It answers the
> Product Manager prompt and the Senior Developer prompt. It is the
> single source of truth the implementation team builds against in Phase 1+.
> No code is scaffolded in Phase 0.

Authority: for MVP conflicts, this contract + [PLAN](../../Phase-Wise-Build-Plan.md)
override the [blueprint](../../CodeGuardian-AI-Blueprint.md). See
[CLAUDE.md](../../../CLAUDE.md) strict rules.

---

## 0. One-sentence product

> **CodeGuardian AI tells you what a pull request can break before you merge it —
> with a risk score, the evidence behind it, and the smallest fix — entirely
> inside GitHub.**

Acceptance criterion *"explained in one sentence"* → met by the line above.

---

# Part A — Product Manager Contract

## A1. End-to-end user journey

| # | Step | Surface | What the developer sees |
|---|------|---------|--------------------------|
| 1 | Install | `.github/workflows/codeguardian.yml` | Adds workflow (and optional `.codeguardian/policy.yml`). One commit. |
| 2 | Open / update PR | GitHub PR | `pull_request` event fires the Action. |
| 3 | Analysis runs | GitHub Actions | `CodeGuardian Risk` check enters *in progress*. |
| 4 | Merge decision | PR merge box | `CodeGuardian Risk` check resolves with score + level + blocking status. |
| 5 | Should comment? | — | Decision per [§A5](#a5-comment-behavior-when-to-speak). |
| 6a | Comment (yes) | Sticky PR comment | One comment created or updated in place (progressive disclosure). |
| 6b | Quiet (no) | — | No PR comment. Check still present. |
| 7 | Evidence | Workflow artifact | `codeguardian-report.json` + `.md` uploaded every run. |
| 8 | Interact | PR comment | Developer replies with `@codeguardian <command>`. |
| 9 | Re-run | GitHub Actions | New push (`synchronize`) or `@codeguardian recheck` re-analyzes; stale jobs collapse. |

Surface responsibilities (every surface has exactly one job — acceptance
criterion *"every PR surface has a purpose"*):

| Surface | Answers | Detail level |
|---------|---------|--------------|
| GitHub Check (`CodeGuardian Risk`) | **"Can I merge?"** | Decision only |
| Sticky PR comment | **"Why, and what do I do?"** | Concise, expandable |
| Workflow artifact | **"Show me all the evidence."** | Full JSON + Markdown |
| Debug logs | maintainer diagnostics | Verbose, opt-in |

## A2. PR check states & exact fields

States the `CodeGuardian Risk` check can report:

| GitHub conclusion | When | Meaning |
|-------------------|------|---------|
| `success` | Low risk, or Medium in Advisory | Safe to merge |
| `neutral` | Medium risk, advisory warning | Merge allowed, read the warning |
| `action_required` | High/Critical in Advisory mode | Strongly advised to act; not gating |
| `failure` | High/Critical in Guarded/Strict | **Blocks merge** (when set as a required check) |

Check **summary fields** (always present — the merge-page output contract):

1. Risk score (`X.X / 10`)
2. Risk level (Low / Medium / High / Critical)
3. Merge status (Allowed / Allowed with warning / Blocked by policy)
4. Affected areas (e.g. Auth, Billing, Profile)
5. Top findings (max N, see noise budget)
6. Recommended actions (ranked, smallest-fix-first)
7. How to ask follow-ups (`@codeguardian` command hints)
8. Mode + provider line (e.g. *Guarded mode · deterministic*)

## A3. Risk score rubric

| Score | Level | Default behavior | Check conclusion (by mode) |
|-------|-------|------------------|----------------------------|
| 0.0–3.0 | **Low** | Pass | `success` (all modes) |
| 3.1–6.0 | **Medium** | Warn | `neutral` (advisory/guarded), `neutral` (strict) |
| 6.1–8.5 | **High** | Block in Guarded or Strict | `action_required` (advisory) → `failure` (guarded/strict) |
| 8.6–10.0 | **Critical** | Block in Guarded or Strict | `action_required` (advisory) → `failure` (guarded/strict) |

Score is a **deterministic aggregate** of category scores; the LLM never sets or
overrides the number. Categories (each 0–10, weighted): dependency/blast-radius,
API contract, database/migration, architecture, test coverage gap, history.
Each contributing finding carries a confidence; low-confidence findings are
down-weighted, never silently dropped.

## A4. Sticky comment structure

One comment per PR, marked with the hidden anchor for idempotency:

```markdown
<!-- codeguardian-ai-summary -->
## CodeGuardian AI — Risk Report

**Risk: 8.2 / 10 · High**  ·  **Merge: Blocked by policy (Guarded)**
Affected: Auth · Billing · Profile

**Top actions**
1. Add profile API regression test
2. Review Prisma migration rollback path
3. Run billing integration suite

<details><summary>Findings & evidence</summary>

- `CG-API-004` API Contract · High · confidence 0.82
  Evidence: apps/api/profile/route.ts, apps/web/profile/ProfileBilling.tsx
  Action: Add profile API regression test · Blocking: yes (Guarded, Strict)
...
</details>

<details><summary>Suppressed findings</summary> ... </details>

---
Ask in this PR: `@codeguardian why blocked` · `tests` · `explain database risk`
_Guarded mode · deterministic · report artifact attached to this run._
```

Docs-only / low-risk fast path replaces the body with a single quiet line:

```markdown
<!-- codeguardian-ai-summary -->
**CodeGuardian Risk: 0.8 / 10 · Low** — docs-only / low-risk change. No action recommended.
```

## A5. Merge blocking policy

Three modes (gradual rollout; default = **Advisory**), set in
`.codeguardian/policy.yml`:

| Mode | Low | Medium | High | Critical |
|------|-----|--------|------|----------|
| **Advisory** (default, week 1) | pass | warn | warn (`action_required`) | warn (`action_required`) |
| **Guarded** | pass | warn | **block** | **block** |
| **Strict** | pass | warn | **block** | **block** (no soft override) |

Rules (acceptance criterion *"blocking behavior is explicit"*):

- Blocking is **opt-in**: it only gates merge when the team marks
  `CodeGuardian Risk` a **required status check** in branch protection.
- A blocked merge always names the **single finding that blocks** and whether a
  test alone clears it or code must change.
- Suppression: maintainers only, requires a reason, scoped to the PR, shown in
  the comment (`@codeguardian ignore <id> reason: ...`).

## A6. Supported `@codeguardian` commands

Limited and memorable (acceptance criterion *"limited and memorable"*):

| Command | Returns | Re-runs analysis? |
|---------|---------|-------------------|
| `@codeguardian help` | This command list, one line each | no |
| `@codeguardian explain` | Why this risk score, in plain language | no (uses last report) |
| `@codeguardian tests` | Recommended tests to run before merge | no |
| `@codeguardian why blocked` | The exact blocking finding + fix | no |
| `@codeguardian summary` | Reposts the concise summary | no |
| `@codeguardian compare` | Δ vs previous run (new/resolved/blockers) | no |
| `@codeguardian recheck` | Fresh full analysis | **yes** |
| `@codeguardian ignore <id> reason: …` | Suppress finding (maintainer only) | no |

`help` response copy (answers the Phase 0 user prompt):

```text
CodeGuardian predicts what this PR can break before merge and shows the evidence.
Commands:
  @codeguardian explain       – why this risk score
  @codeguardian tests         – tests to run before merge
  @codeguardian why blocked   – the finding blocking merge + the fix
  @codeguardian compare       – what changed since the last run
  @codeguardian recheck       – re-run the analysis
  @codeguardian summary       – repost the short report
Full evidence is attached to the run as an artifact.
```

## A7. Bot-noise rules

- **One sticky comment per PR.** Update in place; never post a second summary.
- Reply in-thread **only** to an explicit `@codeguardian` command.
- **Ignore bot-authored comments** (no loops).
- **Quiet by default**: no long comment for docs-only or Low-risk changes.
- Noise budget (policy-tunable): max findings in check, max in comment, whether
  Medium risk comments, whether inline annotations are allowed.
- **Inline annotations only** for high-confidence, localized findings.
- Read-only commands answer from the **last saved report** — they don't re-run.

## A8. MVP acceptance criteria

- [ ] Repo installs the workflow and CodeGuardian runs on every PR update.
- [ ] Merge box shows the `CodeGuardian Risk` check with score + level + status.
- [ ] One sticky comment, created/updated without duplicates, when policy allows.
- [ ] `explain`, `tests`, `recheck` all work via PR comment.
- [ ] LangGraph orchestrates the pipeline; deterministic nodes own evidence.
- [ ] Groq → Hugging Face → deterministic routing works; **zero-key path works**.
- [ ] Blocking works through required GitHub checks (opt-in).
- [ ] Every finding cites evidence; no LLM-only findings.
- [ ] Useful without leaving GitHub.

## A9. Open questions (carried into Phase 1)

- Exact category weights for the score aggregate (tune against fixtures).
- Default noise-budget numbers (N findings in check vs comment).
- Whether `compare` requires the previous artifact to still be retained by GitHub.

---

# Part B — Senior Developer Technical Foundation

> Plan only. No code created in Phase 0. Stack remains a **recommendation** until
> the user confirms (CLAUDE.md rule #9).

## B1. Repository structure (proposed)

```text
.github/workflows/codeguardian.yml   # the workflow users copy / reusable caller
action.yml                           # composite/JS Action metadata (Phase 6)
src/
  index.ts                           # Action entrypoint
  github/                            # checks, sticky comment, artifacts, events
  pr/                                # diff fetch, file classification, context
  analyzers/                         # deterministic: imports, tests, db, api, arch
  graph/                             # LangGraph nodes, shared state
  providers/                         # router: groq | huggingface | deterministic
  scoring/                           # risk aggregation
  report/                            # check summary, comment, artifact builders
  policy/                            # .codeguardian/policy.yml loader + defaults
  security/                          # secret redaction, prompt-injection guards
  commands/                          # @codeguardian parser + handlers (Phase 3)
test/
  fixtures/                          # sample PR diffs + expected reports
.codeguardian/policy.yml             # example policy
```

## B2. Workflow triggers

```yaml
on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
  pull_request_review_comment:
    types: [created]
  issue_comment:
    types: [created]
  workflow_dispatch:
concurrency:                         # collapse stale runs per PR head
  group: codeguardian-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
```

## B3. Required permissions

```yaml
permissions:
  contents: read
  pull-requests: write
  checks: write
  issues: write
  actions: read
```

Secrets (both optional — absence triggers the next fallback):
`GROQ_API_KEY`, `HF_TOKEN`. Policy mode lives in the policy file, not secrets.

## B4. Data contracts

```ts
// PR context
interface PrContext {
  owner: string; repo: string; number: number;
  baseSha: string; headSha: string; installationId?: number;
}
interface DiffFile { path: string; status: 'added'|'modified'|'removed'|'renamed';
  additions: number; deletions: number; patch?: string;
  category: 'frontend'|'backend'|'config'|'database'|'test'|'docs'|'types'|'other'; }

// Finding (every field required; evidence non-empty — no evidence, no finding)
interface Finding {
  id: string;                        // CG-<CATEGORY>-<NNN>, stable per PR
  category: 'dependency'|'api'|'database'|'architecture'|'test'|'history';
  severity: 'low'|'medium'|'high'|'critical';
  confidence: number;                // 0..1
  evidence: string[];                // file paths / graph edges / rules (>=1)
  action: string;                    // smallest recommended fix
  blocking: { guarded: boolean; strict: boolean };
  suppressed?: { by: string; reason: string };
}

// Report
interface Report {
  schemaVersion: string; analyzerVersion: string;
  pr: PrContext; mode: 'advisory'|'guarded'|'strict';
  provider: 'groq'|'huggingface'|'deterministic';
  risk: { score: number; level: 'low'|'medium'|'high'|'critical';
          confidence: number; blocking: boolean };
  affectedAreas: string[]; findings: Finding[]; actions: string[];
  dedupeKey: string;                 // installation/repo/pr/headSha/analyzerVersion
}

// Comment
interface StickyComment { anchor: '<!-- codeguardian-ai-summary -->';
  body: string; commentId?: number; }
```

## B5. LangGraph state shape

```ts
interface CodeGuardianState {
  pr: PrContext;
  diff: { files: DiffFile[]; stats: { files: number; additions: number; deletions: number } };
  repository: { languageSummary: Record<string, number>; frameworkSummary: string[];
    packageManifests: string[]; testFiles: string[] };
  evidence: { dependency: Finding[]; api: Finding[]; database: Finding[];
    architecture: Finding[]; test: Finding[]; history: Finding[] };
  risk: { score: number; level: string; confidence: number; blocking: boolean };
  report: { checkSummary: string; prComment: string; annotations: unknown[] };
}
```

MVP node order: `collect_pr_context → classify_changes → dependency_scan →
test_recommendation → risk_score → llm_summarize → publish_result`. Deterministic
nodes run first and populate `evidence`; the LLM node only synthesizes `report`.

## B6. Provider router config

Priority: **Groq → Hugging Face → deterministic**.

```ts
function pickProvider(env): Provider {
  if (env.GROQ_API_KEY) return groq;       // fast chat completion
  if (env.HF_TOKEN)     return huggingface; // free/open + embeddings
  return deterministic;                      // templates, no network
}
```

Every provider returns through one **schema-validated** path (Zod). On invalid
JSON / timeout / error → retry once, then fall through to the next provider, and
ultimately to deterministic. The score and findings come from analyzers, so an
LLM failure degrades wording, never correctness.

## B7. Deterministic fallback behavior

- Runs all static analyzers; builds findings, score, and report from rules only.
- Summaries are **template-based**; deep NL reasoning is skipped.
- Report is clearly labeled: *"deterministic mode — no model provider configured."*
- This is the **baseline product**: it must fully work with zero keys (rule #3).

## B8. Security rules for untrusted PR content

- Treat all repo code, diffs, and PR/comment text as **untrusted input**.
- Repo text can never override system instructions (prompt-injection defense).
- **Redact secrets** before any model call; never log raw secrets or full source.
- Require structured JSON from model nodes; **validate every response**.
- Never execute model-suggested commands.
- **No analyzer evidence → no finding**, regardless of model output.
- Idempotency: dedupe by `installation/repo/pr/headSha/analyzerVersion`; collapse
  stale jobs (B2 concurrency); one sticky comment, one reply per command.

---

## Traceability to acceptance criteria

| Phase 0 acceptance criterion | Where met |
|---|---|
| Explained in one sentence | §0 |
| Every PR surface has a purpose | §A1 surface table |
| Risk levels easy to understand | §A3 |
| Blocking behavior explicit | §A5 |
| Commands limited & memorable | §A6 |
| Team can implement without ambiguity | Part B (B1–B8) |
