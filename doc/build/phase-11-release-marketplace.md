# Phase 11: Release Engineering & Marketplace

## Objective

Make releases automated, versioned, and reproducible, and publish CodeGuardian to
the GitHub Marketplace with a polished listing.

## Scope

Included:

- **Dependency packaging:** replace per-run `pip install` of the source with a
  robust, fast, reproducible install. Options to evaluate: a prebuilt Docker
  container action, or vendored/locked wheels installed from a pinned lockfile.
  Goal: no PyPI resolution flakiness, fast cold start, reproducible.
- **Release automation:** a tag-triggered workflow that runs CI, builds the
  artifact, generates release notes from CHANGELOG, creates the GitHub Release,
  and moves the `v1` major tag.
- **Versioning policy:** finalize SemVer rules (already drafted in ../RELEASING.md);
  document the `@v1` vs `@v1.2.3` consumer contract.
- **Marketplace listing:** `action.yml` metadata polish, categories, an icon,
  README badges, screenshots/GIF of a real PR run, and a concise listing
  description.
- **Examples:** ready-to-copy workflows for public repos, private repos, monorepos,
  and "required check" branch protection.

Excluded:

- Paid tiers / billing (SaaS scope).

## Deliverables

- A reproducible dependency-packaging approach (Docker image or locked wheels)
  with a documented rationale.
- `.github/workflows/release.yml` automating the release + `v1` tag move.
- Marketplace-ready `action.yml`, listing copy, screenshots, and badges.
- An `examples/` set of workflows.

## Senior Developer Prompt

```text
You are productionizing CodeGuardian's release pipeline (Phase 11).
Read CONTEXT-GRAPH.md, then ROOT, PLAN, archived P6, ../RELEASING.md, and the code map.

Deliver:
- Reproducible, fast dependency packaging (Docker container action or pinned
  wheel lockfile) replacing per-run pip-from-source; document the trade-off.
- A tag-triggered release workflow: CI -> build -> notes from CHANGELOG ->
  GitHub Release -> move v1 tag.
- Marketplace listing assets (metadata, icon, screenshots, badges, examples).

Return: packaging decision + plan, release workflow, listing assets, examples.
```

## Acceptance Criteria

- A tagged commit produces a GitHub Release automatically, with notes and a moved
  `v1` tag, with no manual steps beyond pushing the tag.
- The Action installs reproducibly and starts fast (no live PyPI resolution at
  run time).
- The Marketplace listing is complete (icon, description, screenshots, examples).
- Consumers can pin `@v1`, `@v1.x.y`, and copy a working example in minutes.
