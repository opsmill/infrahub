# Feature Specification: Branch-Agnostic Vertex Metadata Correctness

**Feature Branch**: `vertex-metadata-correctness-ifc-3032`

**Created**: 2026-08-31

**Status**: Draft

**Ticket**: [IFC-3032](https://opsmill.atlassian.net/browse/IFC-3032)

**Input**: Jira ticket IFC-3032 (authoritative) plus idea brief `IFC-3032-brief.md` — verify that `created_at/by` and `updated_at/by` are correctly maintained on `:Node`, `:Attribute`, and `:Relationship` vertices, in particular for branch-agnostic fields on branch-aware objects where the write happens on a non-default branch but the change lands on the `-global-` branch.

## Problem Statement

Vertex properties (`created_at`, `created_by`, `updated_at`, `updated_by`) exist as a denormalised cache so that default-branch metadata reads are fast. Today that cache can silently disagree with the graph it summarises. Nothing errors; a reader is simply shown a timestamp that is **stale** (a change happened, the clock didn't move) or **advanced** (the clock moved for a change the reader cannot see).

A cache that disagrees with the graph is worse than no cache, because the slow path it replaces is correct.

The defect is **silent by construction**: no error is raised, and a wrong timestamp is
indistinguishable from a right one without recomputing it from the edges. The absence of user
reports is therefore the expected symptom, not evidence of low impact.

### The Invariant

> A vertex's `created_at/by` and `updated_at/by` MUST reflect the latest change **visible on the default branch** — i.e. the latest change carried by a `branch_level = 1` edge, whether that edge is on the default branch or on `-global-`.

This is confirmed against the read path: vertex properties are read only when the query branch is default or global (`core/query/node.py::NodeListGetInfoQuery._add_created_metadata_to_query` / `._add_updated_metadata_to_query`, `core/query/node.py::NodeListGetAttributeQuery._add_created_metadata_to_query` / `._add_updated_metadata_to_query`, and `core/query/subquery.py::build_subquery_order_metadata`). User-branch reads derive metadata from edge `from` / `to` / `from_user_id` instead.

### Root Cause

Write sites gate metadata on *"is the owning object's support branch default/global?"* as a proxy for *"is this edge `branch_level = 1`?"*. The proxy is exact only when the field's branch support equals the node's branch support. Every finding below is an instance of that one mistake.

### Who Is Affected

Anyone reading metadata on the default branch: UI "last updated" columns, `order_by` on `updated_at` (`core/query/subquery.py::build_subquery_order_metadata`), and API consumers auditing provenance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Default-branch metadata reflects agnostic changes made from a branch (Priority: P1)

A user changes a branch-agnostic field on a branch-aware object while working on a feature branch. A second user reading that object on the default branch sees both the new value and a matching `updated_at` / `updated_by`.

**Why this priority**: This is the case named in the ticket seed, and it is an under-set: the default branch shows new data with a stale clock, so consumers ordering or auditing by `updated_at` miss the change entirely.

**Independent Test**: Fully testable by updating an agnostic attribute on an aware node from a feature branch and reading the node's vertex metadata on the default branch. Delivers correct provenance for agnostic writes without touching any other finding.

**Acceptance Scenarios**:

1. **Given** an object of a branch-aware kind exists on the default branch, with a field whose branch support is `agnostic`, **When** a user on feature branch `foo` updates that field, **Then** reading the object on the default branch shows the new value, and `updated_at` / `updated_by` equal the time and actor of that update
2. **Given** the same object, **When** a user on feature branch `foo` updates **both** an aware and an agnostic field in one save, **Then** the default-branch `updated_at` advances (the agnostic half is visible on the default branch)

---

### User Story 2 - Default-branch metadata does not move for changes it cannot see (Priority: P1)

A user changes a branch-aware field on a branch-agnostic object from a feature branch. A reader on the default branch sees neither the new value nor a moved clock.

**Why this priority**: This is the same gate in the opposite direction (over-set) and it is **live in the core schema** — `CoreReadOnlyRepository` is agnostic and visible on every branch while `ref` and `commit` are aware. It needs no custom schema fixture, so it is the cheapest anchor for the fix.

**Independent Test**: Fully testable by updating `CoreReadOnlyRepository.ref` on a feature branch and asserting the default-branch vertex metadata is unchanged.

**Acceptance Scenarios**:

1. **Given** an object of a branch-agnostic kind, with a field whose branch support is `aware` (live: `CoreReadOnlyRepository.ref`), **When** a user on feature branch `foo` updates that field, **Then** reading the object on the default branch shows the unchanged value **and** an unchanged `updated_at` / `updated_by`
2. **Given** an agnostic relationship whose two peers are branch-aware nodes that exist only on a feature branch, **When** the relationship is created or deleted, **Then** neither peer's vertex metadata changes

---

### User Story 3 - Schema migrations on a branch set metadata for the rows they publish globally (Priority: P1)

A user adds a branch-agnostic attribute to a branch-aware kind from a feature branch. When the schema change merges, the new attribute is visible on the default branch with populated metadata.

**Why this priority**: Equal severity to Stories 1 and 2 — and uniquely **not self-healing**. The rows are written to `-global-`, not to `foo`, so they never appear in the branch diff; `DiffMergeMetadataQuery` is driven by `node_uuids` from the diff and never sees them. The attribute becomes visible on the default branch with permanently NULL metadata, on a node whose `updated_at` never moved.

**Independent Test**: Fully testable by adding an agnostic attribute to an aware kind on a feature branch and asserting the new Attribute vertex carries `created_at` / `created_by` and the owning Node's `updated_at` advanced, both read on the default branch.

**Acceptance Scenarios**:

1. **Given** a branch-aware kind with existing objects on the default branch, **When** a user on feature branch `foo` adds a branch-agnostic attribute to that kind and the schema change is later merged, **Then** the new Attribute vertex has `created_at` / `created_by` populated and the owning Node's `updated_at` has advanced, both readable on the default branch
2. **Given** a schema migration on a feature branch that writes only `branch_level = 2` edges, **When** it runs, **Then** no vertex metadata is written (regression pin)

---

### User Story 4 - Existing graphs are repaired (Priority: P2)

An operator upgrades an Infrahub instance whose graph was written by a version predating this fix. The upgrade repairs every vertex whose metadata disagrees with its level-1 edges.

**Why this priority**: The fix alone leaves every pre-existing wrong value in place — including the permanently-NULL attributes from Story 3, which no later write repairs. It is P2 only because it depends on the recompute rule that Stories 1–3 establish.

**Independent Test**: Fully testable by seeding a graph with known-wrong vertex metadata, running the repair, and asserting every affected vertex matches the edge-derived recompute.

**Acceptance Scenarios**:

1. **Given** a graph containing vertices whose metadata disagrees with their level-1 edges, **When** the repair migration runs, **Then** every affected vertex's metadata equals the edge-derived recompute
2. **Given** the repair has already run, **When** it runs a second time, **Then** it changes zero vertices

---

### User Story 5 - A failed merge leaves no orphaned metadata (Priority: P2)

A merge into the default branch runs a schema change that adds or removes a branch-agnostic field on a
branch-aware kind, and then fails. The rollback restores the graph completely — including the vertex
metadata those globally-published rows bumped.

**Why this priority**: Named explicitly in the ticket. It is P2 rather than P1 because it needs a
merge to fail, but its blast radius is the worst in the feature: a partial rollback leaves the graph
in a state no later write repairs, with metadata attributed to a merge that did not happen.

**Independent Test**: Fully testable by merging a schema change that adds an agnostic attribute to an
aware kind, forcing the merge to fail, and asserting the rollback restored both the edges and the
vertex metadata.

**Acceptance Scenarios**:

1. **Given** a merge into the default branch whose schema-migration portion adds a branch-agnostic
   attribute to a branch-aware kind, **When** the merge fails and is rolled back, **Then** the
   `-global-` edges the migration created are reversed and every vertex whose metadata it bumped is
   restored from its `previous_updated_at` / `previous_updated_by` snapshot
2. **Given** the same merge removing an agnostic field instead of adding one, **When** the merge fails
   and is rolled back, **Then** the same restoration holds

---

## Findings

The four defects the fix must close, plus the two guard defects they depend on.

### F1 — Node vertex not bumped for agnostic field changes from a user branch (under-set)

`core/node/__init__.py::Node._update` gates `_save_metadata` on `self.get_branch_based_on_support_type()` — the *node's* support:

```python
update_branch = self.get_branch_based_on_support_type()
if update_branch.is_default or update_branch.is_global:
    await self._save_metadata(db=db, branch=update_branch)
```

Aware node + agnostic attribute updated on `foo` → the gate resolves to `foo` → skipped, while the `HAS_VALUE` edge landed on `-global-` at level 1 and is visible on the default branch.

The Attribute vertex itself is correct: `core/query/attribute.py::AttributeUpdateValueQuery` guards on `$branch_level = 1` against `attr.get_branch_based_on_support_type()`, as do the flag / node-property / delete variants.

No core-schema instance; reachable via user-defined schemas. This is the case named in the ticket seed.

### F1b — Node vertex bumped for changes not visible on the default branch (over-set)

Same gate, opposite direction. Agnostic node + aware attribute updated on `foo` → the gate resolves to `-global-` → `_save_metadata` fires and `n.updated_at` advances on the default branch for a change the default branch cannot see.

**Live in the core schema**: `CoreReadOnlyRepository` is agnostic; `ref` and `commit` are aware. Best repro anchor — no custom schema fixture needed.

### F2 — Create path gates field-vertex metadata on the node's branch (latent)

`NodeCreateAllQuery` builds edges from the per-field branch — `core/attribute.py::BaseAttribute.get_create_data` downgrades agnostic fields (and local fields on agnostic nodes) to `-global-` / level 1 — but gates the vertex properties on `self.branch` (`core/query/node.py::NodeCreateAllQuery.query_init`). Under-set for an agnostic field on an aware node created on a branch; over-set for an aware field on an agnostic node.

Both self-heal — via merge, or via a later default-branch write — so this is latent rather than observable.

### F3 — Relationship create/delete stamp peer Node vertices unconditionally (low)

`core/query/relationship.py::RelationshipCreateQuery.query_init` and `::RelationshipDeleteQuery.query_init` issue a bare `SET s.updated_at` / `SET d.updated_at` whenever the *relationship's* branch is level 1, stamping peers that may not exist on the default branch. `core/query/relationship.py::RelationshipDeleteAllQuery.query_init` has the same shape.

`core/query/relationship.py::RelationshipUpdatePropertyQuery` already guards this correctly, requiring a level-1 active `IS_RELATED` **and** a level-1 active `IS_PART_OF`. Self-corrects at merge; lowest severity.

### F5 — Twin handling on the delete guard

`NodeUpdateMetadataQuery`'s `OPTIONAL MATCH ... {status: "deleted", branch: $branch}` / `WHERE delete_edge IS NULL` correctly excludes a kind/inheritance-migrated twin *only when `$branch` is the default branch*. `_save_metadata` currently passes `-global-` for agnostic nodes, so the check looks on the wrong branch and both twins can be bumped.

This is the same problem `DiffMergeMetadataQuery` solves with its opening clause:

```cypher
WHERE NOT EXISTS {
    MATCH (n)-[migrated_out:IS_PART_OF {branch: $target_branch, status: "deleted"}]->(:Root)
    WHERE migrated_out.from < $at AND migrated_out.to IS NULL
}
```

The migrated-out twin keeps its original `active` `IS_PART_OF` open, so `status: "active" AND r.to IS NULL` matches both twins.

### F4 — Delete path gates the Node vertex on the node's branch (under-set)

`core/query/node.py::NodeDeleteQuery` bumps the Node vertex behind
`if self.branch.is_global or self.branch.is_default`, where the branch comes from the node's
`get_branch_based_on_support_type()` — the same proxy as F1, on a third path.

An **aware** node deleted on a user branch resolves the gate to that branch and skips the bump, while
its agnostic attributes' deletion edges land on `-global-` at level 1 and are visible on the default
branch. Live wherever an aware kind carries an agnostic field.

Named in the ticket's path list ("object delete") alongside create, update, and schema updates.

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
| `node_remove` | same `CASE WHEN ... = $global_branch` for deletion edges | `false` | **under-set** |
| `attribute_remove` | fixed `$rel_props` at migration branch level | `false` | consistent |
| `attribute_rename` | fixed, no global handling | `false` | consistent |
| `attribute_kind_update` | fixed, no global handling | `false` | consistent |
| `node_relationship_remove` | fixed, no global handling | `false` | consistent |

Sites: `core/migrations/query/attribute_add.py::AttributeAddQuery`; `core/migrations/query/node_duplicate.py::NodeDuplicateQuery`; `core/migrations/schema/node_remove.py::NodeRemoveMigrationBaseQuery` and its `NodeRemoveMigrationQueryIn` / `NodeRemoveMigrationQueryOut` subclasses.

**Merge does not repair these** — see User Story 3. Highest severity alongside F1 / F1b, because the owning node already exists on the default branch.

### F7 — Rollback cannot reach globally-published rows, or the metadata they bumped

`core/query/rollback.py::RollbackReopenEdgesQuery` and `::RollbackDeleteEdgesQuery` both match
`(src)-[edge {branch: $target_branch}]->(dst)` — a **single** branch.

A merge into the default branch runs its schema-migration portion there, so `$set_metadata` is true
and the `previous_updated_at` / `previous_updated_by` snapshots **are** written. But when that
migration adds or removes a branch-agnostic field on a branch-aware kind, the rows it writes go to
`-global-`, not to the target branch. A failed-merge rollback therefore never sees them: the edges
are not reversed, and the vertices they bumped are never restored from their snapshots.

The snapshot machinery is present and correct; the rollback simply looks on one branch when the write
spanned two. Highest blast radius in the feature — a partial rollback leaves a state no later write
repairs.

## The Four Live Mismatches (test matrix basis)

Enumerated by walking `core_models` and comparing each field's `branch` against its node's.

| # | Node support | Field support | Live instance |
|---|---|---|---|
| 1 | aware | agnostic (rel) | `BuiltinIPPrefix.resource_pool` |
| 2 | aware | agnostic (attr) | none — needs a test schema; the seed's original case |
| 3 | agnostic | aware (attr) | `CoreReadOnlyRepository.ref`, `.commit` |
| 4 | agnostic | local (attr) | `CoreGenericRepository.internal_status`, `.sync_status`, `CoreRepository.commit` |

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `Node._update` MUST decide whether to write Node vertex metadata from whether any changed field wrote a `branch_level = 1` edge, not from the node's own branch support.
  *Verify:* User Story 2's scenario leaves `updated_at` unchanged; User Story 1's advances it.

- **FR-002**: `_save_metadata` MUST pass the default branch to `NodeUpdateMetadataQuery`, so the existing delete-edge guard excludes both nodes deleted on the default branch and migrated-out twins.
  *Verify:* delete a node on the default branch, change an agnostic field from a pre-delete branch, assert no bump; repeat with a kind-migrated twin present and assert only the active vertex is considered.

- **FR-003**: `NodeCreateAllQuery` MUST gate each Attribute/Relationship vertex's metadata on that field's own `branch_level`, not the node's.
  *Verify:* create mismatch #3 on a branch, assert the aware attribute vertex has no metadata; create mismatch #1 on the default branch, assert the agnostic relationship vertex does.

- **FR-004**: `RelationshipCreateQuery`, `RelationshipDeleteQuery`, and `RelationshipDeleteAllQuery` MUST stamp a peer Node vertex only when that peer has a level-1 active `IS_PART_OF`.
  *Verify:* create an agnostic relationship between two aware nodes that exist only on a branch; assert neither peer's vertex metadata changed.

- **FR-005**: A repair migration MUST recompute metadata on `Node`, `Attribute`, and `Relationship` vertices, restricted to kinds where some field's branch support differs from the node's, in both directions. Dropping m050's `IS NULL` guard handles both the NULLs F6 leaves and the wrong values F1b leaves. The migration MUST report the number of vertices it changed, broken down by vertex label, in its migration result — the only signal an operator has that it did what was expected on their graph.
  *Verify:* SC-002, plus an assertion that the reported counts match the vertices actually changed.

- **FR-006**: `dev/knowledge/backend/database-schema.md` MUST state the level-1-edge invariant in place of *"set only on default/global branches"* in its Node/Attribute/Relationship vertex-property tables, which is the buggy proxy stated as fact. Constitution II requires cross-branch side effects be documented.

- **FR-007**: `attribute_add`, `node_duplicate`, and `node_remove` MUST gate each vertex's metadata write on that vertex's own edge level — the `on_global_branch` / `CASE WHEN ... = $global_branch` decision already computed in Cypher — rather than on the Python-side `set_metadata` scalar. The four consistent migrations keep `set_metadata` unchanged.
  When the gate fires via this edge-level path on a **non-default** branch, the query MUST write `updated_at` / `updated_by` only and MUST NOT write the `previous_updated_at` / `previous_updated_by` snapshot. That snapshot exists solely so a rollback can restore it, and `core/rollback.py::GraphRollbacker` restores it only for default/global target branches — a snapshot written during a user-branch migration can never be consumed, and a later default-branch rollback whose window catches it could restore a stale value as if it were current.
  *Verify:* on a feature branch, add an agnostic attribute to a branch-aware kind; assert the new Attribute vertex has `created_at` / `created_by` set and the Node's `updated_at` advanced, both readable on the default branch, and that `previous_updated_at` / `previous_updated_by` are untouched. A test MUST also pin that a level-2-only migration still writes no metadata.

- **FR-008**: `Node.delete` and `NodeDeleteQuery` MUST decide whether to write Node vertex metadata from whether any deleted field wrote a `branch_level = 1` edge, not from the node's own branch support — the same rule as FR-001, applied to the delete path named in the ticket.
  *Verify:* delete an aware node carrying an agnostic attribute from a feature branch; assert the default-branch `updated_at` advanced. Delete an agnostic node carrying an aware attribute from a feature branch; assert it did not.

- **FR-009**: `GraphRollbacker` MUST reverse the `branch_level = 1` writes a merge made on `-global-`, and MUST restore the `previous_updated_at` / `previous_updated_by` snapshots on the vertices those writes bumped, whenever the rollback's target branch is the default branch. Today both rollback queries match a single `$target_branch`, so rows a merge published globally — and the vertex metadata they bumped — survive the rollback.
  The `-global-` half MUST use exact-timestamp semantics regardless of the caller's rollback scope. `SINCE_TIMESTAMP`'s safety argument is that the merge write-block gives the caller sole ownership of the target branch for the window — and that does not hold for `-global-`, which the write-block leaves open to every branch other than the merge's source and the default branch. Reversing every global write since the timestamp would therefore revert unrelated branches' agnostic-field writes.
  This does **not** contradict FR-007's rule against writing a snapshot on a user branch. FR-007 is about not writing a snapshot no rollback can consume; FR-009 is about consuming one that a default-branch merge already wrote. The two apply to different branches.
  *Verify:* SC-004, plus a pin that an unrelated branch's `-global-` write inside the rollback window survives.

### Key Entities *(include if feature involves data)*

All existing; no new entities.

- **`Node` / `Attribute` / `Relationship` vertices** — carry `created_at/by`, `updated_at/by`, `previous_updated_at/by` properties; the denormalised metadata cache this feature corrects
- **`BranchSupportType`** — `aware` / `local` / `agnostic`; the per-field and per-node setting whose divergence causes every finding
- **The `-global-` branch, and edge `branch_level`** — `1` = default/global, `2` = user branch; `branch_level = 1` is the authoritative visibility test
- **`NodeUpdateMetadataQuery`** — the write path for Node vertex metadata (`core/query/node.py::NodeUpdateMetadataQuery`)
- **`DiffMergeMetadataQuery`** — sets metadata at merge; unchanged by this feature, but its `node_uuids`-from-diff scope is why F6 is not self-healing
- **`m050_backfill_vertex_metadata`** — the existing edge-derived recompute; its derivation is the oracle for both tests and the repair migration
- **`GraphRollbacker`** — reverses a failed merge's writes and restores the `previous_updated_at/by` snapshots; currently scoped to a single branch, which FR-009 widens to include `-global-`

### Edge Cases

- **Node created on a branch, not yet merged** → no bump. Handled for free: `NodeUpdateMetadataQuery` requires an active level-1 `IS_PART_OF`, and `DiffMergeMetadataQuery` sets it at merge.
- **Node deleted on the default branch, agnostic field changed from a pre-delete branch** → no bump (FR-002).
- **Kind/inheritance-migrated twins sharing a UUID, one active and one deleted** → only the active vertex counts (FR-002, F5).
- **Mixed update touching both an aware and an agnostic field on an aware node from a branch** → bump; the agnostic half is visible on the default branch.
- **Agnostic relationship where one peer is on the default branch and the other only on a branch** → stamp exactly one (FR-004).
- **Schema migration on a branch that writes only level-2 edges** → still no metadata (FR-007 regression pin).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (gate): for every cell enumerated below, a default-branch read of `created_at/by` and `updated_at/by` equals the value the edge-derived recompute produces. The recompute is the oracle, so assertions do not hard-code timestamps.

  **Mechanism A — via node save** (`Node._create` / `Node._update` / `Node.delete`): all cells valid.

  | Mismatch | create | update | delete |
  |---|---|---|---|
  | #1 aware node / agnostic rel (`BuiltinIPPrefix.resource_pool`) | default + user | default + user | default + user |
  | #2 aware node / agnostic attr (inline test schema) | default + user | default + user | default + user |
  | #3 agnostic node / aware attr (`CoreReadOnlyRepository.ref`) | default + user | default + user | default + user |
  | #4 agnostic node / local attr (`CoreRepository.commit`) | default + user | default + user | default + user |

  24 cells (4 mismatches × 3 operations × 2 write branches).

  **Mechanism B — via schema migration**: only the three queries FR-007 changes, each against the mismatches it can actually reach, on both write branches.

  | Query | Operation | Mismatches reached | Cells |
  |---|---|---|---|
  | `AttributeAddQuery` | attribute create | #2, #3, #4 — **N/A for #1**, which is a relationship; `attribute_add` never creates one | 6 |
  | `NodeDuplicateQuery` | node kind/inheritance change | #1–#4 | 8 |
  | `NodeRemoveMigrationQuery{In,Out}` | node delete | #1–#4 | 8 |

  22 cells. **N/A across all of mechanism B**: an in-place field-*value* update, which no schema migration performs — value updates reach the graph only through mechanism A.

  Plus the FR-007 regression pin (a migration writing only level-2 edges writes no metadata), which is not a mismatch cell.

  Cells sharing a fixture may share a test; the enumeration defines coverage, not test count.

- **SC-002** (gate): the repair migration is idempotent — a second run changes zero vertices.

- **SC-004** (gate): a merge into the default branch whose schema-migration portion adds — and, separately, removes — a branch-agnostic field on a branch-aware kind, then fails, leaves no trace after rollback: the `-global-` edges it created are reversed, and every vertex whose metadata it bumped equals its pre-merge value, restored from `previous_updated_at` / `previous_updated_by`.

- **SC-003** (check, not gate): no measured regression beyond noise on relationship create/delete. If the peer guard costs anything real, that indicates the wrong design — `RelationshipCreateQuery` already proves a level-1 `IS_PART_OF` in `add_source_match_to_query` when the peer's support branch is level 1, so only the aware-peer case needs an added `OPTIONAL MATCH`.

## Constitution Alignment

- **II. Branch-Safe by Default** — squarely the violated principle: *"Cross-branch side effects (e.g., modifying branch-agnostic nodes) MUST be explicitly documented and tested."* Drives FR-006 and SC-001.
- **IV. Test Discipline** — SC-001's matrix is the coverage this area currently lacks.
- **V. Query Performance & Efficiency** — the cache exists for speed; SC-003 keeps the fix from trading the win away. `EXPLAIN` on the modified relationship queries is the SHOULD here.

## Governance Gates Crossed

- [x] **Database / migration change** — repair migration (FR-005) and the widened rollback scope (FR-009). Approved for this ticket.
- [ ] API change — none; read shapes unchanged.
- [ ] New dependency — none.
- [ ] CI/CD change — none.
- [ ] Auth change — none.

## Assumptions

- Vertex metadata is read only on default/global branches; user-branch reads derive from edges. Verified in code (`core/query/node.py::NodeListGetInfoQuery`, `core/query/node.py::NodeListGetAttributeQuery`, `core/query/subquery.py::build_subquery_order_metadata`), not assumed.
- `DiffMergeMetadataQuery` correctly sets metadata at merge and needs no change — but it only covers nodes in the branch diff, which is why F6 is not self-healing.
- m050's derivation (`max()` over level-1 edge `from` / `to`) is the authoritative recompute for both tests and repair.
- **The repair migration is not reversible, and does not need to be.** Unlike m050, which only filled
  NULLs, it overwrites existing values — that is what fixes the wrong ones F1b leaves. This is safe
  because the properties are a derived cache: the migration never modifies the edges it derives from,
  so the recompute can be re-run at any time from the source of truth. No pre-migration snapshot of
  the properties is kept.
- **m050 sets only `created_at` / `updated_at`, not `created_by` / `updated_by`.** Since SC-001 asserts on the `_by` fields too, the repair migration (FR-005) extends the same derivation to the actor fields by taking the `from_user_id` of the edge that supplied the winning timestamp. This is a completion of m050's rule, not a new requirement.
- The repair migration is `m077`, the next free graph migration number (`m076_heal_missing_attribute_rows` is the highest present on this branch's base). The number must be re-checked before merge, since a migration landing on the base first forces a renumber.
- Resolved from the brief's open question — **an agnostic node's kind/inheritance can be migrated**: `node_duplicate` applies no `branch_support` restriction and explicitly preserves `-global-` edges (`core/migrations/query/node_duplicate.py::NodeDuplicateQuery._render_sub_query_out` / `._render_sub_query_in`). F5 therefore fixes a live bug, not a latent one.
- Resolved from the brief's open question — **the `local`-on-agnostic create/update split is treated as a separate defect**: `get_create_data` downgrades a `LOCAL` attribute on an `AGNOSTIC` node to `-global-` / level 1 (`core/attribute.py::BaseAttribute.get_create_data`) while `get_branch_based_on_support_type` special-cases only `AGNOSTIC` (`core/attribute.py::BaseAttribute.get_branch_based_on_support_type`), so mismatch #4 is created at level 1 and updated at level 2. Whichever behaviour is intended, this feature's rule is edge-derived and therefore correct either way: metadata must match the edges actually written. The value-correctness question is recorded in Out of Scope.
- Resolved from the brief's open question — **`attribute_kind_update`, `attribute_rename`, and `node_relationship_remove` are left alone**: they write no `-global-` edges at all, so their `set_metadata` scalar is self-consistent with the edges they produce. Whether they *should* handle agnostic fields is a data-visibility question, recorded in Out of Scope.

## Out of Scope (v1)

- Aware attributes on agnostic nodes being unreachable on the default branch at all (their `HAS_ATTRIBUTE` edges are level 2). A real smell exposed by F2, but a separate defect about data visibility, not metadata.
- `attribute_add` sends an agnostic attribute's rows to `-global-` while `attribute_remove` writes the deletion at the migration branch's level — added globally, removed locally. Asymmetric, but not a metadata defect.
- The `LOCAL`-on-`AGNOSTIC` create/update split (mismatch #4 created at level 1, updated at level 2), which means the default branch keeps showing the creation-time value. A value-correctness defect wider than IFC-3032; file separately.
- Whether `attribute_kind_update`, `attribute_rename`, and `node_relationship_remove` should handle agnostic fields at all. Applied to an agnostic field they write level-2 edges for data living at level 1, so the change is invisible on the default branch where the data lives. A value-correctness gap wider than IFC-3032; file separately.
- Any change to what the metadata read path returns, or to `order_by` semantics.
- F3's peers-not-on-default over-stamp during merge, which `DiffMergeMetadataQuery` already overwrites.

## Proposed Sub-task Breakdown

Each is intended to be its own commit / PR, ordered so the tests land with the fix they cover.

1. **FR-001 + FR-002 + FR-008** — the `Node._update` and `Node.delete` / `NodeDeleteQuery` gates, and the branch passed to `NodeUpdateMetadataQuery`. All three are the same defect on three paths. Anchor test on F1b (`CoreReadOnlyRepository`) since it needs no custom schema.
2. **FR-007** — the three schema-migration queries. Highest-severity remaining after 1.
3. **FR-003** — `NodeCreateAllQuery` per-field gating.
4. **FR-004** — relationship create/delete peer guard. Staged separately so it can be reverted on perf grounds without touching the rest.
5. **FR-005** — repair migration.
6. **FR-009** — rollback coverage for globally-published merge writes. Separate commit; the only part touching the merge-failure path.
7. **FR-006** — knowledge-doc correction.
