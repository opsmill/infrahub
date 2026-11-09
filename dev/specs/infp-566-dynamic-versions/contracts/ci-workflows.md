# Contract: CI/CD workflow behavior

## Tag fetch (FR-014) — the cross-cutting precondition

Audit finding: **no checkout in `.github/workflows/` currently sets `fetch-depth: 0` or
`fetch-tags: true`** (most use `submodules: true`/`recursive`). Every checkout whose job
**builds, publishes, or reads** a package version MUST fetch full history + tags, or it
resolves the fallback. `fetch-depth: 0` fetches reachable tags; add `fetch-tags: true` as
belt-and-suspenders.

Checkouts that MUST be fixed (resolver runs there):

| Workflow | Checkout | Why |
|---|---|---|
| `publish-pypi.yml` | `:51` (`submodules: true`) | runs `uv build` (`:62`) + `uv publish` (`:71`) — **produces the published artifacts** |
| `ci-docker-image.yml` | `:80` (`ref` + `submodules: recursive`) | builds images; reused by all docker-publish workflows + `release.yml` |
| `release.yml` | `:29` (`submodules: true`) | `check_release` reads version for gating |
| `update-compose-file-and-chart.yml` | `:34` | reads version for propagation |
| `ci.yml` `infrahub-testcontainers-check` | `:386` | only if the version-read step is retained (it is replaced, below) |

Re-grep all checkouts at implementation time; fix any other job that builds/publishes/reads
a version.

## `uv version --short` migration (FR-018)

`uv version` reads `[project].version`, which no longer exists → it fails. Replace **all 9
invocations** with installed metadata
(`python -c "import importlib.metadata; print(importlib.metadata.version('infrahub-server'))"`):

- `ci.yml:405,409` (the "Compare package versions" step, `:403-418`)
- `release.yml:49,50,51,52` (`:52` invokes twice — 5 total)
- `update-compose-file-and-chart.yml:52,53`

The prerelease/devrelease gating in `release.yml` (`:46-58`, the `Version(...).is_prerelease`/
`.is_devrelease` logic) and the equivalent in `update-compose-file-and-chart.yml` MUST keep
working — migrate the read mechanism only, do not drop the gate.

## `ci.yml` "Compare package versions" (`:403-418`) — FR-018

Tautological once both packages resolve from the same tag. Either remove it, or replace with a
static check that both `pyproject.toml` files declare the same `git_describe_command` match
pattern and the same hatch-vcs config.

## `release.yml` publish guards (FR-018) — MUST add, hard preconditions

The tag-vs-pyproject check (`:60-64`) becomes tautological. Replace/broaden with two guards
on the publish job, both reading installed metadata:

- **(a) Fallback guard**: fail if the resolved version's **base** equals the fallback base
  (`1.10.1`) AND it is a dev/local release. (Empirical: a `.git`-present miss yields
  `1.10.1.devN+g….d…`, not the literal `1.10.1.dev0` — compare the base, not a literal.)
- **(b) Tag-match guard**: fail if resolved version ≠ the pushed tag's version segment
  (`infrahub-v1.10.0` ⇒ resolved MUST be `1.10.0`). Catches maintenance-hygiene violations.

Both MUST fail the workflow (not warn) and both MUST be present (defense in depth).

## `update-compose-file-and-chart.yml` — FR-019

- **Trigger**: migrate from `push`/`pull_request` on `stable` filtered to
  `paths: [pyproject.toml]` (`:8-18`) — which will never fire once `pyproject.toml` stops
  changing on releases — to **`push` on `infrahub-v*` tags**.
- **Cutover ordering**: this trigger migration MUST land in the same commit as
  (or an earlier commit on the same release-train branch than) FR-001/FR-002.
- **Prerelease/dev gate**: preserve the `is_prerelease == 0 && is_devrelease == 0` conditionals
  (`:55-60,77,85,89`) via the migrated PEP 440-aware read.
- **Remove** the "Update Versions in python_testcontainers/pyproject.toml" step (`:61-62`,
  FR-016).
- **Maintenance scope (FR-022)**: run propagation only when the tag commit is an ancestor of
  `stable` (main-line). Maintenance-branch tags bypass propagation.

## Docker-building workflows (FR-020)

`ci-docker-image.yml` (reused by `publish-preview-dev-docker-image.yml`,
`publish-dev-docker-image.yml`, `schedule-publish-docker-image.yml`, and `release.yml`'s
docker publish) MUST fetch tags at `:80`. The Dockerfile bind-mount (OQ-1) makes the resolver
read `.git/` at build time.
