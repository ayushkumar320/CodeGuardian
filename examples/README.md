# CodeGuardian — example workflows

Copy whichever matches your setup into `.github/workflows/codeguardian.yml`.

| File | When to use |
|------|-------------|
| [public-repo.yml](public-repo.yml) | Default. Public repo, zero secrets, deterministic mode. |
| [private-repo-with-groq.yml](private-repo-with-groq.yml) | Private repo + optional Groq summaries (`GROQ_API_KEY` secret). |
| [required-check.yml](required-check.yml) | Same workflow; shows how to turn CodeGuardian into a *required* status check via branch protection. |
| [monorepo.yml](monorepo.yml) | Large monorepo notes — concurrency, perf caps, optional path filters. |

Pin tips:

- `@v0` (recommended) — auto-receives non-breaking updates.
- `@v0.1.0` — exact pin for full reproducibility.
- `@main` — bleeding edge; not for production.

CodeGuardian always works without an LLM token. Add `GROQ_API_KEY` (or
`HF_TOKEN`) only if you want the rephrased one-paragraph summary; the risk
score, findings, and blocking decision are deterministic either way.
