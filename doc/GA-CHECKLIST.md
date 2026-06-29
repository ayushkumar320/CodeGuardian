# v1.0 GA checklist

Sequence for shipping v1.0. Steps marked **[human]** require external action
(running beta on real repos, accepting feedback, hitting the Marketplace UI);
everything else is in-repo automation.

## 1. Beta runs **[human]**

- [ ] CodeGuardian is enabled on its own repo in advisory mode (dogfood).
- [ ] At least 3 friendly external repos have CodeGuardian installed in advisory
      mode for ≥ 2 weeks of active PR traffic.
- [ ] Real PRs across all these repos have produced a meaningful number of
      findings (low + medium + high mix).

## 2. Feedback loop is active **[human + repo]**

- [x] Feedback issue templates live (`.github/ISSUE_TEMPLATE/`).
- [x] [`SUPPORT.md`](../SUPPORT.md) documents the triage process.
- [ ] At least one round of false-positive / false-negative issues has been
      triaged with category labels and tuning rationale.

## 3. Scoring & threshold tuning

- [ ] Aggregate FP rate per analyzer category is acceptably low (target: under
      ~10 % of fired findings, no analyzer dominating the noise).
- [ ] Any tuning changes to scoring weights, default confidences, or thresholds
      have a commit linking to the issues that motivated them.
- [ ] Default `policy.yml` (no consumer overrides) confirmed quiet on a
      docs-only PR and informative on a high-risk PR across all beta repos.

## 4. P7 pre-release gate **[human]**

Phase 7's live-API validation is partially complete (public deterministic path
green). Before GA, the remaining gates must run on a real sandbox:

- [ ] **Sticky comment + upsert** on a findings PR (no duplicates across pushes).
- [ ] **Command loop** on `/codeguardian`: `explain`, `tests`, `recheck`,
      `ignore`, `compare` each reply once.
- [ ] **Private repo** behavior.
- [ ] **Fork PR safety**: read-only token, no write attempts, no crash.

See [doc/build/archive/phase-7-runbook.md](build/archive/phase-7-runbook.md).

## 5. Docs & policy

- [x] README badges; quick-start covers the zero-key path.
- [x] [`examples/`](../examples/README.md) workflows for public / private+Groq /
      required-check / monorepo.
- [x] [`SECURITY.md`](../SECURITY.md), [`THREAT-MODEL.md`](THREAT-MODEL.md),
      [`SUPPORT.md`](../SUPPORT.md), [`RELEASING.md`](RELEASING.md).
- [ ] [`POST-V1-ROADMAP.md`](POST-V1-ROADMAP.md) reviewed (what we are explicitly
      *not* doing in v1.0).

## 6. Release & announce **[human]**

- [ ] CHANGELOG `[Unreleased]` collapsed under `[1.0.0]` with today's date.
- [ ] `pyproject.toml` version bumped to `1.0.0`.
- [ ] Push tag `v1.0.0` — [`release.yml`](../.github/workflows/release.yml) does
      the rest (tests, notes, GitHub Release, move `v1` major alias).
- [ ] Marketplace UI: publish from the v1.0.0 Release page. One-time per project.
- [ ] Announcement (blog / Discussions / social).

## 7. Post-GA hygiene

- [ ] Re-baseline `bench/` and update the budgets in `bench/README.md`.
- [ ] Confirm Dependabot + CodeQL are still running clean on `main`.
- [ ] Tag a `support/v1` triage rotation if multiple maintainers exist.
