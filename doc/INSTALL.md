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

> **`pull_request` vs `pull_request_target`:** always trigger CodeGuardian on
> `pull_request`. That event runs with a read-only token and **no secrets** for
> fork PRs, which is exactly what we want. Do **not** switch to
> `pull_request_target` — it runs with write permissions and repository secrets
> in the context of untrusted PR code, which is a well-known privilege-escalation
> footgun. CodeGuardian never checks out and executes PR code; it only reads the
> diff and runs static analyzers.

### Permissions explained (least privilege)

Grant only what you use. Each scope and why:

| Permission | Why | Drop it if… |
|---|---|---|
| `checks: write` | publish the `CodeGuardian Risk` check run | never — this is the core surface |
| `pull-requests: write` | post/update the one sticky comment | you only want the check, no comment |
| `issues: write` | comment + `@codeguardian` reply API (issue comments) | you disable the conversation loop |
| `actions: read` | read prior run artifacts for cross-PR memory | `memory.enabled: false` |
| `contents: write` | push the `codeguardian-memory` branch only | `memory.enabled: false` → set back to `read` |

The minimal read-only footprint (no comment, no memory) is `checks: write` +
`contents: read`. See [SECURITY.md](../SECURITY.md) and
[THREAT-MODEL.md](THREAT-MODEL.md) for the full security posture.

## 3. (Optional) Add a model provider

CodeGuardian routes **Groq → Hugging Face → deterministic**. Models only rephrase
the summary — they never set the score or invent findings. Add either secret to
get nicer prose:

- `GROQ_API_KEY` — fast summaries (recommended).
- `HF_TOKEN` — fallback + embeddings.

Repo → Settings → Secrets and variables → Actions → New repository secret.

Setting `GROQ_API_KEY` (or `HF_TOKEN`) makes the LLM summary run on **every** PR —
"optional" only means CodeGuardian won't crash without it. If you want a
**guarantee** the model ran and a loud warning when a token is missing (rather
than a silent deterministic fallback), opt in via policy:

```yaml
# .codeguardian/policy.yml
model:
  require_model: true        # warn (degraded) when no provider token is configured
  block_when_missing: false  # set true to also fail the check
```

This stays opt-in so the default product — and **all fork PRs**, which never
receive secrets — keep working with zero keys.

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
