# Contract: URLs of a scoped number pool

These URLs are shared between operators, so their format must stay stable.

## Paths

The routes are unchanged:

| Path | Shows |
|---|---|
| `/resource-manager/:resourcePoolId` | The table of allocation scopes, or, with `allocation_scope`, the page of one allocation scope with every range |
| `/resource-manager/:resourcePoolId/ranges/:rangeId` | With `allocation_scope`, the page of one allocation scope with one range selected |

## Query string parameters

| Key (`shared/config/qsp.ts`) | Value | Read by | Kept by range links |
|---|---|---|---|
| `allocation_scope` (new) | A JSON array, one value per field of the pool's allocation scope, in its order. A relationship stores the peer's ID, a numeric attribute a number, a boolean attribute a boolean, any other attribute a string. `""` means the holding object has no value. | page of one allocation scope | yes |
| `allocation_scope_search` (new) | Free text | allocation scopes table | no |
| `allocation_scope_sort` (new) | `usage:desc` (default, omitted), `usage:asc`, `<field>:asc`, `<field>:desc` | allocation scopes table | no |
| `allocation_branch` (existing) | Branch name | allocations table | yes |
| `allocation_source` (existing) | `allocated` or `provided` | allocations table | yes |
| `branch`, `at` (existing) | Current branch and time | the whole app | always |

Example: a pool scoped by Device and Role, on range `18a7…`:

```text
/resource-manager/18a2…/ranges/18a7…?allocation_scope=%5B%2218a3…%22%2C%22leaf%22%5D
```

## URL helpers (`entities/resource-manager/ui/routing/number-pool-urls.ts`)

| Helper | Returns |
|---|---|
| `getNumberPoolRangeUrl(poolId, rangeId?)` (existing) | Unchanged signature. It now also keeps `allocation_scope`. |
| `getNumberPoolDivisionUrl(poolId, values)` (new) | `/resource-manager/:poolId?allocation_scope=<json>`. It removes any range and the table's search and sort parameters, and keeps `branch`, `at` and the allocation filters. |
| `getNumberPoolDivisionsUrl(poolId)` (new) | `/resource-manager/:poolId`. It removes `allocation_scope`. This is the "All allocation scopes" link. |

## Invalid values

| URL value | Result |
|---|---|
| Not JSON, not an array, or an item that is not a string, number or boolean | The message "This link does not match the pool's allocation scope (…)" |
| An array whose length differs from the number of fields | The same message |
| A valid array that no allocation scope holds | The page of one allocation scope, with 0 used and no allocations; its summary shows the raw values |
| A value whose type the backend refuses | `ErrorScreen` with the backend message |
