# Quickstart: Validating the Inherited-Attribute Fix and Healing Migration

**Date**: 2026-07-31 | **Plan**: [plan.md](plan.md) | **Data model**: [data-model.md](data-model.md)

## Prerequisites

- `uv sync --all-groups` completed; local test database available for component tests (see `dev/` docs and project memory: component tests run against the running dev containers).
- For the manual end-to-end check: a running dev stack (`uv run invoke dev.build` + start) and the two schema files attached to [#9284](https://github.com/opsmill/infrahub/issues/9284) (v1 without inheritance, v2 adding `inherit_from`).

## Automated validation

### PR 1 — forward fix

```bash
# Pure phase-split helper (no DB)
uv run pytest -x -v backend/tests/unit/core/migrations/schema/test_tasks.py

# Kind-update migration: inherited-attr creation, profiles/templates, gating, NumberPool, name-update no-op
uv run pytest -x -v backend/tests/component/core/migrations/schema/test_node_kind_update.py

# Attribute-add guard/bypass
uv run pytest -x -v backend/tests/component/core/migrations/schema/test_node_attribute_add.py

# Full migration component suite incl. rollback (must pass unchanged)
uv run pytest -x -v backend/tests/component/core/migrations/schema/

# Branch-merge regression check
uv run pytest -x -v backend/tests/component/core/test_branch_merge.py
```

Integration (#9284 repro through the public API — full stack; run via CI or):

```bash
uv run invoke backend.test-integration  # includes backend/tests/integration/schema_lifecycle/test_schema_add_inherited_generic.py
```

**Expected**: all pass. The integration test loads schema v1, creates an object, loads v2 adding the generic, then asserts: read returns non-null `id`; update to a non-default value persists across re-read with `is_default: false`; attribute-value filter matches.

### PR 2 — healing migration

```bash
# Healing migration suite: damaged default branch, branch-scoped repair, tombstone,
# NumberPool (incl. missing-pool failure, runtime row shape, rebase-time branch pass),
# healthy no-op, idempotent rerun, self-validation failure path, deleted-attribute pins
uv run pytest -x -v backend/tests/component/core/migrations/graph/test_m076_heal_missing_attribute_rows.py

# Discovery/detection queries: completeness, tombstone clamp, heal floor, duplicated schema vertices
uv run pytest -x -v backend/tests/component/core/migrations/graph/test_m075_attribute_heal_detection.py
```

**Expected**: all pass. No-op cases assert **zero writes** via full-graph snapshot equality (before/after `DbSnapshotter` snapshots compare equal — strictly stronger than driver write-counter deltas); rerun cases assert second run writes nothing the same way; the seeded-damage cases assert every (active node, generic-inherited attribute) pair reads back with a non-null attribute `id` afterward. Branch-level pool damage is untouched by `execute()` and healed by `execute_against_branch()` (the rebase-time pass), with allocations following the default branch's.

## Manual end-to-end (dev stack)

### Forward fix (SC-002, fresh install)

1. Load schema v1 from the issue; create `BugbServer(name: "server-1")`.
2. Load schema v2 (adds the generic + `inherit_from`).
3. Verify via GraphQL:
   - `BugbServer { status { id value is_default } }` → non-null `id`.
   - `BugbServerUpdate(data: {status: {value: "planned"}})` then re-read → value persisted, `is_default: false`.
   - Query `BugbServer(status__value: "active")` → matches a node never explicitly updated.

### Healing (SC-001/002/003/004, damaged install)

1. On a pre-fix version: load v1, create nodes, load v2 (damage occurs); create a branch **after** the damage.
2. Upgrade to the fixed version and run `infrahub upgrade` (picks up m076 automatically; migration logs per-kind repair counts and any pool rows deferred to branch rebases; the upgrade marks stale branches for rebase).
3. Verify the same three GraphQL operations succeed on the previously-broken nodes — on the default branch **and**, for default-backed attributes, on the pre-existing branch without rebasing it.
4. If the branch carried its own pool-backed damage (inheritance change made on the branch): rebase the branch (already scheduled by the upgrade) and verify the pool attribute reads back with a non-null `id` and a value that does not collide with default-branch allocations.
5. Re-run `infrahub upgrade` → healing reports zero writes (idempotency).

## Pre-push gates

```bash
uv run invoke format && uv run invoke lint
# then the locally-executable CI checks:
/pre-ci
```

Changelog fragments required: `changelog/9284.fixed.md` (PR 1) and a fragment for the healing migration (PR 2).
