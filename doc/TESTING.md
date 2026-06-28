# Running & Testing CodeGuardian

There are **three** ways to run CodeGuardian, from fastest-to-test to
most-realistic. If you just want to see it work, start with Option A — it needs
**no GitHub account, no token, and no PR**.

CodeGuardian always runs the same entrypoint (`python -m codeguardian`). The only
difference between the modes is *how the PR context is supplied* and *whether
results are posted to GitHub or written to disk*.

```
        diff (git)  ->  deterministic analyzers  ->  risk score  ->  report
                                                                       |
                                   local: writes JSON/MD + job summary  |
                                   action: posts check + sticky comment +
```

---

## Option A — Local dry run (no token, no PR) ✅ start here

This is the right way to **test the analysis** without any GitHub setup. It runs
in deterministic mode (the zero-key baseline) and writes the report to a temp dir
instead of posting it.

### A1. One command (recommended)

```bash
# From the CodeGuardian repo. Analyze the last commit of ANY local git repo:
scripts/run-local.sh /path/to/some/repo

# Or analyze a specific range (base ... head):
scripts/run-local.sh /path/to/some/repo main feature/my-branch

# With no args, it analyzes HEAD~1...HEAD of the current directory:
scripts/run-local.sh
```

It prints the risk line and the paths to `codeguardian-report.json`,
`codeguardian-report.md`, and a `summary.md` (a preview of the GitHub job
summary). Open the `.md` to read the full evidence-cited report.

### A2. The same thing by hand (so you understand what the script does)

CodeGuardian reads the PR context from a GitHub **event JSON** file and computes
the diff with `git diff base...head` inside `GITHUB_WORKSPACE`. To run it locally
you just fake that environment:

```bash
REPO=/path/to/some/repo
BASE=$(git -C "$REPO" rev-parse HEAD~1)
HEAD=$(git -C "$REPO" rev-parse HEAD)
OUT=$(mktemp -d)

cat > "$OUT/event.json" <<JSON
{"number":1,"pull_request":{"number":1,"title":"local test",
  "base":{"sha":"$BASE","repo":{"full_name":"local/repo"}},
  "head":{"sha":"$HEAD","repo":{"full_name":"local/repo"}}}}
JSON

GITHUB_EVENT_PATH="$OUT/event.json" \
GITHUB_EVENT_NAME=pull_request \
GITHUB_REPOSITORY=local/repo \
GITHUB_WORKSPACE="$REPO" \
CODEGUARDIAN_OUT="$OUT" \
GITHUB_STEP_SUMMARY="$OUT/summary.md" \
  python -m codeguardian

cat "$OUT/codeguardian-report.md"
```

**Why no token is fine:** with no `GITHUB_TOKEN`, all GitHub writes become no-ops
(the check/comment are skipped) and the deterministic analyzers still produce the
full report. This is the guaranteed zero-key path.

> **Tip — get an interesting score:** a docs-only or trivial change is correctly
> reported as low risk with no comment. To see findings, analyze a range that
> touches source, adds an API/DB change, or removes a function other files import.

### A3. Run the unit + integration test suite

```bash
pip install -e ".[dev]"   # once
pytest -q                 # builds real throwaway git repos as fixtures
```

---

## Option B — Real GitHub Action on a sandbox repo

This proves the **GitHub surfaces** (check run, sticky comment, artifacts,
`/codeguardian` commands) that a local run cannot. This is the Phase 7 validation
path.

1. **Create a sandbox repo** (a throwaway public repo is easiest).
2. **Add the workflow** — commit `.github/workflows/codeguardian.yml`:

   ```yaml
   name: CodeGuardian Risk
   on:
     pull_request:
       types: [opened, reopened, synchronize, ready_for_review]
     issue_comment:
       types: [created]
   permissions:
     checks: write
     pull-requests: write
     issues: write
     contents: read        # use `write` only if you enable cross-PR memory
     actions: read
   jobs:
     risk:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
           with: { fetch-depth: 0 }   # REQUIRED: full history for the diff
         - uses: your-org/CodeGuardian@v0   # or `uses: ./` if testing in-repo
   ```

   > **Pin `uses:` to your fork/branch while testing.** If you're iterating on
   > CodeGuardian itself, point `uses:` at `your-name/CodeGuardian@your-branch`
   > (or `./` if the Action lives in the same repo), not a release tag.

3. **Open a PR** in the sandbox. Within a minute you should see:
   - a `CodeGuardian Risk` check near the merge box,
   - one sticky comment (skipped for docs-only / low-risk changes — this is
     intended, not a bug),
   - `codeguardian-report.json` + `.md` under the run's **Artifacts**.
4. **Exercise the conversation loop:** comment `/codeguardian explain`,
   `/codeguardian tests`, `/codeguardian recheck`.
5. **(Optional) add a model provider** for nicer prose: set `GROQ_API_KEY` or
   `HF_TOKEN` as repo secrets and pass them to the Action. The score and findings
   never change — models only rephrase the summary.

See [INSTALL.md](INSTALL.md) for the full configuration reference and the
least-privilege permissions table.

---

## Option C — Scripted live validation harness (Phase 7)

For repeatable assertions against a live PR, use the e2e harness. It checks that
the check appears, the sticky comment is upserted (not duplicated), artifacts
exist, and commands reply once.

```bash
export GITHUB_TOKEN=<a token with repo scope on the sandbox>
python e2e/validate_sandbox.py verify-pr --repo owner/sandbox --pr 1 --expect-sticky
python e2e/validate_sandbox.py send-command --repo owner/sandbox --pr 1 \
    --body "/codeguardian tests"
```

There is also a `Phase 7 Sandbox Validate` workflow
(`.github/workflows/phase7-sandbox-validate.yml`) you can trigger via
**workflow_dispatch** to run these checks from CI. See [e2e/README.md](../e2e/README.md)
and [doc/build/phase-7-runbook.md](build/phase-7-runbook.md).

---

## Diagnostics: `--selfcheck`

Verify the runtime can reach its dependencies (git, GitHub token, provider):

```bash
python -m codeguardian --selfcheck
```

It prints a pass/fail line per dependency and exits non-zero if a required one
fails. Set `CODEGUARDIAN_DEBUG=1` on any run for verbose logging (secrets are
always redacted).

---

## Common misconceptions (FAQ)

- **"It needs a GitHub token / a real PR to run."** No — Option A runs the full
  analysis with neither. Tokens only enable *posting* results.
- **"No comment showed up, so it's broken."** CodeGuardian is **quiet by
  default**: docs-only and low-risk changes get the check but no comment. Look at
  the check and the artifact.
- **"I need a hosted server / database / Neo4j."** No. It's a GitHub Action (or a
  local `python -m codeguardian`). There is no always-on service.
- **"`fetch-depth: 0` is optional."** It's required — without full history the
  diff between base and head can't be computed.
- **"Models drive the result."** They don't. Deterministic analyzers own every
  finding and the score; the LLM only rephrases the summary, and the product runs
  fully without any model keys.
- **"The diff range is wrong locally."** It's `base...head`. If you point both at
  the same commit you'll get an empty diff and a 0/10 score.
