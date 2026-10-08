# GraphQL operations used by the number pool forms

No schema change. These operations use the existing contract described in [`dev/specs/ifc-3065-number-pool-ranges/contracts/graphql-schema-changes.md`](../../ifc-3065-number-pool-ranges/contracts/graphql-schema-changes.md). Types come from `frontend/app/src/shared/api/graphql/generated`.

## Read: pool for editing

```graphql
query GetNumberPoolForEditing($id: ID!) {
  CoreNumberPool(ids: [$id]) {
    edges {
      node {
        id
        name { value }
        description { value }
        node { value }
        node_attribute { value }
        allocation_scope { value }
        pool_type { value }
        ranges {
          edges {
            node {
              id
              start { value }
              end { value }
              allocation_weight { value }
            }
          }
        }
      }
    }
  }
}
```

The exact field names and the page size of `ranges` are confirmed against `schema/schema.graphql` during implementation.

## Write: pool

Existing generic mutations `CoreNumberPoolCreate` and `CoreNumberPoolUpdate`, with `name`, `description`, `node`, `node_attribute` and `allocation_scope` on create; `name` and `description` on update. `ranges`, `start_range` and `end_range` are never sent.

## Write: ranges

| Operation | Input | Refusals the form must display |
|---|---|---|
| `CoreNumberPoolRangeCreate` | `start`, `end`, `allocation_weight` (nullable), `pool { id }` | "Range end (X) cannot be lower than start (Y)"; "Range a-b overlaps c-d (id)"; schema pool refusal |
| `CoreNumberPoolRangeUpdate` | `id`, `start`, `end`, `allocation_weight` | same |
| `CoreNumberPoolRangeDelete` | `id` | schema pool refusal |

Range calls pass a `processErrorMessage` that does not toast, so the form shows the message once, inline.
