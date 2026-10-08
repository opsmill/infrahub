# Quickstart: validating number pool allocation scopes

Scenarios that prove the feature end to end, with the commands that run them. Contract details are in [contracts/](contracts/), entity rules in [data-model.md](data-model.md).

## Prerequisites

- Docker running (component and integration tests start Neo4j through testcontainers).
- `uv sync --all-groups`.
- For the live-stack measurement: a stack built from this branch (`export INFRAHUB_IMAGE_VER=local`, `uv run invoke dev.build`, `uv run invoke dev.start`).

## Automated scenarios

| Scenario | Spec reference | Command |
|----------|----------------|---------|
| Scope resolver rules and division key | FR-003 to FR-006, FR-009 | `uv run pytest backend/tests/unit/pools/test_scope.py` |
| Allocation per division, parallel writers in two divisions, repeatable identifier | FR-010 to FR-013 | `uv run pytest backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py` |
| Free, used, divisions and allocated queries with a division | FR-015, FR-019 to FR-021 | `uv run pytest backend/tests/component/core/resource_manager/test_number_pool_scope.py` |
| Scope on create, every refusal, immutability on update | FR-001 to FR-008 | `uv run pytest backend/tests/component/graphql/resource_manager/test_number_pool_scope_mutation.py` |
| The three dedicated queries and their refusals | FR-016 to FR-022 | `uv run pytest backend/tests/component/graphql/resource_manager/test_number_pool_queries.py` |
| Declared scope on a schema-created pool | FR-023 to FR-026 | `uv run pytest backend/tests/component/pools/test_schema_number_pool_scope.py` |
| Schema guard, rename follow-up, guard on a branch, branch load declaring an element absent from the default branch | FR-026 to FR-028 | `uv run pytest backend/tests/integration/schema_lifecycle/test_number_pool_scope_guard.py` |
| Unscoped rendering of the shared Cypher fragment unchanged | FR-029 | `uv run pytest backend/tests/unit/core/query/test_resource_manager_fragments.py` |
| Nothing changes for unscoped pools | FR-029 | `uv run pytest backend/tests/component/core/resource_manager backend/tests/component/graphql/resource_manager backend/tests/integration/schema_lifecycle/test_number_pool_branch_merge.py` |

## Manual scenario on a live stack

1. Load a schema with `LocationSite` and `InfraDevice`, where `InfraDevice.site` is a required cardinality-one relationship and `InfraDevice.vlan_id` is a `Number` attribute.
2. Create the pool:

   ```graphql
   mutation {
     CoreNumberPoolCreate(data: {
       name: { value: "vlan-per-site" }
       node: { value: "InfraDevice" }
       node_attribute: { value: "vlan_id" }
       start_range: { value: 1 }
       end_range: { value: 100 }
       allocation_scope: { value: ["site"] }
     }) { ok object { id allocation_scope { value } } }
   }
   ```

   Expected: `allocation_scope.value` is `[{"id": "...", "name": "site"}]`.
3. Create two devices in site A and one in site B with `vlan_id: { from_pool: { id: "<pool id>" } }`. Expected: site A receives 1 and 2, site B receives 1.
4. Run `InfrahubNumberPoolDivisions(pool_id: "<pool id>")`. Expected: two divisions, site A first (2 of 100), then site B (1 of 100).
5. Run `InfrahubNumberPoolUtilization(pool_id: "<pool id>")` without a division. Expected: refused with the message of the contract. Run it with `division: [{ path: "site", value: "<site A id>" }]`. Expected: `used: 2`.
6. Try `CoreNumberPoolUpdate` with `allocation_scope: { value: [] }`. Expected: refused, "can't be changed after the pool is created".
7. Rename `site` to `location` in the schema and reload it. Expected: load accepted; `allocation_scope.value` now reads `name: "location"`; a new device in site A receives 3.
8. Make `location` optional in the schema and reload it. Expected: refused, the error names the pool `vlan-per-site` and the field.

## Two-branch scenarios

1. On branch `b1`, move device D1 from site A to site C. Expected: `InfrahubNumberPoolDivisions` lists site C with `used_branches: 1`, and site A still counts D1's number on the default branch.
2. On branch `b2`, create a device in site A with `from_pool`. Expected: it receives the lowest number free in site A across all live branches.
3. Merge `b1`. Expected: D1's number is counted under site C only.
4. Known limitation to assert (see research R5): a value closed on the default branch but still visible to an older branch takes the holder's division read with the default-branch fallback.

## Measurements

Run on the live stack, with the database reset to the same baseline before each variant (see `dev/guidelines/backend/testing.md` for the perf discipline):

| Variant | What to record |
|---------|----------------|
| Unscoped pool, 10 000 tracked values | Latency of one allocation, number of database queries |
| Pool scoped by one relationship, same values spread over 10 sites | Same figures, plus `EXPLAIN` of the scoped free query |
| Pool scoped by one relationship and two attributes | Same figures |
| Twenty writers, two sites, in parallel | Throughput compared with one site |

Record the figures as ratios against the unscoped variant in `dev/specs/ifc-3185-number-pool-scopes/measurements.md`. If the holder-anchored Cypher order (research R5) is faster by a clear margin, keep it and update the plan.

## Expected outcome

Every automated scenario passes, the manual scenario behaves as listed, the two-branch scenarios behave as listed, and the measured scoped allocation stays within the same order of magnitude as the unscoped one.
