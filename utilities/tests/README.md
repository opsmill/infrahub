# PR lifecycle tests

Run the standalone Python suite from the repository root with Python 3.14:

```bash
python3.14 -m unittest discover -s utilities/tests -p 'test_pr_lifecycle.py' -v
uv run ruff check utilities/pr_lifecycle.py utilities/tests/test_pr_lifecycle.py
uv run ruff format --check utilities/pr_lifecycle.py utilities/tests/test_pr_lifecycle.py
```

The suite injects time and a recording read transport. It needs no token, network connection,
backend services, or third-party Python packages. Observation collects complete human PR snapshots and excluded bot identities, and fails closed
on missing data, insufficient quota, or exhausted request budgets.

## API fixtures

Files in `fixtures/pr_lifecycle/` are synthetic response fragments, authored from the GitHub
REST/GraphQL field contracts. They are not captured production traffic. All logins, IDs, bodies,
teams, timestamps, and commit hashes are invented; no credentials or private comments are stored.
Top-level keys name scenarios rather than representing an API response envelope.

- `reviews.json`: decisive reviews, subsequent comments, dismissal, and requested users/teams.
- `activity.json`: human comments, edits to bot comments, label changes, and reopening events.
- `mergeability.json`: GraphQL response envelopes for approval, missing requirements, partial
  approval, unknown state, stale head, explicit null versus absent review decision, and errors.
  The expected current REST head for these cases is forty `a` characters.

These fragments seed later behavioral tests. Valid JSON alone does not validate GitHub review,
event, permission, or pagination semantics. Any future recorded fixture must document its source,
capture date, and sanitization here without retaining personal content.

## Pinned upstream processor

`pr_lifecycle_upstream.mjs` executes upstream method bodies with fixture APIs and cache storage.
It requires Node 24 or later with `stripTypeScriptTypes`. It installs no packages and has no live
GitHub transport. Assertions about closure change only local fixture variables.

Prepare sources once in an isolated directory using read-only GitHub CLI requests:

```bash
mkdir -p /tmp/pr-lifecycle-stale-source
gh api 'repos/actions/stale/contents/src/classes/issues-processor.ts?ref=4391f3da665fdf50b6810c1a66712fb9ba21aa93' -H 'Accept: application/vnd.github.raw+json' > /tmp/pr-lifecycle-stale-source/infrahub-stale-processor.ts
gh api 'repos/actions/stale/contents/src/functions/dates/is-date-more-recent-than.ts?ref=4391f3da665fdf50b6810c1a66712fb9ba21aa93' -H 'Accept: application/vnd.github.raw+json' > /tmp/pr-lifecycle-stale-source/infrahub-stale-date.ts
gh api 'repos/actions/stale/contents/src/classes/state/state.ts?ref=4391f3da665fdf50b6810c1a66712fb9ba21aa93' -H 'Accept: application/vnd.github.raw+json' > /tmp/pr-lifecycle-stale-source/infrahub-stale-state.ts
```

Then run offline:

```bash
STALE_SOURCE_DIR=/tmp/pr-lifecycle-stale-source node utilities/tests/pr_lifecycle_upstream.mjs
```

The harness verifies every source hash before executing any upstream method. Expected SHA-256:

| Source filename | SHA-256 |
| --- | --- |
| infrahub-stale-processor.ts | 9545917e652b88e06a64c8c9c10645b25cba5659a91901ef5981a2a227c920d1 |
| infrahub-stale-date.ts | f4bbd5da44a0ecf45795729181436c17bc16ded2d991706397f892d7c05d1070 |
| infrahub-stale-state.ts | 3c5f33059183508162d0b6a67b8edae37dfa953d3fad5883c8f4c4965fc52cdb |

Sources belong to `actions/stale` commit `4391f3da665fdf50b6810c1a66712fb9ba21aa93` and remain
separately downloaded under upstream licensing. Expected result: 34 fixture assertions pass.
The harness covers timer resets, gate selection, and cache continuation. It does not prove hosted
token permissions, cache transport, actual GitHub event emission, or concurrent update safety.
