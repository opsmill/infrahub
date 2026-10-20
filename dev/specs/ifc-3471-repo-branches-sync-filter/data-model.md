# Data model: Filter a repository's branches by sync status

No stored data changes. The feature reads existing values and adds one filter entry to the card's URL state.

## Branch sync status (existing)

- Attribute `sync_status` on `GenericRepository` (inherited by Repository and Read-only Repository), kind Dropdown.
- Values and labels, in schema order: `unknown` (Unknown), `error-import` (Import Error), `error-ref-missing` (Tracked Ref Missing), `in-sync` (In Sync), `syncing` (Syncing). Labels come from the schema choices at runtime.
- Resolved per branch; a branch with no value of its own inherits the default branch's value.

## Branches section filter (existing shape, one new field)

- A filter is `{ name, value }`, stored in the list under the URL key `branches_filter`.
- Fields: `name__value` (search and Branch), `status__value` (Status), and new `sync_status__value` (Sync Status).
- Condition: "contains" only, for all three fields.
- Validation: `sync_status__value` is sent only when its value is one of the five values; otherwise it is ignored.
