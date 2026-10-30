# Data Model: Branch-Agnostic Reads That Return the Right Branch's Data

No schema node, attribute or relationship is added or changed. This file describes the structures the queries pass around and the graph shapes the migration changes.

## Branch window

One live branch's view of the graph at a read time `at`.

| Field | Type | Value |
|---|---|---|
| `name` | string | The branch name. Never `-global-`. |
| `origin_name` | string or NULL | The origin branch. NULL for the default branch. |
| `origin_at` | timestamp string or NULL | `min(branched_from, at)`. NULL for the default branch. |

Rules:

- A branch is live when its name is not `-global-` and its status is not `DELETING`. Merged branches are live until they are deleted or rebased.
- An edge `e` is visible in window `w` when either:
  - `e.branch` is `-global-` or `w.name`, and `e.from <= at`, and `e.to` is NULL or later than `at`; or
  - `e.branch = w.origin_name`, and `e.from <= w.origin_at`, and `e.to` is NULL or later than `w.origin_at`.
- Edge `r` outranks edge `e` when `r.branch_level > e.branch_level`, or the levels are equal and `r.from > e.from`.
- An edge is the latest in a window when it is visible, `active`, and no visible edge of its competing group outranks it. The competing groups are described in `dev/knowledge/backend/query-pattern.md`.

In Cypher, the list of windows is `branch_windows: list[map]`, built once at the start of a query. In Python, a chosen window is passed as a frozen dataclass:

```python
@dataclass(frozen=True)
class BranchWindow:
    name: str
    origin_name: str | None
    origin_at: str | None

    def to_param(self) -> dict[str, str | None]: ...
```

## Chosen window of a node

Produced by `NodeListGetInfoQuery` in branch-agnostic mode and passed by `NodeManager.get_many` to the attribute and relationship queries as `node_windows: dict[str, BranchWindow]` (node uuid to window). Rendered as the Cypher parameter `$node_windows`, a map keyed by uuid.

The order of choice is:

1. The request branch, when the node exists there.
2. Otherwise, the default branch, when the node exists there.
3. Otherwise, the first other live branch by name in which the node exists.

`-global-` is never chosen. A node that exists in no window is not returned.

## Link

A `Relationship` vertex `rl` with:

- two `IS_RELATED` edges, one to each node;
- optional `IS_PROTECTED`, `HAS_OWNER` and `HAS_SOURCE` edges to their property vertices.

`rl.branch_support` is `"aware"` or `"agnostic"`. It is set when the link is created and never changes.

| `rl.branch_support` | Edges allowed after this feature |
|---|---|
| `agnostic` | `-global-` only |
| `aware` | The default branch and user branches only |

## Mixed pair (migration input)

Two vertices joined by both a `-global-` edge and a branch edge of the same type, where the type is one of `IS_RELATED`, `IS_PROTECTED`, `HAS_OWNER` or `HAS_SOURCE`.

| Shape | Recognised by | Written by today | Migration result |
|---|---|---|---|
| 1 | `rl.branch_support = "aware"`, and a `-global-` edge with `status = "deleted"` | Deleting a branch-agnostic node | The same edges the new delete writes, with the original `from`. On the default branch: the decision of open question 2. On each user branch whose own latest edge is `active`: a `deleted` edge. Then the `-global-` edge is removed. |
| 2 | `rl.branch_support = "agnostic"`, and a branch edge with `status = "deleted"` | Deleting a branch-aware node on a branch | The branch edge is removed, and any copy on the default branch if open question 1 finds one. |
| Other | Any other mixed pair | Unknown | Not changed. Counted and logged. |

## Peer existence check

Rendered for a relationship read when `needs_peer_existence_check(relationship_schema, peer_schema, schema_branch)` returns true:

- the relationship's branch support is `agnostic`; or
- the peer schema is a node whose branch support is `agnostic`; or
- the peer schema is a generic, and at least one node schema in its `used_by` has branch support `agnostic`.

A peer passes when its latest `IS_PART_OF` edge is `active`:

- in the request branch's view, for a normal read;
- in the same window as the link, for a branch-agnostic read.

## Delete check result for a branch-agnostic node

`RelationshipGetByIdentifierQuery` in window mode returns rows of `RelationshipPeersData` with one more field, `window_name: str | None`. The field is set only in window mode. `NodeDeleteValidator` groups the rows by `window_name` and runs its existing walk on each group.
