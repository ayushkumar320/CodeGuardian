# Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No `CodeGuardian Risk` check appears | Workflow didn't trigger, or wrong events | Confirm the workflow `on.pull_request.types` includes `opened`/`synchronize`; check the Actions tab for a run |
| Check runs but no PR comment | Docs-only / low-risk change (quiet by default), or policy noise budget | Expected. Set `noise.skip_comment_for_docs_only: false` to always comment |
| "deterministic mode" notice though I set a key | Secret not exposed to the job, or wrong name | Pass `groq-api-key: ${{ secrets.GROQ_API_KEY }}` via `with:`; confirm the secret exists |
| Empty / wrong diff, everything looks unchanged | Shallow checkout | Use `actions/checkout@v4` with `fetch-depth: 0` |
| `/codeguardian recheck` says permission denied | Not a maintainer | `recheck` and suppressing blockers need OWNER/MEMBER/COLLABORATOR |
| Memory / "has this happened before?" never finds anything | First runs (empty memory), or `contents: write` missing | Memory builds over time; ensure the workflow has `contents: write` or set `memory.enabled: false` |
| Merge isn't blocked despite High/Critical | Advisory mode, or check not required | Set `mode: guarded` AND mark `CodeGuardian Risk` a required status check |
| Duplicate bot comments | Not possible by design (sticky anchor) — if seen, multiple workflows | Ensure only one CodeGuardian workflow is installed |
| Action is slow on first run | Cold `pip install` of dependencies | The `cache: pip` setup caches subsequent runs |
| Fork PR shows artifacts but no sticky comment/check update | Fork `pull_request` runs have a read-only token and no secrets | Expected safe degradation. Deterministic analysis still runs, but write operations are skipped on fork-originated PRs |

## Getting more detail

Every run uploads `codeguardian-report.json` (full evidence) and `.md` as
artifacts — download them from the run page to see exactly what was detected and
why. Re-run analysis without pushing via `/codeguardian recheck`.

## Reporting a bug

Open an issue with: the `codeguardian-report.json` artifact, your
`.codeguardian/policy.yml`, and the workflow file. Never paste secrets.
