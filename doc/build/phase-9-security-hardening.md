# Phase 9: Security & Supply-Chain Hardening

## Objective

Make CodeGuardian safe to run on untrusted PRs (including public repos and forks)
and safe to depend on as a supply-chain component.

## Scope

Included:

- **Fork-PR safety:** confirm secrets are never exposed to fork-originated code;
  document the `pull_request` (safe, no secrets) vs `pull_request_target`
  (dangerous) distinction and which we use; never check out and execute untrusted
  PR code.
- **Prompt-injection defense (extend):** dedicated test corpus of malicious repo
  text / PR comments attempting to override instructions, exfiltrate secrets, or
  fabricate findings; assert the model layer ignores them and no finding lacks
  evidence.
- **Output safety:** scan generated comment/check text for secret patterns before
  posting (defense in depth on top of input redaction).
- **Supply chain:** pin all third-party Actions to commit SHAs; add Dependabot;
  pin Python deps with hashes; generate an SBOM; CodeQL on this repo; sign
  release artifacts / tags.
- **Least privilege:** document the minimal `permissions:` and when each is
  needed; make `contents: write` (memory) optional.
- **SECURITY.md** with disclosure policy; a written threat model.

Excluded:

- Enterprise SSO/SAML, secret vaults (out of MVP/Action scope).

## Deliverables

- `SECURITY.md`, `THREAT-MODEL.md`.
- Prompt-injection test corpus + tests.
- Output secret-scan step before any post.
- SHA-pinned actions; Dependabot config; CodeQL workflow; SBOM in releases;
  signed releases.
- A "permissions explained" section in INSTALL.

## Senior Developer Prompt

```text
You are security-hardening CodeGuardian (Phase 9).
Read CONTEXT-GRAPH.md, then ROOT, PLAN, WFI security sections, and the code map.

Deliver:
- Fork-PR safety verification + docs (pull_request vs pull_request_target).
- Prompt-injection corpus + tests proving model output never creates
  evidence-free findings and never leaks secrets.
- Pre-post output secret scan.
- SHA-pinned actions, Dependabot, CodeQL, SBOM, signed releases.
- SECURITY.md + threat model + minimal-permissions doc.

Return: design, files, tests, threat model.
```

## Acceptance Criteria

- Demonstrated: a fork PR cannot access secrets and cannot cause CodeGuardian to
  execute its code.
- The prompt-injection corpus produces no fabricated or evidence-free findings and
  no secret leakage.
- Generated outputs are secret-scanned before posting.
- All actions are SHA-pinned; releases are signed; SBOM is published.
- SECURITY.md and a threat model exist and are linked from the README.
