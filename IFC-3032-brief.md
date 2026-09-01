# Idea Brief: Branch-agnostic vertex metadata correctness (IFC-3032)

**Status**: Ready for next step
**Ticket**: https://opsmill.atlassian.net/browse/IFC-3032 (not read — Jira behind auth; brief built from the
seed description plus code investigation)

**Seed**: Verify that `created_at/by` and `updated_at/by` are correctly maintained on `:Node`, `:Attribute`,
and `:Relationship` vertices. In particular, check branch-agnostic fields on branch-aware objects where the
write happens on a non-default branch but the change lands on the `-global-` branch.

## Users and Value

Anyone reading metadata on the default branch: UI "last updated" columns, `order_by` on `updated_at`
(`backend/infrahub/core/query/subquery.py:193`), and API consumers auditing provenance. Today they can be
shown a timestamp that is stale (a change happened, the clock didn't move) or advanced (the clock moved for a
change they cannot see). Both are silent; nothing errors.

The vertex properties exist as a denormalised cache so that default-branch metadata reads are fast. A cache
that disagrees with the graph is worse than no cache, because the slow path it replaces is correct.

## The Invariant

> A vertex's `created_at/by` and `updated_at/by` MUST reflect the latest change **visible on the default
> branch** — i.e. the latest change carried by a `branch_level = 1` edge, whether that edge is on the default
> branch or on `-global-`.

Confirmed against the read path: vertex properties are read only when the query branch is default or global
(`core/query/node.py:1386-1450`, `core/query/node.py:767-826`, `core/query/subquery.py:193`). User-branch reads
derive metadata from edge `from` / `to` / `from_user_id` instead.

**Root cause of every finding below.** Write sites gate on *"is the owning object's support branch
default/global?"* as a proxy for *"is this edge `branch_level = 1`?"*. The proxy is exact only when the field's
branch support equals the node's branch support. Every divergence below is an instance of that one mistake.

## User Journeys

### P1 — Default-branch metadata reflects agnostic changes made from a branch

Journey: a user changes a branch-agnostic field on a branch-aware object while working on a feature branch; a
second user reading that object on the default branch sees both the new value and a matching
`updated_at` / `updated_by`.

- **Given** an object of a branch-aware kind exists on the default branch, with a field whose branch support
  is `agnostic`
- **When** a user on feature branch `foo` updates that field
- **Then** reading the object on the default branch shows the new value, and `updated_at` / `updated_by` equal
  the time and actor of that update

### P2 — Default-branch metadata does not move for changes it cannot see

- **Given** an object of a branch-agnostic kind, with a field whose branch support is `aware`
  (live: `CoreReadOnlyRepository.ref`)
- **When** a user on feature branch `foo` updates that field
- **Then** reading the object on the default branch shows the unchanged value **and** an unchanged
  `updated_at` / `updated_by`

### P3 — Schema migrations on a branch set metadata for the rows they publish globally

- **Given** a branch-aware kind with existing objects on the default branch
- **When** a user on feature branch `foo` adds a branch-agnostic attribute to that kind, and the schema change
  is later merged
- **Then** the new Attribute vertex has `created_at` / `created_by` populated and the owning Node's
  `updated_at` has advanced, both readable on the default branch

### P4 — Existing graphs are repaired

- **Given** a graph written by a version predating the fix, containing vertices whose metadata disagrees with
  their level-1 edges
- **When** the repair migration runs
- **Then** every affected vertex's metadata equals the edge-derived recompute, and a second run changes zero
  vertices

## Findings

### F1 — Node vertex not bumped for agnostic field changes from a user branch (under-set)

`core/node/__init__.py:1199-1201` gates `_save_metadata` on `self.get_branch_based_on_support_type()` — the
*node's* support:

```python
update_branch = self.get_branch_based_on_support_type()
if update_branch.is_default or update_branch.is_global:
    await self._save_metadata(db=db, branch=update_branch)
```

Aware node + agnostic attribute updated on `foo` → gate is `foo` → skipped, while the `HAS_VALUE` edge landed
on `-global-` at level 1 and is visible on `main`.

The Attribute vertex itself is correct: `core/query/attribute.py:96-99` guards on `$branch_level = 1` against
`attr.get_branch_based_on_support_type()`, as do the flag / node-property / delete variants.

No core-schema instance; reachable via user-defined schemas. This is the case named in the seed.

### F1b — Node vertex bumped for changes not visible on the default branch (over-set)

Same gate, opposite direction. Agnostic node + aware attribute updated on `foo` → the gate resolves to
`-global-` → `_save_metadata` fires and `n.updated_at` advances on `main` for a change `main` cannot see.

**Live in the core schema**: `CoreReadOnlyRepository` is agnostic and visible on every branch; `ref` and
`commit` are aware. Best repro anchor — no custom schema fixture needed.

### F2 — Create path gates field-vertex metadata on the node's branch (latent)

`NodeCreateAllQuery` builds edges from the per-field branch — `core/attribute.py:683-694` downgrades agnostic
fields (and local fields on agnostic nodes) to `-global-` / level 1 — but gates the vertex properties on
`self.branch` (`core/query/node.py:266-281`). Under-set for an agnostic field on an aware node created on a
branch; over-set for an aware field on an agnostic node.

Both self-heal — via merge, or via a later default-branch write — so this is latent rather than observable.

### F3 — Relationship create/delete stamp peer Node vertices unconditionally (low)

`core/query/relationship.py:340-345` (create) and `:613-618` (delete) issue a bare `SET s.updated_at` /
`SET d.updated_at` whenever the *relationship's* branch is level 1, stamping peers that may not exist on the
default branch. `RelationshipDeleteAllQuery` (`:1366`, `:1409`) has the same shape.

`RelationshipUpdatePropertyQuery` (`:460-487`) already guards this correctly, requiring a level-1 active
`IS_RELATED` **and** a level-1 active `IS_PART_OF`. Self-corrects at merge; lowest severity.

### F5 — Twin handling on the delete guard

`NodeUpdateMetadataQuery`'s `OPTIONAL MATCH ... {status: "deleted", branch: $branch}` / `WHERE delete_edge IS
NULL` correctly excludes a kind/inheritance-migrated twin *only when `$branch` is the default branch*.
`_save_metadata` currently passes `-global-` for agnostic nodes, so the check looks on the wrong branch and
both twins can be bumped.

This is the same problem `DiffMergeMetadataQuery` solves with its opening clause:

```cypher
WHERE NOT EXISTS {
    MATCH (n)-[migrated_out:IS_PART_OF {branch: $target_branch, status: "deleted"}]->(:Root)
    WHERE migrated_out.from < $at AND migrated_out.to IS NULL
}
```

The migrated-out twin keeps its original `active` `IS_PART_OF` open, so `status: "active" AND r.to IS NULL`
matches both twins.

### F6 — Schema migrations gate vertex metadata on the migration's branch, not the edge's level

All seven migration queries use the same Python-side scalar:

```python
self.params["set_metadata"] = self.branch.is_default or self.branch.is_global
```

Three of them write level-1 edges from a level-2 branch, so the scalar is wrong exactly there:

| Migration | Edge branch decision | `set_metadata` on a user branch | Verdict |
|---|---|---|---|
| `attribute_add` | per-node in Cypher: `$is_branch_agnostic OR ($is_branch_local AND n.branch_support = $agnostic_support)` → `-global-`, level 1 | `false` | **under-set** |
| `node_duplicate` | preserves source edge: `CASE WHEN rel.branch = "-global-" THEN "-global-"` + matching level | `false` | **under-set** |
| `node_remove` | same `CASE WHEN ... = $global_branch` for deletion edges (`:25-26`) | `false` | **under-set** |
| `attribute_remove` | fixed `$rel_props` at migration branch level | `false` | consistent |
| `attribute_rename` | fixed, no global handling | `false` | consistent |
| `attribute_kind_update` | fixed, no global handling | `false` | consistent |
| `node_relationship_remove` | fixed, no global handling | `false` | consistent |

Sites: `migrations/query/attribute_add.py:74` and `:144-162`; `migrations/query/node_duplicate.py:163`
and `:190`; `migrations/schema/node_remove.py:45`, `:116`, `:246`.

**Merge does not repair these.** The rows were written to `-global-`, not to `foo`, so they never appear in the
branch diff — `DiffMergeMetadataQuery` is driven by `node_uuids` from the diff and never sees them. The schema
change merges, the attribute becomes visible on `main`, and its vertex metadata is NULL permanently, on a node
whose `updated_at` never moved.

Highest severity alongside F1 / F1b, because the owning node already exists on the default branch.

## The Four Live Mismatches (test matrix basis)

| # | Node support | Field support | Live instance |
|---|---|---|---|
| 1 | aware | agnostic (rel) | `BuiltinIPPrefix.resource_pool` |
| 2 | aware | agnostic (attr) | none — needs a test schema; the seed's original case |
| 3 | agnostic | aware (attr) | `CoreReadOnlyRepository.ref`, `.commit` |
| 4 | agnostic | local (attr) | `CoreGenericRepository.internal_status`, `.sync_status`, `CoreRepository.commit` |

Enumerated by walking `core_models` and comparing each field's `branch` against its node's.

## Functional Requirements

- **FR-001**: `Node._update` MUST decide whether to write Node vertex metadata from whether any changed field
  wrote a `branch_level = 1` edge, not from the node's own branch support.
  *Verify:* P2's scenario leaves `updated_at` unchanged; P1's advances it.
- **FR-002**: `_save_metadata` MUST pass the default branch to `NodeUpdateMetadataQuery`, so the existing
  delete-edge guard excludes both nodes deleted on the default branch and migrated-out twins.
  *Verify:* delete a node on `main`, change an agnostic field from a pre-delete branch, assert no bump; repeat
  with a kind-migrated twin present and assert only the active vertex is considered.
- **FR-003**: `NodeCreateAllQuery` MUST gate each Attribute/Relationship vertex's metadata on that field's own
  `branch_level`, not the node's.
  *Verify:* create mismatch #3 on a branch, assert the aware attribute vertex has no metadata; create #1 on
  `main`, assert the agnostic relationship vertex does.
- **FR-004**: `RelationshipCreateQuery`, `RelationshipDeleteQuery`, and `RelationshipDeleteAllQuery` MUST stamp
  a peer Node vertex only when that peer has a level-1 active `IS_PART_OF`.
  *Verify:* create an agnostic relationship between two aware nodes that exist only on a branch; assert
  neither peer's vertex metadata changed.
- **FR-005**: A repair migration MUST recompute metadata on `Node`, `Attribute`, and `Relationship` vertices,
  restricted to kinds where some field's branch support differs from the node's, in both directions.
  Dropping m050's `IS NULL` guard handles both the NULLs F6 leaves and the wrong values F1b leaves.
  *Verify:* SC-002.
- **FR-006**: `dev/knowledge/backend/database-schema.md` MUST state the level-1-edge invariant in place of
  *"set only on default/global branches"*, which is the buggy proxy stated as fact. Constitution II requires
  cross-branch side effects be documented.
- **FR-007**: `attribute_add`, `node_duplicate`, and `node_remove` MUST gate each vertex's metadata write on
  that vertex's own edge level — the `on_global_branch` / `CASE WHEN ... = $global_branch` decision already
  computed in Cypher — rather than on the Python-side `set_metadata` scalar. The four consistent migrations
  keep `set_metadata` unchanged.
  *Verify:* on a feature branch, add an agnostic attribute to a branch-aware kind; assert the new Attribute
  vertex has `created_at` / `created_by` set and the Node's `updated_at` advanced, both readable on the default
  branch. A test should also pin that a level-2-only migration still writes no metadata.

## Key Entities

All existing; no new entities.

- `Node` / `Attribute` / `Relationship` vertices and their `created_at/by`, `updated_at/by`,
  `previous_updated_at/by` properties
- `BranchSupportType` — `aware` / `local` / `agnostic`
- The `-global-` branch, and edge `branch_level` (1 = default/global, 2 = user branch)
- `NodeUpdateMetadataQuery`, `DiffMergeMetadataQuery`, `m050_backfill_vertex_metadata`

## Edge Cases

- Node created on a branch, not yet merged → no bump. Handled for free: `NodeUpdateMetadataQuery` requires an
  active level-1 `IS_PART_OF`, and `DiffMergeMetadataQuery` sets it at merge.
- Node deleted on the default branch, agnostic field changed from a pre-delete branch → no bump (FR-002).
- Kind/inheritance-migrated twins sharing a UUID, one active and one deleted → only the active vertex counts
  (FR-002, F5).
- Mixed update touching both an aware and an agnostic field on an aware node from a branch → bump; the
  agnostic half is visible on the default branch.
- Agnostic relationship where one peer is on the default branch and the other only on a branch → stamp exactly
  one (FR-004).
- Schema migration on a branch that writes only level-2 edges → still no metadata (FR-007 regression pin).

## Success Criteria

- **SC-001** (gate): for each of the four live mismatches, crossed with {create, update, delete} ×
  {write on default branch, write on user branch} × {via node save, via schema migration}, a default-branch
  read of `created_at/by` and `updated_at/by` equals the value m050's edge-derived recompute produces. The
  recompute is the oracle, so assertions do not hard-code timestamps. The migration axis needs only the three
  affected queries.
- **SC-002** (gate): the repair migration is idempotent — a second run changes zero vertices.
- **SC-003** (check, not gate): no measured regression beyond noise on relationship create/delete. If the peer
  guard costs anything real, that indicates the wrong design — `RelationshipCreateQuery` already proves a
  level-1 `IS_PART_OF` in `add_source_match_to_query` when the peer's support branch is level 1, so only the
  aware-peer case needs an added `OPTIONAL MATCH`.

## Constitution Alignment

- **II. Branch-Safe by Default** — squarely the violated principle: *"Cross-branch side effects (e.g.,
  modifying branch-agnostic nodes) MUST be explicitly documented and tested."* Drives FR-006 and SC-001.
- **V. Query Performance & Efficiency** — the cache exists for speed; SC-003 keeps the fix from trading the win
  away. `EXPLAIN` on the modified relationship queries is the SHOULD here.
- **IV. Test Discipline** — SC-001's matrix is the coverage this area currently lacks.

## Governance Gates Crossed

- [x] **Database / migration change** — repair migration (FR-005). Approved for this ticket.
- [ ] API change — none; read shapes unchanged.
- [ ] New dependency — none.
- [ ] CI/CD change — none.
- [ ] Auth change — none.

## Assumptions

- Vertex metadata is read only on default/global branches; user-branch reads derive from edges. Verified in
  code, not assumed.
- `DiffMergeMetadataQuery` correctly sets metadata at merge and needs no change — but note it only covers nodes
  in the branch diff, which is why F6 is not self-healing.
- m050's derivation (`max()` over level-1 edge `from` / `to`) is the authoritative recompute for both tests and
  repair.

## Out of Scope (v1)

- Aware attributes on agnostic nodes being unreachable on the default branch at all (their `HAS_ATTRIBUTE`
  edges are level 2). A real smell exposed by F2, but a separate defect about data visibility, not metadata.
- `attribute_add` sends an agnostic attribute's rows to `-global-` while `attribute_remove` writes the deletion
  at the migration branch's level — added globally, removed locally. Asymmetric, but not a metadata defect.
- Any change to what the metadata read path returns, or to `order_by` semantics.
- F3's peers-not-on-default over-stamp during merge, which `DiffMergeMetadataQuery` already overwrites.

## Open Questions

- **[NEEDS CLARIFICATION: is the `local`-on-agnostic create/update split intentional?]**
  `get_create_data` downgrades a `LOCAL` attribute on an `AGNOSTIC` node to `-global-` / level 1
  (`core/attribute.py:687-689`), but `get_branch_based_on_support_type` does not — it special-cases only
  `AGNOSTIC` (`core/attribute.py:188-190`). So mismatch #4 (`CoreRepository.commit`) is created at level 1 and
  updated at level 2. Beyond metadata, that means the default branch keeps showing the creation-time value.
  Either `LOCAL` deliberately means per-branch-after-creation, or the two methods have drifted and this is a
  value-correctness bug larger than IFC-3032.
- **[NEEDS CLARIFICATION: can an agnostic node's kind/inheritance be migrated?]**
  If yes, F5 means both twins are being bumped today for agnostic nodes, and FR-002 fixes a live bug rather
  than a latent one.
- **[NEEDS CLARIFICATION: should `attribute_kind_update`, `attribute_rename`, and `node_relationship_remove`
  handle agnostic fields at all?]**
  They have no `-global-` handling, so applied to an agnostic field they write level-2 edges for data living at
  level 1 — the change would not be visible on the default branch where the data is. That makes their metadata
  gating self-consistent, which is why they are not in FR-007, but it may indicate a value-correctness gap
  wider than IFC-3032.

## Proposed Sub-task Breakdown

Each is intended to be its own commit / PR, ordered so the tests land with the fix they cover.

1. **FR-001 + FR-002** — `Node._update` gate and the branch passed to `NodeUpdateMetadataQuery`. Anchor test on
   F1b (`CoreReadOnlyRepository`) since it needs no custom schema.
2. **FR-007** — the three schema-migration queries. Highest-severity remaining after 1.
3. **FR-003** — `NodeCreateAllQuery` per-field gating.
4. **FR-004** — relationship create/delete peer guard. Stage separately so it can be reverted on perf grounds
   without touching the rest.
5. **FR-005** — repair migration.
6. **FR-006** — knowledge-doc correction.
