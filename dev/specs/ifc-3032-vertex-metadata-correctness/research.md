# Phase 0 Research: Branch-Agnostic Vertex Metadata Correctness

All unknowns were resolved by reading the code the spec names. No external research was required —
this is a correctness defect in an existing subsystem, not a technology selection.

## R1 — What decides the level of the edge a field write actually produces?

**Decision**: The field's own `get_branch_based_on_support_type()`, evaluated per field, is the
authoritative predicate for the *update* path. `Node._update` must consult it per changed field
rather than consulting the node's.

**Rationale**: `core/query/attribute.py::AttributeQuery.__init__` sets
`self.branch = branch or self.attr.get_branch_based_on_support_type()` and then
`self.params["branch_level"] = self.branch.hierarchy_level`. Every attribute write query
(`AttributeUpdateValueQuery`, `AttributeUpdateFlagQuery`, `AttributeUpdateNodePropertyQuery`, and the
delete variants) stamps its own vertex behind `WHERE $branch_level = 1` derived from exactly that
value. `core/relationship/model.py::Relationship.get_branch_based_on_support_type` plays the same
role on the relationship side. So the field-level predicate is not an approximation of the edge
level — it *is* the value the edge is written with.

**Alternatives considered**:

- *Read the edge level back from the database after the write.* Correct but adds a round trip per
  save on the hot path, and the value is already known in Python before the write. Rejected on
  Constitution V.
- *Pass a flag down from each field's `save()` return.* `BaseAttribute.save` returns a changelog
  entry, not a branch; threading a second return value through every field type is a wider change
  than reading a predicate the object already exposes. Rejected on Constitution VII.

## R2 — Which fields count as "changed" for the FR-001 decision?

**Decision**: The fields already recorded on the `NodeChangelog` that `Node._update` builds —
`node_changelog.updated_fields` plus the relationship entries — are the changed set. The gate
becomes: write Node vertex metadata if **any** changed field's own support branch is level 1.

**Rationale**: `Node._update` only reaches the metadata gate under `if node_changelog.has_changes`,
and the changelog is populated from the truthy return of each `attr.save()` / `rel.save()`. It
therefore already carries exactly the set of fields that produced edges, including the fields added
by `_recompute_local_jinja2`, `_recompute_hfid`, and `_recompute_display_label`.

**Alternatives considered**:

- *Use the caller-supplied `fields` argument.* It is the set the caller asked to save, not the set
  that changed, and it is `None` for a full save. Rejected as wrong.

## R3 — Does `get_branch_based_on_support_type` diverge from `get_create_data`?

**Decision**: Yes, and FR-001 deliberately follows the *update* path
(`get_branch_based_on_support_type`), while FR-003 follows the *create* path
(`get_create_data`). Each gate mirrors the edges its own path writes.

**Rationale**: `core/attribute.py::BaseAttribute.get_create_data` downgrades both `AGNOSTIC` fields
and `LOCAL` fields on an `AGNOSTIC` node to `-global-` / level 1, whereas
`core/attribute.py::BaseAttribute.get_branch_based_on_support_type` special-cases only `AGNOSTIC`.
Mismatch #4 (`CoreRepository.commit`) is therefore created at level 1 and updated at level 2. This
divergence is a value-correctness question recorded in the spec's Out of Scope. Because each gate is
derived from the path it guards, the metadata stays correct under **either** answer to that
question — which is why this feature does not need it resolved first.

**Alternatives considered**:

- *Unify the two methods as part of this work.* That changes which branch data is written to, not
  just which vertex properties are stamped — a data-visibility change well outside IFC-3032.
  Rejected; filed as a follow-up instead.

## R4 — How should each of the three migration queries express the per-vertex gate?

**Decision**: Each already computes the edge's branch decision in Cypher. Reuse that expression as
the gate, OR-ed with the existing `$set_metadata` scalar so default-branch behaviour is unchanged.

| Query | Expression already present | Gate becomes |
|---|---|---|
| `core/migrations/query/attribute_add.py::AttributeAddQuery` | `on_global_branch` (`$is_branch_agnostic OR ($is_branch_local AND n.branch_support = $agnostic_support)`) | Attribute vertex: `$set_metadata OR on_global_branch`. Node vertex: additionally require the node's own `is_part_of_e.branch_level = 1`. Both `on_global_branch` and `is_part_of_e` are currently dropped from the `WITH` before the metadata `CALL` and must be carried through. |
| `core/migrations/query/node_duplicate.py::NodeDuplicateQuery` | `CASE WHEN rel.branch = "-global-" THEN ...` in `_render_sub_query_out` / `_render_sub_query_in` | Gate on whether the node's own `IS_PART_OF` edge is on `-global-`, i.e. `$set_metadata OR is_part_of_e.branch = $global_branch`. The matched `IS_PART_OF` edge must be returned from the existing `CALL (node)` subquery, which today returns only `node` and `is_active`. |
| `core/migrations/schema/node_remove.py::NodeRemoveMigrationQueryIn` / `::NodeRemoveMigrationQueryOut` | `_branch_from_existing(...)` → `new_branch_level` | `$set_metadata OR new_branch_level = 1`. This requires **reordering**: the metadata `CALL` currently runs before `_branch_from_existing` computes `new_branch_level`, so the `WITH` that computes it must move above the metadata block. |

**Rationale**: Gating on an expression the query already computes keeps the gate and the edge it
guards provably in step — the failure mode being fixed is precisely two independently-computed
answers to the same question drifting apart.

**Alternatives considered**:

- *Compute a richer `set_metadata` in Python.* Impossible for `attribute_add` and `node_duplicate`:
  their decision is per-matched-node (`n.branch_support`, the matched edge's branch), which Python
  does not know before the query runs. Rejected as not expressible.
- *Always set metadata and let a later pass correct it.* Reintroduces the over-set half of the bug.
  Rejected.

## R5 — Can the repair migration identify affected vertices without the schema?

**Decision**: Yes. Restrict on `branch_support` properties stored on the vertices themselves:
a Node/field pair is in scope when `field.branch_support <> n.branch_support`.

**Rationale**: `core/query/node.py::NodeCreateAllQuery` writes `branch_support` onto every Attribute
and Relationship vertex it creates (`{ uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support }`),
`core/migrations/query/attribute_add.py::AttributeAddQuery` does the same
(`CREATE (a:Attribute { name: $attr_name, branch_support: $branch_support })`), and Node vertices
carry `branch_support` as well. A graph migration therefore needs no schema load — which matters,
because graph migrations run before the schema is necessarily loadable.

This filter is a slight *superset* of the true mismatch set: it also matches `local`-on-`aware`
pairs, which are consistent. Recomputing a consistent vertex is a no-op, so the superset is safe and
avoids encoding the branch-support lattice in Cypher.

**Alternatives considered**:

- *Sweep every vertex in the graph.* m050's derivation is not identical to what the write path
  produces in every case (`Node.updated_at` is derived from field vertices rather than from the
  node's own edges), so an unrestricted sweep risks changing values that are currently correct. The
  spec's restriction to mismatched kinds is what bounds that blast radius. Rejected.
- *Load the schema and enumerate mismatched kinds in Python.* Graph migrations run against a
  database whose schema may predate the current models. Rejected as fragile.

## R6 — The recompute oracle, and the gap in m050

**Decision**: Reuse m050's derivation, extended to the actor fields, as the single oracle shared by
the repair migration and the SC-001 assertions.

- `Attribute.created_at` = `from` of the level-1 `HAS_ATTRIBUTE` edge
- `Relationship.created_at` = `min(from)` over level-1 `IS_RELATED` edges
- `Node.created_at` = `min(from)` over level-1 `IS_PART_OF` edges **for all vertices sharing the uuid**
  (this is what makes kind-migrated twins agree)
- `*.updated_at` = `max()` over the `from` and non-null `to` of the level-1 edges of the vertex,
  falling back to `created_at`
- `Node.updated_at` = `max(updated_at)` over the linked Attribute/Relationship vertices, falling back
  to `created_at`
- `*_by` = the `from_user_id` (or `to_user_id`, when a `to` supplied the winning timestamp) of the
  edge that produced the corresponding timestamp

**Rationale**: `core/migrations/graph/m050_backfill_vertex_metadata.py` already implements everything
above **except the `_by` fields** — it sets only `created_at` and `updated_at`. Since SC-001 asserts
on `created_by` / `updated_by` too, the repair migration must carry the derivation across to the
actor fields. Edges already store `from_user_id` and `to_user_id`, so no new data is needed. This is
a completion of m050's existing rule, not a new one.

**Alternatives considered**:

- *Leave `_by` untouched in the repair.* Would leave `updated_by` pointing at whoever last triggered
  an over-set bump, contradicting the timestamp beside it. Rejected as shipping a half-repaired cache.

## R7 — Idempotency (SC-002)

**Decision**: The repair writes only `created_at/by` and `updated_at/by`, computed as a pure function
of edges it does not modify, and does **not** touch `previous_updated_at/by`.

**Rationale**: A second run recomputes the same values from the same edges, so no property changes.
Touching `previous_updated_*` would break this: the second run would snapshot the first run's result
and report changed vertices. The `previous_*` pair exists to let a merge-failure rollback restore
pre-merge values (`backend/tests/component/core/migrations/schema/metadata_helpers.py` documents this);
a repair migration has no rollback partner and must leave it alone.

## R8 — Where the relationship peer guard already exists

**Decision**: Copy the guard shape from
`core/query/relationship.py::RelationshipUpdatePropertyQuery`, which already requires a level-1
active `IS_RELATED` **and** a level-1 active `IS_PART_OF` before stamping a peer.

**Rationale**: The correct query already exists in the same module; the three broken ones
(`RelationshipCreateQuery`, `RelationshipDeleteQuery`, `RelationshipDeleteAllQuery`) issue a bare
`SET s.updated_at` / `SET d.updated_at` under `if self.branch.is_default or self.branch.is_global`.
Constitution VII: follow the established pattern rather than invent a second one.

**Performance note (SC-003)**: `RelationshipCreateQuery.query_init` already calls
`add_source_match_to_query(source_branch=self.source.get_branch_based_on_support_type())` and the
destination equivalent, which proves a level-1 `IS_PART_OF` whenever the peer's support branch is
level 1. Only the aware-peer case needs an added `OPTIONAL MATCH`. If a benchmark shows real cost
here, that is evidence the guard was written in the wrong place, not a reason to drop it.

## R9 — Test level

**Decision**: Component tests under `backend/tests/component/`, extending the existing metadata
suites rather than starting new ones.

**Rationale**: The invariant is a statement about what a Cypher read returns after a Cypher write, so
it cannot be tested without a database — ruling out unit tests. It does not span services, so it does
not need functional or integration-Docker tests. Constitution IV names component tests as the level
for "small scope, may use database". Existing anchors to extend:

- `backend/tests/component/core/migrations/schema/metadata_helpers.py` — `VertexMetadata`,
  `get_node_vertex_metadata`, `get_attribute_vertex_metadata`
- `backend/tests/component/core/migrations/graph/test_050.py` — the m050 pattern, including the
  agnostic/aware test schemas the SC-001 matrix needs for mismatch #2
- `backend/tests/component/core/test_relationship_metadata.py` — FR-004's home
