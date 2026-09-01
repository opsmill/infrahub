# Contract: Vertex Metadata Invariant

This feature introduces no external API. Its contract is internal but normative: it is the single
rule that the write sites, the repair migration, and the SC-001 test oracle must all agree on. It is
recorded here so those three can be checked against one statement rather than against each other.

## Scope

Applies to the properties `created_at`, `created_by`, `updated_at`, `updated_by` on `:Node`,
`:Attribute`, and `:Relationship` vertices.

Does **not** apply to `previous_updated_at` / `previous_updated_by`, which are a rollback snapshot
owned by the schema-migration and merge paths, not part of this cache.

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

## The recompute (oracle)

Given a vertex, its metadata is defined as a pure function of its `branch_level = 1` edges. This is
`core/migrations/graph/m050_backfill_vertex_metadata.py`'s derivation, extended to the actor fields.

| Vertex | `created_at` | `updated_at` |
|---|---|---|
| `:Attribute` | `from` of the level-1 `HAS_ATTRIBUTE` edge | `max()` over `from` and non-null `to` of the vertex's level-1 edges; falls back to `created_at` |
| `:Relationship` | `min(from)` over level-1 `IS_RELATED` edges | `max()` over `from` and non-null `to` of the vertex's level-1 non-`IS_RELATED` edges; falls back to `created_at` |
| `:Node` | `min(from)` over level-1 `IS_PART_OF` edges **across every vertex sharing the uuid** | `max(updated_at)` over linked `:Attribute` / `:Relationship` vertices; falls back to `created_at` |

`created_by` / `updated_by` are the `from_user_id` — or `to_user_id`, when a `to` supplied the
winning timestamp — of the edge that produced the corresponding timestamp.

The uuid-wide `min()` for `:Node.created_at` is deliberate: kind- and inheritance-migration leave two
vertices sharing one uuid, and both must report the original creation time.

## Consumers

- **Write sites** must produce values equal to the recompute. This is SC-001: assertions compare a
  default-branch read against the recompute rather than against a hard-coded timestamp.
- **The repair migration** (FR-005) applies the recompute directly.
- **The read path** — `core/query/node.py::NodeListGetInfoQuery`,
  `core/query/node.py::NodeListGetAttributeQuery`, and
  `core/query/subquery.py::build_subquery_order_metadata` — consumes the properties only when the
  query branch is default or global. It is unchanged by this feature; the invariant exists to keep
  its fast path equal to the slow path it replaces.
