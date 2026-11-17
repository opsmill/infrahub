# Contract: GraphQL documents the body sends

**Spec**: [../spec.md](../spec.md) | **Source of the schema**: [PR #10932](https://github.com/opsmill/infrahub/pull/10932), the SDL in `dev/specs/ifc-3185-scoped-number-pools/contracts/graphql-number-pool-surface.md` on that branch

The body consumes these two queries and does not change the schema. It selects only the fields it shows. Both are sent with the request context of the user's branch and time (`branchName`, `atDate`), like every other query in the app. The figures count every live branch whatever the request's branch, so the body shows the same numbers on every branch (spec FR-004).

## `GET_NUMBER_POOL_UTILIZATION`

File: `entities/resource-manager/api/get-number-pool-utilization-from-api.ts`.

```graphql
query GET_NUMBER_POOL_UTILIZATION($poolId: String!) {
  InfrahubNumberPoolUtilization(pool_id: $poolId) {
    figures {
      size
      used
      used_default_branch
      used_branches
      utilization
    }
    ranges {
      id
      start
      end
      weight
      figures {
        size
        used
        used_default_branch
        used_branches
        utilization
      }
    }
  }
}
```

| Case | Response | Body behaviour |
|---|---|---|
| Pool without an allocation scope | `figures` and `ranges` (ordered by start) | Ranges card in fill order |
| Pool with no range | `ranges: []`, `figures.size: 0` | "No ranges" state |
| Pool with an allocation scope | `ValidationError`: "The pool <id> has an allocation scope in force on branch <branch>; give a division to read its utilization" | `ErrorScreen` with the message. Accepted until the scope work. |

## `GET_NUMBER_POOL_ALLOCATIONS`

File: `entities/resource-manager/api/get-number-pool-allocations-from-api.ts`.

```graphql
query GET_NUMBER_POOL_ALLOCATIONS(
  $poolId: String!
  $rangeId: String
  $offset: Int!
  $limit: Int!
) {
  InfrahubNumberPoolAllocations(
    pool_id: $poolId
    range_id: $rangeId
    offset: $offset
    limit: $limit
  ) {
    count
    allocations {
      value
      branch
      provenance
      holder {
        id
        kind
        display_label
      }
      range {
        id
      }
    }
  }
}
```

| Case | Response | Body behaviour |
|---|---|---|
| "All ranges" | `rangeId` omitted. Rows of every range, ordered by value, then branch, then holder ID. | Table with the Range column when the pool has more than one range |
| One range | `rangeId` set. Rows of that range only. | Table without the Range column |
| No match | `count: 0`, `allocations: []` | "No allocations yet" or "No allocations in <range>" |
| `rangeId` not in the pool | Error (confirmed by the user; the exact message is not in the contract) | Not normally sent: the page checks the range first. If a range is deleted between the two requests, `ErrorScreen` shows. |

Not selected: `identifier`, `holder.hfid`, `range.display_label`, and the `division`, `branch` and `provenance` filters (no filters in this work, spec FR-014).
