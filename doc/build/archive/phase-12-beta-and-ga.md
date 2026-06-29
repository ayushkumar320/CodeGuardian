# Phase 12: Beta, Tuning & v1.0 GA

## Objective

Validate CodeGuardian's usefulness on real teams, tune the risk model against real
feedback, and ship v1.0 as a trusted, generally-available product.

## Scope

Included:

- **Dogfood:** run CodeGuardian on its own repository and a handful of friendly
  repos in advisory mode.
- **Feedback loop:** a lightweight way to capture false positives / false
  negatives (e.g., `@codeguardian ignore` reasons + a feedback issue template);
  review categories and confidence.
- **Scoring/threshold tuning:** adjust category weights, confidences, and default
  thresholds against observed outcomes to hit a **low false-positive rate** (the
  product's core promise: fewer, right findings).
- **Default policy finalization:** the out-of-box experience (advisory, quiet,
  sensible high-risk paths) confirmed against real repos.
- **GA readiness:** docs complete, support/triage process defined, versioning and
  deprecation policy published, v1.0 tagged and announced.

Excluded:

- Net-new analyzer categories (defer to a post-v1.0 roadmap).

## Deliverables

- A beta report: repos, findings, precision/recall observations, and the tuning
  changes made.
- Tuned default scoring weights/thresholds and default policy.
- Feedback issue template + a documented triage process.
- v1.0 release: tag, changelog entry, announcement, Marketplace GA.
- A short post-v1.0 roadmap (candidate next: more languages, richer specs,
  optional hosted backend — explicitly deferred).

## Product Manager Prompt

```text
You are taking CodeGuardian to v1.0 GA (Phase 12).

Define and run the beta:
- Pick dogfood + beta repos; run in advisory mode.
- Capture false positives/negatives; measure perceived precision.
- Tune scoring weights, confidences, and default thresholds for a low
  false-positive rate without hiding real risk.
- Finalize the default policy and onboarding.
- Define GA criteria, support/triage, and versioning/deprecation policy.

Return: beta plan, tuning recommendations, GA checklist, post-v1.0 roadmap.
```

## Acceptance Criteria

- CodeGuardian has run on real PRs across multiple repos for a beta period.
- Measured false-positive rate is low enough that maintainers trust the findings;
  tuning changes are documented with rationale.
- The default out-of-box experience is confirmed quiet and useful.
- A feedback + triage process exists.
- v1.0 is tagged, changelogged, announced, and live on the Marketplace.
