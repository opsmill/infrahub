# Quickstart: Validating Branch-Agnostic Vertex Metadata Correctness

How to run and verify this feature's changes. The normative rule and the recompute the assertions
compare against live in [contracts/vertex-metadata-invariant.md](contracts/vertex-metadata-invariant.md).

## Prerequisites

```bash
uv sync --all-groups
```

Component tests need a database. Either let testcontainers start one (requires a running Docker
daemon), or point at an already-running database:

```bash
export INFRAHUB_USE_TEST_CONTAINERS=false   # reuse a running dev database instead
```

## Run the suites this feature touches

```bash
# The whole metadata surface
uv run pytest -x backend/tests/component/core/test_relationship_metadata.py \
                backend/tests/component/core/test_node_manager_prefetch_metadata.py \
                backend/tests/component/core/migrations/schema/ \
                backend/tests/component/core/migrations/graph/

# The new cross-product suite (SC-001), once it exists
uv run pytest -x backend/tests/component/core/test_vertex_metadata_invariant.py

# The repair migration, including its idempotency check (SC-002)
uv run pytest -x backend/tests/component/core/migrations/graph/ -k repair
```

Nothing here needs the full stack; no functional or integration-Docker run is required.

## Validation scenario 1 — the live over-set (User Story 2, F1b)

The cheapest end-to-end check, because `CoreReadOnlyRepository` is agnostic while its `ref` is aware,
so no custom schema is needed.

1. On the default branch, note a `CoreReadOnlyRepository`'s `updated_at`.
2. Create a branch, update `ref` on it, save.
3. Read the same repository on the default branch.

**Expected**: the value of `ref` is unchanged **and** `updated_at` / `updated_by` are unchanged.
**Before the fix**: `updated_at` has advanced for a change the default branch cannot see.

## Validation scenario 2 — the under-set (User Story 1, F1)

Requires a test schema: a branch-aware kind with a branch-agnostic attribute (mismatch #2). The
schema fixtures in `backend/tests/component/core/migrations/graph/test_050.py` are the pattern to
follow.

1. Create an object of that kind on the default branch.
2. On a feature branch, update the agnostic attribute.
3. Read the object on the default branch.

**Expected**: the new value **and** an `updated_at` / `updated_by` matching that update.
**Before the fix**: the new value with a stale clock.

## Validation scenario 3 — the migration under-set (User Story 3, F6/FR-007)

The only finding merge does not repair.

1. On a feature branch, add a branch-agnostic attribute to a branch-aware kind and let the schema
   migration run.
2. Read the new Attribute vertex and its owning Node on the default branch.

**Expected**: the Attribute vertex has `created_at` / `created_by` set and the Node's `updated_at`
has advanced.
**Before the fix**: the Attribute's metadata is NULL permanently, and the Node's clock never moved.

Pin the opposite direction in the same suite: a migration on a feature branch that writes only
level-2 edges must still write no metadata.

## Validation scenario 4 — the repair (User Story 4, FR-005)

1. Seed a graph with vertices whose metadata disagrees with their level-1 edges — both the NULLs F6
   leaves and the advanced values F1b leaves.
2. Run the repair migration.
3. Assert every affected vertex equals the recompute.
4. Run it again and assert zero vertices changed (SC-002).

## Performance check (SC-003)

A check, not a gate. Benchmark relationship create/delete before and after the FR-004 peer guard:

```bash
uv run pytest backend/tests/query_benchmark/ -k relationship
```

Also run `EXPLAIN` on the modified relationship queries, per Constitution V. A measurable regression
means the guard sits in the wrong place — `RelationshipCreateQuery` already proves a level-1
`IS_PART_OF` for level-1 peers, so only the aware-peer case should add an `OPTIONAL MATCH`.

## Before pushing

```bash
uv run invoke format
uv run invoke lint
```

Then `/pre-ci`. This feature needs a Towncrier fragment in `changelog/` — the wrong timestamps are
user-visible.
