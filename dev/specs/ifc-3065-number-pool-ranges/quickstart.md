# Quickstart / Validation Guide: Number Pools — Weighted Ranges (P1)

Runnable checks that prove the P1 slice works. Details of the model and contract live in `data-model.md` and `contracts/graphql-schema-changes.md`; this file is the run guide.

## Prerequisites

- Backend deps: `uv sync --all-groups`.
- Docker daemon for component/functional tests (testcontainers), or `INFRAHUB_USE_TEST_CONTAINERS=false` against a running database.

## Regenerate after schema changes

```bash
uv run invoke backend.generate                 # protocols.py, generated schema
uv run invoke schema.generate-graphqlschema    # schema/schema.graphql
uv run invoke schema.generate-jsonschema       # schema/openapi.json
uv run invoke docs.generate                     # reference docs
cd frontend/app && pnpm codegen                 # frontend generated types
```

CI's `validate-generated-documentation` fails on any stale generated file — commit them.

## Targeted test commands

```bash
# Core allocation & range behaviour
uv run invoke backend.test-unit
uv run pytest backend/tests/component/core/resource_manager/test_number_pool.py
uv run pytest backend/tests/component/core/resource_manager/test_number_pool_query.py

# Schema validator over a range set (FR-039)
uv run pytest backend/tests/component/core/constraint_validators/test_attribute_numberpool_constraints.py

# Migration: existing pools become single-range pools (SC-005)
uv run pytest backend/tests/component/core/migrations/graph/test_0NN_number_pool_single_range.py

# Branch-agnostic range edits
uv run pytest backend/tests/functional/pools/test_numberpool_branch.py
```

## Acceptance walkthroughs (map to Success Criteria)

1. **Fall-through across gaps (SC-001, US1)**: Create a pool with ranges 100–200 and 205–300. Exhaust 100–200. Allocate → expect **205**. Allocate until both ranges are consumed → next allocation raises the pool-exhausted error, and only then.

2. **Weighted range selection (US1 #3)**: Two ranges with different `allocation_weight`. Repeated allocation draws from the heavier range first, lowest free value within it.

3. **Remove a range holding a number (SC-002, US2)**: Allocate 250 (in 205–300). Remove range 205–300 → removal succeeds; utilization reports **101 of 101**; 250 is never handed out but stays associated. Re-add 205–300 → 250 counts as in use again.

4. **Zero ranges (SC-006, US2 #3)**: Remove the last range → pool legal; utilization **0 of 0 (0%)**; allocation raises pool-exhausted (no divide-by-zero).

5. **Effective space honours the attribute domain (SC-003)**: Pool ranges partly outside the attribute's `[min_value, max_value]`, with some excluded values inside a range and some outside every range. Read size/utilization → only the in-domain portion counts; only intersecting exclusions subtract; every read path agrees.

6. **Former divide-by-zero (SC-004)**: Attribute whose excluded values lie entirely outside the pool's ranges. Read size/utilization → succeeds with a correct non-zero size.

7. **Shorthand round-trip (SC-007)**: Author a pool via `start_range`/`end_range` → reads back those bounds while it holds one range. Add a second range → `start_range`/`end_range` read as **null**.

8. **FR-011 taken-value skip still works (decoupling)**: On a unique attribute, hand-set a value inside a range on the target kind, then allocate → allocation skips the hand-set value (behaviour preserved over the range set; not deleted in P1).

9. **Upgrade (SC-005)**: Run the migration against a database with existing single-span pools → each becomes a one-range pool covering its old span and keeps allocating with no operator action.

## Pre-push

```bash
# from repo root
/pre-ci          # format, lint, unit, generated-file + generated-doc validation
```

Also Vale-lint any `changelog/*.md` fragments (branded-terms), which `/pre-ci` does not cover.
