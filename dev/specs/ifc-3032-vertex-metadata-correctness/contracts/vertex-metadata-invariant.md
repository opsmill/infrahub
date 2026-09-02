# Contract: Vertex Metadata Invariant

This feature introduces no external API. Its contract is internal but normative: it is the single
rule that the write sites, the repair migration, and the SC-001 tests must all agree on. It is
recorded here so those three can be checked against one statement rather than against each other.

## Scope

Applies to the properties `created_at`, `created_by`, `updated_at`, `updated_by` on `:Node`,
`:Attribute`, and `:Relationship` vertices.

Does **not** apply to `previous_updated_at` / `previous_updated_by`, which are a rollback snapshot
owned by the schema-migration and merge paths, not part of this cache. Two rules govern them, and they
apply to different branches rather than competing:

- A snapshot is written only where a rollback could consume it — i.e. where the write is on the
  default or global branch. `GraphRollbacker` refuses to restore metadata for any other target branch,
  so a snapshot written during a user-branch migration is unusable and must not be written.
- Where a snapshot *is* written, the rollback must be able to reach it, including when the write it
  accompanies landed on `-global-` rather than on the merge's target branch.

## The invariant

> A vertex's `created_at/by` and `updated_at/by` MUST reflect the latest change **visible on the
> default branch** — i.e. the latest change carried by a `branch_level = 1` edge, whether that edge
> is on the default branch or on `-global-`.

### Corollaries the write sites must satisfy

1. **Per-edge, not per-object.** The decision to stamp a vertex is a property of the edge being
   written, never of the owning object's branch support. Where an object and one of its fields have
   different branch support, the two answers differ, and the edge's answer is the correct one.
2. **A Node vertex is stamped only if the node itself is visible on the default branch.** A
   `branch_level = 1` field edge is necessary but not sufficient: the node must also have an active
   `IS_PART_OF` edge at `branch_level = 1`. This is what excludes peers that exist only on a branch,
   nodes deleted on the default branch, and migrated-out twins.
3. **No write, no stamp.** A path that produces only `branch_level = 2` edges MUST leave every
   vertex property untouched, on every branch.

## The recompute

Given a vertex, its metadata is defined as a pure function of its `branch_level = 1` edges. This is
`core/migrations/graph/m050_backfill_vertex_metadata.py`'s derivation, extended to the actor fields.

| Vertex | `created_at` | `updated_at` |
|---|---|---|
| `:Attribute` | `from` of the level-1 `HAS_ATTRIBUTE` edge | `max()` over `from` and non-null `to` of the vertex's level-1 edges; falls back to `created_at` |
| `:Relationship` | `min(from)` over level-1 `IS_RELATED` edges | `max()` over `from` and non-null `to` of the vertex's level-1 non-`IS_RELATED` edges; falls back to `created_at` |
| `:Node` | `min(from)` over level-1 `IS_PART_OF` edges **across every vertex sharing the uuid** | `max()` over the vertex's level-1 field edges and the edges of the fields they actively hold (see below); falls back to `created_at` |

`created_by` / `updated_by` are the `from_user_id` — or `to_user_id`, when a `to` supplied the
winning timestamp — of the edge that produced the corresponding timestamp.

**Which vertex owns a change.** The recompute is total: every vertex has metadata derived from its
own level-1 edges, and none is excluded. Selecting targets is not how the twin case is handled.

Kind- and inheritance-migration leave two `:Node` vertices sharing one uuid, and those two vertices
**share their field vertices outright** — the migration repoints the edges, it does not copy the
`:Attribute` and `:Relationship` vertices. So a change to a field cannot be attributed to one of the
two by looking at the field: only the edge between the Node and the field says which of them was
holding it at the time. That is why a field's own edges count towards a Node's `updated_at` only
while the Node still holds it through an `active` edge with a null `to`, and why the edge to the
field counts as a change in its own right. A migrated-out twin's last change is then the moment the
migration took its fields away, which is exactly what the migration stamps on it.

Both halves of that test are load-bearing. The migration leaves the twin a *new* `deleted`-status
edge to each field whose `to` is null, so an open-edge test alone still reaches through it; and the
`to` is what excludes the edge the migration closed.

A node deleted on the default branch is likewise not excluded. Its `HAS_ATTRIBUTE` edges close at the
delete, so its last change is the deletion — which is what the delete path stamps, and which SC-001
therefore checks like any other write.

The uuid-wide `min()` inside `:Node.created_at` is deliberate: the surviving vertex must report the
original creation time, which lives on the other vertex's edge. `node_duplicate` copies `created_at`
forward onto the new vertex, so a derivation narrowed to one vertex's own edges would report the
migration timestamp instead.

## Consumers

- **Write sites** must produce values equal to the recompute. This is SC-001: assertions compare a
  default-branch read against the recompute rather than against a hard-coded timestamp.
- **The repair migration** (FR-005) applies the recompute directly.
- **The rollback** — `core/rollback.py::GraphRollbacker` — must be able to *undo* any write this
  contract permits. A write made at `branch_level = 1` on `-global-` during a default-branch merge is
  as much in scope for rollback as one made on the default branch itself; a rollback that reaches only
  one of the two branches has not restored the invariant.
- **The read path** — `core/query/node.py::NodeListGetInfoQuery`,
  `core/query/node.py::NodeListGetAttributeQuery`, and
  `core/query/subquery.py::build_subquery_order_metadata` — consumes the properties only when the
  query branch is default or global. It is unchanged by this feature; the invariant exists to keep
  its fast path equal to the slow path it replaces.
