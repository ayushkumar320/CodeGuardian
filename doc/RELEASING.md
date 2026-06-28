# Releasing CodeGuardian

CodeGuardian is consumed as a GitHub Action (`uses: your-org/CodeGuardian@vX`),
so it follows the standard Action release convention: immutable version tags plus
a moving major tag.

## Versioning

[Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking change to inputs, policy schema, finding IDs, or behavior
  a consumer relies on.
- **MINOR** — new analyzers, commands, or policy keys (backward compatible).
- **PATCH** — bug fixes, copy, internal changes.

## Cutting a release

1. Ensure `main` is green (CI: tests on 3.11/3.12 + Action smoke run).
2. Move the `[Unreleased]` section of [CHANGELOG.md](../CHANGELOG.md) under the new
   version with today's date; bump `version` in `pyproject.toml`.
3. Commit, then tag the immutable version and move the major alias:

   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   # move the major tag consumers pin to:
   git tag -f v0 v0.1.0
   git push -f origin v0
   ```

4. Create a GitHub Release from `v0.1.0` with the changelog section as notes.
   (Marketplace publishing is done from the Release UI once `action.yml` has
   `name`, `description`, and `branding`.)

## What consumers pin

- `@v0` — recommended; gets non-breaking updates automatically.
- `@v0.1.0` — exact pin for reproducibility.
- `@main` — bleeding edge; not recommended.
