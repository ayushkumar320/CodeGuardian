# Installing CodeGuardian AI

> **In one minute:** CodeGuardian runs on every pull request, predicts what the
> change can break, and posts a `CodeGuardian Risk` check plus one sticky comment
> — entirely inside GitHub. It works with **zero model keys** (deterministic
> mode) and never blocks merges until you opt in.

Target: a new user is running in **under 10 minutes**.

## 1. Add the workflow (no secrets needed)

Create `.github/workflows/codeguardian.yml`:

```yaml
name: CodeGuardian Risk
on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
  issue_comment:
    types: [created]
permissions:
  contents: write       # write is only for the codeguardian-memory branch
  pull-requests: write
  checks: write
  issues: write
  actions: read
concurrency:
  group: codeguardian-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
jobs:
  risk:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }          # full history is required for the diff
      - uses: your-org/CodeGuardian@v0
        with:
          groq-api-key: ${{ secrets.GROQ_API_KEY }}   # optional
          hf-token: ${{ secrets.HF_TOKEN }}           # optional
```

> If `contents: write` is not allowed by your org, set `memory.enabled: false` in
> the policy (below) and drop the permission back to `read`. Everything except
> cross-PR memory still works.

## 2. Open a test PR

Open any PR. The Action runs in **deterministic mode** (no keys) and:

- adds a `CodeGuardian Risk` check near the merge box,
- posts one sticky comment (skipped for docs-only / low-risk changes),
- uploads `codeguardian-report.json` + `.md` as run artifacts.

First-run success = the check appears and is green/neutral on a small PR, and the
report clearly says *deterministic mode*.

### Fork PR note

For `pull_request` events opened from forks, GitHub provides a read-only token
and no repository secrets. CodeGuardian therefore degrades safely:

- deterministic analysis still runs
- run artifacts are still produced
- check/comment/memory writes are skipped rather than failing noisily

This is the intended safe behavior for untrusted fork-originated code.

## 3. (Optional) Add a model provider

CodeGuardian routes **Groq → Hugging Face → deterministic**. Models only rephrase
the summary — they never set the score or invent findings. Add either secret to
get nicer prose:

- `GROQ_API_KEY` — fast summaries (recommended).
- `HF_TOKEN` — fallback + embeddings.

Repo → Settings → Secrets and variables → Actions → New repository secret.

## 4. Configure (optional): `.codeguardian/policy.yml`

Start from the [example policy](.codeguardian/policy.yml). Most teams only set
`mode`. See the [configuration reference](#configuration-reference) below.

## 5. Roll out blocking gradually

Default is **advisory** (never blocks). When you trust the reports:

1. **advisory** (week 1) — warnings only.
2. **guarded** — blocks High/Critical. Set `mode: guarded` in the policy.
3. **strict** — guarded with no soft override, for critical repos.

## 6. Make the check required (opt-in blocking)

Repo → Settings → Branches → branch protection rule for `main` →
**Require status checks to pass** → select **CodeGuardian Risk**. Now a blocked
analysis (guarded/strict) prevents merge.

## Talk to it in the PR

```
@codeguardian help
@codeguardian explain            @codeguardian explain database risk
@codeguardian tests              @codeguardian why blocked
@codeguardian compare            @codeguardian has this happened before?
@codeguardian recheck            @codeguardian ignore CG-DB-002 reason: column unused
```

`recheck` and suppressing a blocking finding require a maintainer.

## Configuration reference

| Key | Default | Purpose |
|-----|---------|---------|
| `mode` | `advisory` | `advisory` / `guarded` / `strict` |
| `thresholds` | 3.1 / 6.1 / 8.6 | score cutoffs for medium/high/critical |
| `noise.*` | see example | max findings, docs-only skip, medium comments |
| `architecture.forbidden_imports` | `[]` | `paths` cannot import `cannot_import` |
| `architecture.layers` | `[]` | layer-direction rules (`may_import`) |
| `architecture.detect_circular` | `true` | flag import cycles |
| `test_suite_mappings` | `[]` | path glob → suite to run |
| `service_owners` | `[]` | path glob → recommended reviewers |
| `memory.*` | enabled | cross-PR history on a repo branch |
| `ignored_findings` | `[]` | finding IDs pre-suppressed |

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if something looks off.
