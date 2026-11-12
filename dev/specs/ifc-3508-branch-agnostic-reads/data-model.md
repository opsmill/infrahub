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

Migration `m083` (PR 6) handles every shape below.

Two vertices joined by both a `-global-` edge and a branch edge of the same type, where the type is one of `IS_RELATED`, `IS_PROTECTED`, `HAS_OWNER` or `HAS_SOURCE`.

| Shape | Recognised by | Written by today | Migration result |
|---|---|---|---|
| 1 | `rl.branch_support = "aware"`, and a `-global-` edge with `status = "deleted"` | Deleting a branch-agnostic node | The same edges the new delete writes, with the `-global-` edge's `from`. On the default branch: the decision of open question 2. On each live user branch whose own latest edge for the link, as of that `from`, is `active`, and that has no edge of its own for the link with a later `from`: a `deleted` edge. Branches with a later edge of their own are counted and logged, not changed. Then the `-global-` edge is removed. |
| 2 | `rl.branch_support = "agnostic"`, and a `deleted` edge on the default branch or a user branch | Deleting a branch-aware node on any branch, the default branch included; possibly a merge (open question 1) | The edge is removed. |
| Other | Any other mixed pair | Unknown | Not changed. Counted and logged. |

## Peer existence check

Rendered for a relationship read when `needs_peer_existence_check(relationship_schema, peer_schema, schema_branch)` returns true:

- the relationship's branch support is not `agnostic`; and
- the peer schema is a node whose branch support is `agnostic`, or a generic with at least one node schema in its `used_by` whose branch support is `agnostic`.

A branch-agnostic relationship never gets the check. Its peer is returned while the `-global-` link is open, and the retirement check closes the link once no live branch holds both ends.

A peer passes when its latest `IS_PART_OF` edge is `active`:

- in the request branch's view, for a normal read;
- in the same window as the link, for a branch-agnostic read.

## Delete check result

`NodeDeleteCascadeQuery` returns one row, read as `NodeDeleteCascadeQueryResult`:

| Field | Type | Value |
|---|---|---|
| `nodes` | list of `DeleteSetNode` | The nodes already known and every node the cascade reached in the request branch's window. `DeleteSetNode` holds `uuid`, `kind` and `is_agnostic`, which is true when the node has an `IS_PART_OF` edge on `-global-`. |
| `frontier_ids` | list of strings | The nodes reached at the last level, from which the cascade continues when the cascade kinds can loop. |
| `required_links` | list of `RequiredPeerLink` | The links from a peer outside the delete set with a required relationship to a node in it, on the request branch. Empty while the cascade continues. |

`RequiredPeerLink` is a frozen, ordered dataclass of `deleted_kind`, `deleted_id`, `identifier`, `peer_kind` and `peer_id`.

`NodeDeleteOtherBranchesQuery` runs only when a node of the delete set is branch-agnostic. It returns one `RequiredPeerLinkOnBranches` per blocking link: the `RequiredPeerLink` and the names of the other live branches whose window holds it. Its parameter `required_by_branch` maps each branch name to the `[deleted node kind, relationship identifier, peer kind]` triples of the relationships that branch's schema makes required.
