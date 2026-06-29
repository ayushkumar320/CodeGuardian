# Support & Triage

## How to get help

| Need | Where |
|------|-------|
| Bug, crash, broken output | [Bug report](https://github.com/ayushkumar320/CodeGuardian/issues/new?template=bug.yml) |
| A finding that shouldn't have fired | [False positive](https://github.com/ayushkumar320/CodeGuardian/issues/new?template=false-positive.yml) |
| Something broke and CodeGuardian missed it | [False negative](https://github.com/ayushkumar320/CodeGuardian/issues/new?template=false-negative.yml) |
| Usage question / idea / discussion | [Discussions](https://github.com/ayushkumar320/CodeGuardian/discussions) |
| Security vulnerability | Privately, via [security advisory](https://github.com/ayushkumar320/CodeGuardian/security/advisories/new) (see [SECURITY.md](SECURITY.md)) |

## Triage process

Every new issue gets a `needs-triage` label until first review.

1. **Triage** (within ~5 working days during beta):
   - Add a category label: `false-positive`, `false-negative`, `bug`, `docs`,
     `enhancement`, `question`.
   - Add severity: `sev-1` (broken / data risk / blocks merge for everyone),
     `sev-2` (degraded for many), `sev-3` (annoyance / edge case).
   - Remove `needs-triage`.
2. **Reproduce + write a failing test** before fixing (for bugs and FPs/FNs).
   The test goes into `tests/` and stays after the fix lands.
3. **Resolve, link the commit, close.** False-positive fixes also get a note in
   the CHANGELOG so consumers see precision is moving the right way.

## False-positive / false-negative bookkeeping (Phase 12 beta)

All `false-positive` and `false-negative` issues feed the beta tuning loop:

- Each is tagged with the analyzer category that fired (or missed).
- Tuning changes (severity, confidence, threshold, default policy) reference the
  issues that motivated them in the commit message.
- We track aggregate counts per category to spot noisy analyzers before GA.

## Beta scope (until v1.0)

- API is still semver-pre-`1.0`. Minor versions may change defaults; we'll call
  it out in the CHANGELOG when they do.
- No SLAs. Response times are best-effort.
- Public-only issue tracker. For private feedback, open a discussion or email
  the maintainer.
