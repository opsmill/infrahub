# Data Model: Cross-branch Repository Status Query

**Branch**: `cross-branch-repo-status-infp-671` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

No node kind, attribute, relationship or migration is added. This document describes the graph facts
the read depends on and the in-memory shapes the feature introduces.

## Graph facts the read relies on

### Repository nodes

`CoreGenericRepository`, `CoreRepository` and `CoreReadOnlyRepository`
(`backend/infrahub/core/schema/definitions/core/repository.py`) are `AGNOSTIC` at node level: one node,
visible from every branch. Attribute branch support decides where value edges live:

| Kind | Attribute | Branch support | Read once or per branch |
| --- | --- | --- | --- |
| Generic and both concrete kinds | `name`, `description`, `location`, `operational_status` | `AGNOSTIC` | Once (from the repository lookup) |
| `CoreRepository` | `default_branch` | agnostic by inheritance | Once |
| `CoreGenericRepository`, `CoreRepository` | `commit`, `sync_status`, `internal_status` | `LOCAL` | Per branch |
| `CoreReadOnlyRepository` | `commit`, `ref` | `AWARE` | Per branch |

`LOCAL` and `AWARE` differ in merge and diff behaviour, not in how a read on a branch resolves them.
Both are read with the same per-branch predicate.

### Where a per-branch value edge lives

- At repository creation the attribute and its first value are written on the global branch
  (`branch_level` 1), because the node is agnostic.
- A later write on branch X (an import on that branch) creates a `HAS_VALUE` edge on X. On the default
  branch that edge has `branch_level` 1; on a user branch it has `branch_level` 2.

### Per-branch visibility of an edge `r` for row branch `B` at time `at`

```text
default_window(B) = B.branched_from if B.is_isolated else at

visible(r, B) =
     (r.branch IN [B, "-global-"] AND r.from <= at AND (r.to IS NULL OR r.to > at))
  OR (B <> default AND r.branch = default
      AND r.from <= default_window(B) AND (r.to IS NULL OR r.to > default_window(B)))
```

Operators are the ones `Branch.get_query_filter_path` emits: **non-strict** `from <=` and strict
`to >`. It builds two arms per branch, `from <= t AND to IS NULL` and `from <= t AND to > t`, which
together are the disjunction above. The distinction is not cosmetic: an edge whose `from` equals the
query time (or a branch's `branched_from` exactly) is visible to the standard read, and a strict `<`
would silently hide it. The
implementation copies them rather than paraphrasing, and a differential test against a standard
per-branch read pins them. `is_isolated` is deprecated and forced to true on creation, but a branch
from an older database may carry `false`, and the standard read then sees the default branch at query
time; `default_window` keeps the primitive consistent with that.

Winner among visible edges: `ORDER BY r.branch_level DESC, r.from DESC, r.status ASC LIMIT 1`, then keep
only `status = "active"`. This is the rule `Branch.get_query_filter_path` encodes for a single branch
and `infrahub.database.validation::_check_duplicate_attributes` encodes for a branch list.

Consequences the spec pins by test:

| Situation | Winning `HAS_VALUE` edge for branch B | Row shows |
| --- | --- | --- |
| B imported on its own branch | B's edge (level 2) | B's commit, `own_value = true` |
| B never imported; default imported before B forked | default's edge as of `branched_from` (level 1) | Fork-point commit, `own_value = false` |
| B never imported; default imported after B forked | Same as above; the newer default edge fails the `branched_from` window | Fork-point commit (unchanged) |
| B rebased | `branched_from` advanced; the newer default edge is now inside the window | Newer commit |
| Repository never imported anywhere | Global creation edge | `commit.value = null`, `sync_status = unknown` |
| Row is the default branch | Default's own edge if any, else global | `own_value = true` only if written on the default branch |

## Row set

For a repository of kind K, the rows are the `Branch` nodes such that:

- `is_global = false`
- `status NOT IN (MERGED, DELETING)` (`TERMINAL_BRANCH_STATUSES` in `infrahub.core.branch.enums`)
- `sync_with_git = true` when K is `CoreRepository`; no constraint when K is `CoreReadOnlyRepository`
- the caller's optional name (exact or partial) and status filters hold

`Branch` is a standard node (`infrahub.core.branch.models::Branch`); it is joined to attribute edges by
name only (`edge.branch = branch.name`). The row set is read with `Branch.get_list` and the filters in
`BranchListFilters`, which gains `sync_with_git`.

`sync_with_git` is both a criterion and a returned row field (FR-003). It reads constant `true` on the
read-write kind, where it selects the row set, and varies on the read-only kind, where every branch is
a row. It comes off the `Branch` object already held by the row, so returning it costs nothing.

## New in-memory shapes

### `BranchListFilters.sync_with_git: bool | None`

`infrahub.core.branch.filters::BranchListFilters`. `None` means no constraint. Emitted as
`n.sync_with_git = $filter_sync_with_git`.

### `RepositoryBranchAttributeValue` (frozen dataclass, query result)

`infrahub.core.query.repository::RepositoryBranchAttributeValue`

| Field | Type | Source |
| --- | --- | --- |
| `repository_id` | `str` | `n.uuid` |
| `branch_name` | `str` | the unwound branch name |
| `attribute_name` | `str` | `a.name` |
| `attribute_id` | `str` | `a.uuid` |
| `value` | `str \| None` | `av.value` of the winning `HAS_VALUE` edge |
| `own_value` | `bool` | `r_value.branch = branch_name` |
| `updated_at` | `str \| None` | `r_value.from` |

One row per `(repository_id, branch_name, attribute_name)` that resolved to an active value. A branch
whose attribute has no visible edge (never created) produces no row; the reader backfills `None`.

### `RepositoryBranchAttributes` (frozen lookup, reader result)

`infrahub.core.repository_branch_status.models::RepositoryBranchAttributes`

- Built from a sequence of `RepositoryBranchAttributeValue`.
- `get(repository_id, branch_name, attribute_name) -> RepositoryBranchAttributeValue | None`.
- `for_branch(repository_id, branch_name) -> dict[str, RepositoryBranchAttributeValue]` for row assembly.
- Immutable; holds a `Mapping` keyed by the triple.

### `RepositoryBranchStatusRow` (frozen dataclass, resolver internal)

`infrahub.graphql.queries.repository_branch_status.paging::RepositoryBranchStatusRow`

| Field | Type | Source |
| --- | --- | --- |
| `branch` | `Branch` | branch list |
| `values` | `Mapping[str, RepositoryBranchAttributeValue]` | reader (increment B) or stub (increment A) |

The pure helpers in `paging.py` operate on a list of these: `apply_value_filters`, `order_rows`
(default branch first, then `name` ascending, only when no `order` argument), `page_rows`.

### `RepositoryData` and `RepositoryBranchInfo`

`infrahub.git.models::RepositoryData` keeps `branch_info: dict[str, RepositoryBranchInfo]` unchanged.
Two changes in increment C:

- `branches` widens from `dict[str, str]` to `dict[str, str | None]`. A branch whose `commit` resolves
  to no visible value is written as `None` rather than skipped, so callers can tell "no commit here"
  from "branch absent from the read". The declared type does not permit that today, and the one
  consumer that reads the value already handles a falsy one.
- The `-global-` key is no longer present. No caller reads it.

### Constant

`infrahub.git.constants::REPOSITORY_BRANCH_READ_CHUNK_SIZE = 100`, the number of branch names per
primitive call in the periodic sync.

## Validation rules (resolver arguments)

| Argument | Rule | Failure |
| --- | --- | --- |
| `id` | required; a repository uuid or its name, resolved with `NodeManager.get_one_by_id_or_default_filter` | `NodeNotFoundError` when neither matches |
| `limit` | `>= 1`; default 40; no maximum | `ValidationError` |
| `offset` | `>= 0`; default 0 | `ValidationError` |
| `order` | at most one of `created_at`, `updated_at` (existing `standard_node_ordering_from_order_input`) | `ValidationError` |
| `name__value` | any string; combined with `partial_match` for a contains match | none |
| `partial_match` | boolean; default false | none |
| `status__value` | any `BranchStatus` (the SDL name of the `InfrahubBranchStatus` symbol); `MERGED` or `DELETING` yields an empty set, not an error | none |
| `own_values_only` | boolean; default false; keeps rows whose `commit` is the branch's own, and forces `commit` into the attribute read | none |
| `sync_status__value`, `internal_status__value` | any string; unknown values yield an empty set | none |
| repository not found | same `NodeNotFoundError` path as other repository lookups | error |
| no `ALLOW_ALL` view on either repository kind | `PermissionDeniedError` before the lookup | error |
| missing `ALLOW_ALL` view on the resolved concrete kind | `PermissionDeniedError` before any row is returned | error |
| context without a `PermissionManager` | treated as denial | error |

## State transitions

None. The feature writes nothing.
