# Quickstart: validating number pool allocation scopes

Scenarios that prove the feature end to end, with the commands that run them. Contract details are in [contracts/](contracts/), entity rules in [data-model.md](data-model.md).

## Prerequisites

- Docker running (component, functional and integration tests start Neo4j through testcontainers).
- `uv sync --all-groups`.
- For the live-stack measurement: a stack built from this branch (`export INFRAHUB_IMAGE_VER=local`, `uv run invoke dev.build`, `uv run invoke dev.start`).

## Automated scenarios

| Scenario | Spec reference | Command |
|----------|----------------|---------|
| Scope resolver rules, refusal of `List`, `JSON` and `Any` elements, division key | FR-003 to FR-006, FR-009 | `uv run pytest backend/tests/unit/pools/test_scope.py` |
| Allocation per division, parallel writers in two divisions, repeatable identifier, update moving a node to another site, branch whose schema lacks the element | FR-010 to FR-013, FR-016 | `uv run pytest backend/tests/component/core/resource_manager/test_number_pool_scope_allocation.py` |
| Free, used, divisions and allocated queries with a division, read on the request branch | FR-015, FR-020 to FR-022 | `uv run pytest backend/tests/component/core/resource_manager/test_number_pool_scope.py` |
| Scope on create, every refusal, immutability on update, `null` refused | FR-001 to FR-008 | `uv run pytest backend/tests/component/graphql/resource_manager/number_pools/test_pool_allocation_scope.py` |
| The fixed dataset of PR #10932 on the `{id, name}` contract (until the resolvers read the database) | FR-018 | `uv run pytest backend/tests/component/graphql/queries/test_number_pool_surface.py` |
| The three dedicated queries on real pools and their refusals | FR-017 to FR-023 | `uv run pytest backend/tests/component/graphql/queries/test_number_pool_surface.py` |
| Declared scope on a schema-created pool | FR-024 to FR-027 | `uv run pytest backend/tests/component/pools/test_schema_number_pool_scope.py` |
| Schema checker decision table, without a database | FR-026, FR-028 | `uv run pytest backend/tests/unit/core/validators/test_number_pool_scope_checker.py` |
| Schema checker against a database: refusals, rename accepted, declaration compared by id | FR-026, FR-028, FR-029 | `uv run pytest backend/tests/component/core/constraint_validators/test_number_pool_scope.py` |
| Declared scope, rename and refusals through the schema load API, on the default branch and on a branch | FR-026 to FR-029 | `uv run pytest backend/tests/integration/schema_lifecycle/test_number_pool_scope_schema.py` |
| Two-branch scenarios and the known limitation of decision 7 | FR-011, FR-022 | `uv run pytest backend/tests/functional/pools/test_numberpool_scoped_branch.py` |
| Unscoped rendering of the shared Cypher fragment unchanged | FR-030 | `uv run pytest backend/tests/unit/core/test_resource_manager_query.py` |
| Nothing changes for unscoped pools | FR-030 | `uv run pytest backend/tests/component/core/resource_manager backend/tests/component/graphql/resource_manager backend/tests/component/graphql/queries backend/tests/functional/pools backend/tests/integration/schema_lifecycle/test_number_pool_branch_merge.py` |

## Manual scenario on a live stack

1. Load a schema with `LocationSite` and `InfraDevice`, where `InfraDevice.site` is a required cardinality-one relationship, `InfraDevice.role` is a required `Text` attribute and `InfraDevice.vlan_id` is a `Number` attribute.
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
4. Run `InfrahubNumberPoolDivisions(pool_id: "<pool id>")`. Expected: two divisions, site A first (2 of 100), then site B (1 of 100), each entry carrying the `id` of the `site` relationship.
5. Run `InfrahubNumberPoolUtilization(pool_id: "<pool id>")` without a division. Expected: refused with the message of the contract. Run it with `division: [{ path: "site", value: "<site A id>" }]`. Expected: `used: 2`.
6. Try `CoreNumberPoolUpdate` with `allocation_scope: { value: [] }`, then with `{ value: null }`. Expected: both refused, "can't be changed after the pool is created".
7. Update the first device of site A with `site: <site B>` and `vlan_id: { value: null, from_pool: { id: "<pool id>" } }` in one request. Expected: it receives 2, the lowest number free in site B.
8. Rename `site` to `location` in the schema (keeping the relationship's id in the file) and reload it. Expected: load accepted; `allocation_scope.value` now reads `name: "location"`; a new device in site A receives 3.
9. Make `location` optional in the schema and reload it. Expected: refused, the error names the pool `vlan-per-site` and the field.
10. Load a schema where `InfraDevice.vlan_id` is a `NumberPool` attribute with `parameters.allocation_scope: ["role"]`. Expected: the pool the schema creates reads `[{"id": "...", "name": "role"}]`. Reload the same schema with `allocation_scope: ["site"]`. Expected: refused, `InfraDevice.vlan_id: allocation_scope can't be changed after the pool is created`. Rename `role` to `function` (id kept) while the file still declares `["role"]`. Expected: refused, `InfraDevice.vlan_id: allocation_scope: "role" was renamed to "function"; update allocation_scope to the new name`. Reload with `allocation_scope: ["function"]`. Expected: accepted, the pool reads `name: "function"`.

## Two-branch scenarios

1. On branch `b1`, move device D1 from site A to site C. Expected: on `b1`, `InfrahubNumberPoolDivisions` lists site C with D1's number and site A without it; on the default branch, site A still counts D1's number and site C is absent.
2. On branch `b2`, create a device in site A with `from_pool`. Expected: it receives the lowest number free in site A as read on `b2`.
3. Merge `b1`. Expected: D1's number is counted under site C only, on every branch.
4. Known limitation to assert (decision 7, research R5): create R1 on branch `b2` in site A, then R2 on branch `b1` in site A. Expected: both receive the same number, because R1 is invisible from `b1`; after both branches merge, two holders in site A hold that number, and the pool reports it once under site A.
5. Create branch `b3`, then add a required relationship `pod` to `InfraDevice` on the default branch and create a pool scoped by `pod`. Allocate from that pool on `b3`. Expected: refused, the error names `pod` and `b3`. Rebase `b3` and allocate again. Expected: accepted.

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
