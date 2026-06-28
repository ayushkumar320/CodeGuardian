# CodeGuardian Threat Model

Scope: CodeGuardian running as a GitHub Action on pull requests. The Action reads
a PR diff and repository content, runs deterministic analyzers, optionally calls a
hosted LLM to rephrase a summary, and posts a check run + sticky comment.

## Assets

- The repository's `GITHUB_TOKEN` and any configured provider secrets
  (`GROQ_API_KEY`, `HF_TOKEN`).
- The integrity of the merge decision (check conclusion / risk score).
- The `codeguardian-memory` branch and run artifacts.

## Trust boundaries

- **Untrusted:** PR diff, changed file contents, PR/issue comment bodies, branch
  and file names — anything an external contributor controls.
- **Trusted:** the Action code in this repo, the policy file on the base branch,
  the runner environment for non-fork events.

## Threats and mitigations

| # | Threat | Vector | Mitigation |
|---|--------|--------|------------|
| T1 | **Prompt injection** — repo text/comments override instructions or fabricate findings | Untrusted text reaches the LLM | Text fenced as untrusted data (`wrap_untrusted`); LLM only rephrases; findings require analyzer evidence (`Finding.evidence_files`), so no evidence-free finding can be created. Corpus test in `tests/test_phase9_security.py`. |
| T2 | **Secret exfiltration via output** | Inject content that echoes a secret into the comment/check | Ingress redaction before model calls + **egress** secret-scan (`safe_output`) on every check/comment/reply before posting. |
| T3 | **Secret leakage via logs** | Error messages / debug logs print a token | Logger applies a redaction filter to every record; secrets/full source are never logged (Phase 8). |
| T4 | **Fork-PR privilege escalation** | `pull_request_target` exposing secrets/write token to untrusted code | Use `pull_request` only; never `pull_request_target`. Fork PRs get read-only token, no secrets; writes are skipped. Never check out/execute PR code. |
| T5 | **Code execution from PR content** | Analyzer runs/evaluates untrusted code | Analyzers are static (parse/inspect only); no `eval`, no install/run of PR code. |
| T6 | **Supply-chain compromise of a 3rd-party Action** | A tag is moved to malicious code | All actions pinned to commit SHAs; Dependabot proposes reviewed bumps. |
| T7 | **Dependency compromise** | Malicious PyPI package version | Pinned deps; Dependabot + CodeQL; minimal runtime dependency surface. |
| T8 | **Self-DoS / availability** | Internal bug or hostile diff crashes the Action and blocks merges | Never-crash boundary → neutral check, exit 0 (Phase 8); large-diff caps and timeouts. |
| T9 | **Tampering with the merge decision** | Comment commands force an approve/suppress | Suppressions are accountable (recorded `by`/`reason`); command permissions checked via author association; the score is recomputed deterministically. |

## Non-goals / out of scope

- Enterprise SSO/SAML, secret vaults, runtime sandboxing of the runner itself.
- Defending against a malicious **base-repo maintainer** (they already control CI).
- Guaranteeing detection of every secret format — redaction is conservative and
  best-effort defense-in-depth, not a replacement for proper secret scanning.

## Residual risks

- A novel secret format not matched by the redaction patterns could pass egress
  scanning. Mitigation: patterns are conservative and reviewed; report gaps via
  [SECURITY.md](SECURITY.md).
- A model provider could log prompts on their side. Mitigation: only redacted,
  structured facts (never raw source) are sent, and the provider is optional.
