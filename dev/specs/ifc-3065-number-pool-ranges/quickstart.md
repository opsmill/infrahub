# Quickstart: Number Pools P1 — Weighted Ranges

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Prerequisites

```bash
uv sync --all-groups
export INFRAHUB_IMAGE_VER=local   # when running against a local stack
```

Component tests start Neo4j through testcontainers and need Docker.

## Unit checks (no database)

```bash
uv run pytest backend/tests/unit/pools/test_number_ranges.py backend/tests/unit/core/schema/test_number_pool_parameters.py
```

Expected: segment order `(-weight, start)`, size excludes clipped and excluded values, zero ranges gives size 0; parameters refuse both spellings and overlap, resolve a single bound, and produce no warning without the shorthand.

## User Story 1: allocation across weighted ranges

```bash
cd backend && uv run pytest tests/component/core/resource_manager/test_number_pool.py -k ranges
```

Expected: 101 allocations from 100-200 ascending on a pool with 100-200 (weight 10) and 205-300, utilization 101 of 197, then 205; equal weights drain lowest start first; raising a weight redirects the next allocation.

## User Story 2: existing pools unchanged

```bash
cd backend && uv run pytest tests/component/core/migrations/graph/m079_number_pool_ranges
uv run pytest backend/tests/unit/core/graph/test_graph_version.py
```

Expected: every pre-existing pool holds one range with its old bounds, figures unchanged, second run creates nothing, `GRAPH_VERSION` matches the migration number.

## User Story 3: grow and shrink a live pool

```bash
cd backend && uv run pytest tests/component/graphql/resource_manager/test_number_pool_range.py tests/component/graphql/resource_manager/test_resource_manager.py -k "range or shorthand"
```

Expected: removal of a range holding allocations succeeds and hides them; re-adding restores them; overlap and backwards ranges refused with named ranges; shorthand on a multi-range pool refused with the range list; zero ranges legal.

## User Story 4: schema-declared ranges

```bash
cd backend && uv run pytest tests/component/pools tests/component/core/constraint_validators/test_attribute_numberpool_constraints.py tests/component/core/schema/test_attribute_parameters.py
uv run pytest backend/tests/integration/schema_lifecycle/test_attribute_parameters_update.py
```

Expected: ranges materialised at pool creation, reconciled on a default-branch edit, unsafe change refused naming objects, direct edits refused through both mutations.

## User Story 5: deprecation signals

```bash
cd backend && uv run pytest tests/component/graphql/test_manager.py -k deprecat
uv run invoke schema.generate-graphqlschema && git diff --stat schema/schema.graphql
```

Expected: `@deprecated` on `start_range` / `end_range` in the object type, interface and inputs; schema load returns one `DEPRECATION` warning per shorthand attribute.

## Benchmark (recorded, not gated)

```bash
cd backend && uv run pytest tests/query_benchmark/test_number_pool_allocation.py --benchmark-only
```

## Generated files

```bash
uv run invoke backend.generate
uv run invoke schema.generate-graphqlschema
uv run invoke schema.generate-jsonschema
cd frontend/app && pnpm codegen
uv run invoke docs.generate
uv run invoke docs.validate
```

## Pre-CI

Run `/pre-ci` before pushing; Vale-lint the changelog fragments separately.
