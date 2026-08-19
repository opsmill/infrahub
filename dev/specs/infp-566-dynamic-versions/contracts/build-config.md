# Contract: Package build configuration

Both packages MUST declare a dynamic version resolved from git tags. The resolver is
`hatch-vcs` (FR-013). This is the public contract a build of either package satisfies.

## `pyproject.toml` (root — `infrahub-server`)

```toml
[project]
name = "infrahub-server"
dynamic = ["version"]          # was: version = "1.10.0"  (field REMOVED, FR-008)
# ...

[build-system]
requires = ["hatchling", "hatch-vcs"]   # hatch-vcs ADDED
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"
fallback-version = "1.10.1.dev0"   # FR-003: raise to next release after E2E validation

[tool.hatch.version.raw-options]
git_describe_command = ["git", "describe", "--tags", "--long", "--match", "infrahub-v*"]

[tool.hatch.build.hooks.vcs]
version-file = "backend/infrahub/_version.py"   # OQ-3
```

> **`--dirty` intentionally omitted.** The Docker build resolves the version against a work tree
> that `.dockerignore` strips of tracked files (`.gitignore`, `.gitmodules`, `.gitattributes`,
> `.github/`, `.devcontainer/`, `development/infrahub.toml`). `git describe --dirty` would report
> that stripped tree as dirty, so setuptools-scm bumped every on-tag image to
> `{next}.devN+g<node>.d<date>` instead of the clean tag. Omitting `--dirty` derives the version
> from committed state only, independent of what the work tree contains.

## `python_testcontainers/pyproject.toml` (`infrahub-testcontainers`)

Identical, plus `raw-options.root = ".."` so it walks up to the repo root for git metadata
(FR-002), and its own version-file path:

```toml
[tool.hatch.version.raw-options]
root = ".."
git_describe_command = ["git", "describe", "--tags", "--long", "--match", "infrahub-v*"]

[tool.hatch.build.hooks.vcs]
version-file = "infrahub_testcontainers/_version.py"
```

## Guarantees (acceptance)

- On tag `infrahub-v<X>` → artifact metadata version is exactly `<X>` (FR-005).
- Past a tag → PEP 440 dev/local version sorting strictly after the tag (FR-006).
- Non-`infrahub-v*` tags ignored (FR-007).
- No reachable tag → build succeeds with the fallback (US3); never fails the build.
- Both packages resolve identical versions from the same tag (FR-001/FR-002).
- `version-file` baked into wheel and sdist; git-ignored (OQ-3).

## Lockfiles

- `uv.lock` (root) and `python_testcontainers/uv.lock` MUST be regenerated (`uv lock`).
- Verified (OQ-2, uv 0.11.6): no `version` is recorded for dynamic members → no per-commit
  churn. Re-verify if uv is upgraded in this change.
