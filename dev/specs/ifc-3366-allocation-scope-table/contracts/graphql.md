# Contract: GraphQL operations used

All of these are existing backend fields from `schema/schema.graphql`; this feature changes none of them.

## New operation: `GET_NUMBER_POOL_DIVISIONS`

In `entities/resource-manager/api/get-number-pool-divisions-from-api.ts`.

```graphql
query GET_NUMBER_POOL_DIVISIONS($poolId: String!) {
  InfrahubNumberPoolDivisions(pool_id: $poolId) {
    allocation_scope { id name }
    divisions {
      display_label
      entries { path value display_label peer_kind }
      figures { size used used_default_branch used_branches utilization }
    }
  }
}
```

The backend lists every allocation scope that holds at least one number on any live branch. It orders them by usage, highest first, then by `display_label`, and does not paginate.

## Changed operations: a new `$division` variable

Each of these gains `$division: [NumberPoolDivisionEntryInput!]` and passes it as `division:`. Leaving it out keeps the current behavior for unscoped pools.

| Operation | File |
|---|---|
| `GET_NUMBER_POOL_UTILIZATION` | `entities/resource-manager/api/get-number-pool-utilization-from-api.ts` |
| `GET_NUMBER_POOL_ALLOCATIONS` | `entities/resource-manager/api/get-number-pool-allocations-from-api.ts` |
| The allocation count operation | `entities/resource-manager/api/get-number-pool-allocation-count-from-api.ts` |

The `NumberPoolDivisionEntryInput` input is `{ path: String!, value: GenericScalar! }`.

`GenericScalar` is not mapped in `initGraphQLTada`, so the mapper narrows `value` to `string | number | boolean`. It treats any other type as a string.

## Query keys (`entities/resource-manager/ui/queries/resource-manager.query-keys.ts`)

| Key | Parts |
|---|---|
| `numberPoolDivisions` (new) | `poolId`, `branchName`, `atDate` |
| `numberPoolUtilization` | adds `division` |
| `numberPoolAllocations` | adds `division` |
| `numberPoolAllocationCount` | adds `division` |

The header's refresh button already invalidates `resourceManagerQueryKeys.all`, which also covers the new key.
