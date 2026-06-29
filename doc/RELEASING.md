# Releasing CodeGuardian

CodeGuardian is consumed as a GitHub Action (`uses: ayushkumar320/CodeGuardian@vX`),
so it follows the standard Action release convention: immutable version tags plus
a moving major tag.

## Versioning

[Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking change to inputs, policy schema, finding IDs, or behavior
  a consumer relies on.
- **MINOR** — new analyzers, commands, or policy keys (backward compatible).
- **PATCH** — bug fixes, copy, internal changes.

## Cutting a release (automated, Phase 11)

1. Ensure `main` is green (CI: tests on 3.11/3.12, lockfile sync, Action smoke run).
2. Move the `[Unreleased]` section of [CHANGELOG.md](../CHANGELOG.md) under the new
   version with today's date.
3. Bump `version` in `pyproject.toml` to match.
4. Commit both, then push a SemVer tag:

   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```

That's it. [`.github/workflows/release.yml`](../.github/workflows/release.yml) runs
on the tag and:

- Re-runs the full test suite.
- Verifies the tag matches `pyproject.toml`'s version.
- Extracts the matching CHANGELOG section as the release notes.
- Creates the GitHub Release.
- Force-updates the major alias (`v0` → `v0.1.0`) that consumers pin to.

If you need to publish the Marketplace listing, do that **once** from the GitHub
Release UI after `v0.1.0` lands. Subsequent releases inherit the listing.

## What consumers pin

- `@v0` — recommended; gets non-breaking updates automatically.
- `@v0.1.0` — exact pin for reproducibility.
- `@main` — bleeding edge; not recommended.

## Lockfile

`requirements.lock` pins every dependency the Action installs at run time. After
adding/removing/upgrading a dep in `pyproject.toml`:

```bash
pip install pip-tools
pip-compile --strip-extras --output-file=requirements.lock pyproject.toml
```

CI's `lockfile` job verifies it stays in sync.
