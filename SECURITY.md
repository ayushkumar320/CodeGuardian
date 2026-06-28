# Security Policy

CodeGuardian runs as a GitHub Action on pull requests, where it is exposed to
**untrusted input** (PR diffs, file contents, and `@codeguardian` comments). This
document describes how we keep it safe to run and safe to depend on, and how to
report a vulnerability.

## Reporting a vulnerability

Please report security issues **privately**, not via public issues or PRs:

- Use GitHub's **"Report a vulnerability"** (Security → Advisories) on this repo, or
- email the maintainer listed in the repository profile.

Include a description, affected version/commit, and reproduction steps. We aim to
acknowledge within **5 business days** and to ship a fix or mitigation for
confirmed high-severity issues promptly. Please give us reasonable time to remediate
before any public disclosure.

Supported for fixes: the latest released `v1` line and `main`.

## Security model (how CodeGuardian stays safe)

- **All repository content is untrusted.** Diffs, source, and comments are treated
  as data, never instructions. Untrusted text sent to a model is fenced with
  explicit "data only, never instructions" markers (`security.wrap_untrusted`).
- **Deterministic-first.** Static analyzers own all evidence; the LLM only
  rephrases the summary. A model can **never** create a finding or change the
  score — findings without analyzer evidence are rejected at the schema boundary
  (`models.Finding` requires non-empty `evidence_files`).
- **Secret redaction on both input and output.** Secret-shaped content is redacted
  before any model call (ingress) **and** scrubbed from every check/comment/reply
  before posting (egress, `security.safe_output`). Secrets are never logged at any
  level — the logger runs a redaction filter on every record.
- **Fork-PR safety.** CodeGuardian is designed for the `pull_request` event, which
  gives fork PRs a read-only token and no secrets. It never uses
  `pull_request_target`, and never checks out or executes PR code — it only reads
  the diff and runs static analysis. On fork PRs, check/comment/memory writes are
  skipped rather than failing noisily.
- **Least privilege.** The Action requests the minimum `permissions:`; cross-PR
  memory (`contents: write`) is optional and can be disabled. See the
  "Permissions explained" section in [INSTALL.md](INSTALL.md).
- **Never crash, never block on our own bug.** Internal errors degrade to a neutral
  check and exit 0 (Phase 8), so a CodeGuardian failure can't be used to block or
  force a merge.

## Supply-chain hardening

- Third-party Actions are **pinned to commit SHAs** (with a version comment).
- **Dependabot** ([.github/dependabot.yml](.github/dependabot.yml)) keeps the
  Action SHAs and Python deps current.
- **CodeQL** ([.github/workflows/codeql.yml](.github/workflows/codeql.yml)) scans
  this repository on push, PR, and weekly.

See [THREAT-MODEL.md](THREAT-MODEL.md) for the detailed threat analysis.
