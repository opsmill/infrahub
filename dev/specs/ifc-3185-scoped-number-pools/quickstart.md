# Quickstart: validating scoped number pools

**Feature**: `dev/specs/ifc-3185-scoped-number-pools` | **Date**: 2026-10-02

How to prove the feature works. Each scenario names the user story and requirement it verifies.
Contracts and the data model are linked, not repeated.

---

## Prerequisites

```bash
uv sync --all-groups
```

Component and functional tests start Neo4j through testcontainers, so a Docker daemon must be
running. To reuse an already-running database:

```bash
INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest backend/tests/component/core/resource_manager/
```

---

## Running the suites

```bash
# Pure logic, no database
uv run pytest backend/tests/unit/pools/ backend/tests/unit/graphql/test_number_pool_surface_contract.py

# Queries, validators, mutations
uv run pytest backend/tests/component/core/resource_manager/
uv run pytest backend/tests/component/graphql/queries/test_number_pool_surface.py
uv run pytest backend/tests/component/graphql/resource_manager/number_pools/
uv run pytest backend/tests/component/core/constraint_validators/
uv run pytest backend/tests/component/pools/

# Lifecycle and branch behaviour, in process
uv run pytest backend/tests/functional/pools/

# Schema-load refusal through the full stack
GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
  uv run pytest backend/tests/integration_docker/test_number_pool_scope_schema_load.py
```

Before pushing: `/pre-ci`. It includes `uv run invoke docs.validate`, which fails on any stale
generated file; this slice regenerates the GraphQL schema, the OpenAPI schema, the protocols, the SDK
models, the frontend GraphQL types and the attribute-parameter docs.

---

## Scenario 1 — the contract is up (User Story 1, FR-014 to FR-019, FR-022 to FR-030, SC-007, SC-009, SC-010)

```bash
uv run invoke backend.generate schema.generate-graphqlschema schema.generate-jsonschema docs.generate
rtk git diff --stat schema/ backend/infrahub/core/protocols.py python_sdk/
cd frontend/app && pnpm codegen && cd ../..
```

Expected: `schema/schema.graphql` shows `allocation_scope: ListAttribute` on `CoreNumberPool` and
its three inputs, the root fields `InfrahubNumberPoolUtilization`, `InfrahubNumberPoolDivisions`
and `InfrahubNumberPoolAllocations` with every type of the
[contract](./contracts/graphql-number-pool-surface.md), and only description changes on
`PoolUtilization`, `PoolAllocated`, `PoolAllocatedNode`, `IPPrefixUtilizationEdge` and
`IPPoolUtilizationResource`; the OpenAPI schema shows `allocation_scope` on
`NumberPoolParametersWrite` / `Read`. Then:

```graphql
mutation { CoreNumberPoolCreate(data: {name: {value: "p"}, node: {value: "InfraDevice"},
  node_attribute: {value: "vlan_id"}, start_range: {value: 1}, end_range: {value: 100},
  allocation_scope: {value: ["site"]}}) { object { id allocation_scope { value } } } }
query { InfrahubNumberPoolUtilization(pool_id: "<id>") {
  allocation_scope figures { size used utilization } ranges { display_label figures { size used } } } }
query { InfrahubNumberPoolDivisions(pool_id: "<id>") { count divisions { display_label entries { path value } figures { used } } } }
query { InfrahubNumberPoolAllocations(pool_id: "<id>", division: [{path: "site", value: "<value of Site A>"}]) {
  count allocations { value branch provenance holder { display_label } range { display_label } } } }
```

Expected: the scope reads back `["site"]`. The first delivery of the three queries returns the
fixed in-memory dataset of the
[contract](./contracts/graphql-number-pool-surface.md#fixed-dataset-of-the-first-delivery) and reads
nothing from the database, so any `pool_id` returns the scoped dataset: `allocation_scope:
["site"]`, a utilization refused without `division` and reporting 40 of 100 for Site A, the
divisions Site A (40), Site B (30) and Site C (1), and 41 rows when filtered on Site A. The reserved
`pool_id` `mock-unscoped` returns the unscoped dataset: `allocation_scope` is `[]`, the divisions
list holds one division with no entry, and the `division` filter is refused. Once the real reads
land, the same requests return the created pool's own data.

## Scenario 2 — one pool, every site (User Story 2, FR-001 to FR-007, SC-001, SC-002, SC-004)

`backend/tests/functional/pools/test_numberpool_scoped_allocation.py`: devices in sites A and B both
receive 1; a second in A receives 2; a brand-new site C receives 1; an explicit 1 in A is accepted and
the next allocation in A is 3; fifty concurrent creates in A are distinct. The two-branch case (D1
moved to C on `b1`; default branch allocates 6 in A, 6 in C, 5 in D; deleting `b1` frees 5 in C) is
in `backend/tests/component/core/resource_manager/test_number_pool_scoped_query.py`.

## Scenario 3 — which site is about to run out (User Story 3, FR-011, FR-015 to FR-017, FR-022 to FR-025, SC-011)

`backend/tests/component/graphql/queries/test_number_pool_surface.py`: A 50 records, B two
nodes no records, C no nodes → A alone listed with 50 of 100, no division for B or C, the
utilization query without `division` refused; the utilization query with the division of B reports
30 of 100, `1 - 50` 0 of 50 and `51 - 100` 30 of 50; the allocation list filtered on A
returns D1's two rows and so does the filter on C; no row of the fixed dataset of the first delivery
is returned, and an unknown `pool_id` is refused.

## Scenario 4 — scope in the schema (User Story 4, FR-012, FR-013)

`backend/tests/component/pools/test_schema_number_pool_scope.py`: `vlan_id` with ranges 100–200 and
`allocation_scope: ["site"]`; two sites both receive 100; clearing the scope on the default branch
and reloading makes the next allocation 102; a direct update of the pool's scope is refused with the
default-branch message.

## Scenario 5 — refusals (User Story 5, FR-009, FR-010, FR-024, SC-008)

`backend/tests/component/graphql/resource_manager/number_pools/test_pool_scope.py` (seven refused
entries, each naming the entry),
`backend/tests/component/core/constraint_validators/test_scoped_pool_dependency.py` (optional,
removed, cardinality many → refused naming the pool; a field that never existed on the branch →
accepted) and `backend/tests/component/graphql/queries/test_number_pool_surface.py` (an IP pool as
`pool_id`, a range of another pool, a division filter on an unscoped pool, a path not in force, a
duplicate path). `backend/tests/integration_docker/test_number_pool_scope_schema_load.py` runs the
removal case through the schema-load API.

## Scenario 6 — the branch seam (User Story 6, FR-008, FR-009, FR-027)

`backend/tests/functional/pools/test_numberpool_scoped_branch.py`: `pod` exists only on `b1`;
`["site", "pod"]` is refused on `b1` and on the default branch naming `pod` (the default branch's
schema validates the scope); `b0` forked, `b1` merged; `["site", "pod"]` saves from any branch; the
default branch allocates per site and pod, `b0` per site; `InfrahubNumberPoolDivisions` on the
default branch reports `allocation_scope: ["site", "pod"]` with two-entry divisions and on `b0`
`["site"]` with one-entry divisions; after `b0` is rebased it allocates per the full scope.

## Scenario 7 — consolidation (User Story 7)

P_A scoped by site; each of the ten site-B nodes attached with one `<Kind>Update` sending `value`
and `from_pool: {id: <P_A>}` → A 10/100, B 10/100, next in B is 11, P_B tracks nothing and is
deleted.

## Scenario 8 — measurement (User Story 8, SC-005, SC-006)

```bash
# SC-006: one allocation on a full 4094-number pool, three entries, five branches
uv run pytest backend/tests/query_benchmark/test_number_pool_scoped_allocation.py --benchmark-only
# SC-005: one scoped pool against N per-site pools under concurrent allocation (excluded from the default run)
uv run pytest backend/tests/functional/pools/test_numberpool_scoped_throughput.py -m measurement
```

Record the figures, the anchor order kept, and the `EXPLAIN` plan of the scoped free query in
`dev/specs/ifc-3185-scoped-number-pools/measurements.md`.

## Regression guard (FR-005, FR-029, SC-003, SC-009)

```bash
uv run pytest backend/tests/component/core/resource_manager/ backend/tests/component/graphql/queries/test_resource_pool.py backend/tests/functional/pools/ -k "not scoped"
```

Expected: every pre-existing number-pool test passes with unchanged figures, the unscoped
`reserved_values_query` text is identical to today's (pinned by a snapshot test), and the generic
`InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated` reads return what they
returned before the slice.
