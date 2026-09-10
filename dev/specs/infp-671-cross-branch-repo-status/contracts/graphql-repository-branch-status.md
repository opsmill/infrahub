# Contract: `InfrahubRepositoryBranchStatus` GraphQL query

**Branch**: `cross-branch-repo-status-infp-671` | **Date**: 2026-09-03 | **SDL**: [graphql-repository-branch-status.graphql](graphql-repository-branch-status.graphql)

This is the document to hand to the frontend team. The contract is final from increment A; only the
truthfulness of the attribute values changes in increment B.

## Semantics

### Anchoring

`id` is required and accepts either the repository's uuid or its `name` (the repository kinds
declare no human-friendly id; `name` is their default filter, so this is the same lookup other
repository reads use). Both kinds, `CoreRepository` and `CoreReadOnlyRepository`, are accepted; the
resolver dispatches on the resolved kind. A repository that does not resolve fails the way every other
repository lookup fails. A caller with no qualifying grant on either kind is denied before the lookup
runs, so denial does not reveal whether the id exists.

### Row set

| Repository kind | Rows |
| --- | --- |
| `CoreRepository` | Branches with `sync_with_git = true` |
| `CoreReadOnlyRepository` | All branches |

In both cases the global branch and branches in `MERGED` or `DELETING` status are excluded. Every
other branch status is included. The branch the query is executed against does not affect the row set.

### Row values

- `name`, `status`, `is_default`, `sync_with_git`, `branched_from` are the branch's own. `sync_with_git`
  is always `true` on a read-write repository's rows, because that is the row-set criterion; on a
  read-only repository it varies, because every branch is a row.
- `commit`, `sync_status`, `internal_status`, `ref` are the repository's attribute values **as that
  branch resolves them**. A branch that never wrote its own value shows the default branch's value at
  the branch's fork point. This is the correct value for that branch and is not an error state.
- `ref` is non-null only for `CoreReadOnlyRepository`; the other three are present for both kinds.
- The `TextAttribute` and `Dropdown` payloads are the existing types. `value`, `label`, `color`,
  `description`, `id` and `updated_at` are populated. `is_default`, `is_protected`, `is_from_profile`,
  `permissions`, `source` and `owner` are always null on this query.
- Do not render `updated_at` as a "last import" time. On an inherited row it is the default branch's
  write time.

### Filters, ordering and paging

All filters apply server-side and `count` reflects them.

| Argument | Effect |
| --- | --- |
| `name__value` + `partial_match` | Branch name equals, or contains when `partial_match` is true |
| `status__value` | Branch status equals; asking for `MERGED` or `DELETING` returns an empty set |
| `sync_status__value` | Keep rows whose resolved `sync_status.value` equals the given value |
| `internal_status__value` | Keep rows whose resolved `internal_status.value` equals the given value |
| `own_values_only` | Keep rows where the branch holds its own `commit` value, meaning it has imported on this branch. Independent of the selected fields |
| `order` | Existing `MetadataOrderInput` on branch node metadata (`created_at` or `updated_at`) |
| `limit` / `offset` | Default 40 / 0; `limit` has no maximum |

Default ordering when `order` is omitted: the default branch first, then branch name ascending.

### Permission

The caller needs `view` on the repository's concrete kind (`Core/Repository` or
`Core/ReadOnlyRepository`) with a decision covering both the default branch and other branches: one
`ALLOW_ALL` grant, or `ALLOW_DEFAULT` and `ALLOW_OTHER` granted separately. `ALLOW_DEFAULT` alone or
`ALLOW_OTHER` alone is denied, whatever branch the request runs against. Denial is an error, never a
trimmed row set.

### Guarantees

- Resolved entirely from the graph. No git operation, no message-bus send, no task worker.
- Database queries per page do not grow with the branch count.
- `count` is computed only when selected.

## Example document

```graphql
query RepositoryBranchStatus($id: String!, $limit: Int, $offset: Int, $syncStatus: String) {
  InfrahubRepositoryBranchStatus(
    id: $id
    limit: $limit
    offset: $offset
    sync_status__value: $syncStatus
  ) {
    count
    edges {
      node {
        name
        status
        is_default
        sync_with_git
        branched_from
        commit { value updated_at }
        sync_status { value label color }
        internal_status { value label color }
        ref { value }
      }
    }
  }
}
```

## Example response (read-write repository, three branches, one failed import)

```json
{
  "data": {
    "InfrahubRepositoryBranchStatus": {
      "count": 3,
      "edges": [
        {
          "node": {
            "name": "main",
            "status": "OPEN",
            "is_default": true,
            "sync_with_git": true,
            "branched_from": "2026-08-01T09:00:00.000000Z",
            "commit": { "value": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b", "updated_at": "2026-09-02T14:12:03.512000Z" },
            "sync_status": { "value": "in-sync", "label": "In Sync", "color": "#60a5fa" },
            "internal_status": { "value": "active", "label": "Active", "color": "#86efac" },
            "ref": null
          }
        },
        {
          "node": {
            "name": "add-core-switches",
            "status": "OPEN",
            "is_default": false,
            "sync_with_git": true,
            "branched_from": "2026-09-01T08:30:00.000000Z",
            "commit": { "value": "0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e", "updated_at": "2026-09-02T15:40:11.001000Z" },
            "sync_status": { "value": "error-import", "label": "Import Error", "color": "#f87171" },
            "internal_status": { "value": "inactive", "label": "Inactive", "color": "#e5e7eb" },
            "ref": null
          }
        },
        {
          "node": {
            "name": "wip-firewall-rules",
            "status": "OPEN",
            "is_default": false,
            "sync_with_git": true,
            "branched_from": "2026-09-02T10:00:00.000000Z",
            "commit": { "value": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b", "updated_at": "2026-09-02T14:12:03.512000Z" },
            "sync_status": { "value": "in-sync", "label": "In Sync", "color": "#60a5fa" },
            "internal_status": { "value": "inactive", "label": "Inactive", "color": "#e5e7eb" },
            "ref": null
          }
        }
      ]
    }
  }
}
```

The third row inherits the default branch's commit and `updated_at`: it forked after the import and
never imported itself.

## Dropdown values and colours (from the schema, unchanged)

Values are the wire values a filter must send, taken from `RepositorySyncStatus` and
`RepositoryInternalStatus`. Note the hyphens in `in-sync` and `error-import`: the Python enum members
are underscored (`IN_SYNC`, `ERROR_IMPORT`) but the stored values are not, and
`sync_status__value` matches the stored value.

| Attribute | value | label | color |
| --- | --- | --- | --- |
| `sync_status` | `unknown` | Unknown | `#9ca3af` |
| `sync_status` | `error-import` | Import Error | `#f87171` |
| `sync_status` | `in-sync` | In Sync | `#60a5fa` |
| `sync_status` | `syncing` | Syncing | `#a855f7` |
| `internal_status` | `staging` | Staging | `#fef08a` |
| `internal_status` | `active` | Active | `#86efac` |
| `internal_status` | `inactive` | Inactive | `#e5e7eb` |

## Increment A (stub) behaviour, for the frontend team

While the stub is live on `develop`:

- Repository lookup, kind dispatch, not-found, permission denial, the row set, `status__value`,
  `name__value`, `partial_match`, `order`, `limit`, `offset` and `count` are real.
- `commit`, `sync_status`, `internal_status` and `ref` values are fabricated deterministically from the
  branch name, so they are stable across reloads. Labels and colours are the real schema choices, and
  every `sync_status` value appears across a handful of branches.
- `sync_status__value`, `internal_status__value` and `own_values_only` are accepted and ignored.
  `count` therefore ignores them too.
- The API log carries one warning when the stub module is loaded, and the root field's description
  in the schema says "(preview: attribute values are placeholders, not yet read from the graph)".
  Both disappear with the stub.
- The card is built without the git-derived drift column for now; that column arrives on its own
  data path once the sibling PRD settles it, and nothing in this contract changes for it.

Consuming the types: pull `develop`, run `pnpm codegen` in `frontend/app`, then write the document
with the `graphql()` tag from `@/shared/api/graphql/client` in the `api/` layer of the repository entity
slice (`frontend/app/src/entities/repository/api/`), as `get-repository-group-from-api.ts` does.

## No companion change on the existing branch query

`InfrahubBranch` is unchanged by this feature. An earlier draft of this contract gave it a
`sync_with_git` filter argument; that was dropped, because nothing queries `InfrahubBranch` to build
this feature. The row set is narrowed inside the resolver, which calls `Branch.get_list` in Python
with `BranchListFilters(sync_with_git=...)`. The Branches card reads
`InfrahubRepositoryBranchStatus` and gets its branches in that response.
