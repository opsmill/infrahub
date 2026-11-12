# Quickstart — validating the Git status indicator (IFC-3199)

How to prove this feature works, from cheapest check to most expensive. All paths are
relative to the repository root.

## 1. Unit + component tests (seconds)

```bash
cd frontend/app
pnpm test
```

Expected: the use-case tests cover the three sync verdicts and the requests each one makes;
the component tests cover all five rendered states, the link's filter and branch parameter,
and the header mounting both indicators.

Targeted run while iterating:

```bash
cd frontend/app
pnpm test -- get-repository-sync-health
pnpm test -- repository-sync-status
```

## 2. Type and lint gates (seconds)

These are separate CI jobs and each fails the build independently. `pnpm biome:fix` alone is
**not** the gate.

```bash
cd frontend
pnpm exec biome ci .      # format + lint, whole workspace, as CI runs it
cd app
pnpm knip                 # unused exports/files/deps
pnpm exec betterer ci     # TypeScript regression gate (not plain tsc)
```

`knip` matters here: this feature adds a URL builder and a sync-health use case that are
each imported from exactly one place. If either ends up unreferenced after a refactor, knip
fails.

## 3. Manual check in the running app (minutes)

```bash
cd frontend/app
pnpm dev
```

Walk the five states:

| State | How to reach it |
|---|---|
| `in-sync` | A branch with at least one healthy repository |
| `failing` | A branch with a repository whose sync status is the import-error value |
| `no-repositories` | A deployment with no Git repositories configured |
| `loading` | Throttle the network, or block the count request, and reload |
| `check-failed` | Block the GraphQL endpoint in devtools and reload |

Check specifically, because tests do not cover these:

- The header does not shift when switching between the states (SC-004). Compare against a
  branch in a different state at the same window width.
- Hovering in the `no-repositories` state still shows the tooltip, and the control is still
  focusable by keyboard — it is dimmed, not disabled.
- The indicator reads as distinct from the branch selector beside it, which uses the same
  `mdi:source-branch` glyph. This is a known accepted risk from the spec.

## 4. End-to-end (slowest)

Requires the local stack. No new fixture repository — the test sets an existing repository's
`sync_status` to the import-error value directly.

```bash
# from the repository root — the suite boots its own stack from a local image
uv run invoke dev.build
INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false \
  uv run pytest -c tests/e2e/pytest.ini tests/e2e/repository/test_git_status_header.py
```

Expected: with a repository on the branch carrying the import-error status, the indicator is
in its error state from an arbitrary page, and activating it lands on the repository list
filtered to that repository.

The test mutates shared fixture state, so confirm it restores the status afterwards or runs on
its own branch. A leaked error status would leave later tests in the same session looking at a
repository they did not expect to be broken.

## 5. Full local CI gate before pushing

```bash
cd frontend && pnpm exec biome ci . && cd app && pnpm knip && pnpm exec betterer ci && pnpm test
```

A frontend lint job runs on every PR regardless of paths touched, so this must be green even
if the final diff looks backend-shaped.
