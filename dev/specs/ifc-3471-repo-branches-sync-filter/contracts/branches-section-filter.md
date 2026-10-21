# Contract: Branches section filter

## Request

`InfrahubRepositoryBranchStatus` (existing query, no schema change). The card's document adds one variable:

```graphql
$sync_status__value: String
...
InfrahubRepositoryBranchStatus(
  ...
  sync_status__value: $sync_status__value
)
```

- Sent only when the stored filter holds one of `unknown`, `in-sync`, `error-import`, `error-ref-missing`, `syncing`; otherwise the variable is `undefined`.
- Server behaviour (existing): rows whose resolved `sync_status` equals the value; `count` is the filtered count; paging applies after filtering; combines with `name__value`, `partial_match` and `status__value` by AND.
- The document keeps not declaring `internal_status__value` and `own_values_only`.

## URL state

- Key: `branches_filter` (card scope `branches`).
- Entry: `{ "name": "sync_status__value", "value": "<one of the sync_status choices>" }`.
- Written identically by the filter picker and the Sync Status column header.

## Active filter tag

- Sync Status tag: `Sync Status contains <label>`, for example `Sync Status contains Import Error`.
- Status tag: unchanged, for example `Status contains OPEN`.
- Other object tables: unchanged (they do not set `showChoiceLabels`).
