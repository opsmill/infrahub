# Implementation Plan: Branch-Agnostic Vertex Metadata Correctness

**Branch**: `vertex-metadata-correctness-ifc-3032` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3032-vertex-metadata-correctness/spec.md`

## Summary

The vertex properties `created_at/by` and `updated_at/by` on `:Node`, `:Attribute`, and
`:Relationship` are a denormalised cache of "the latest change visible on the default branch". Seven
write sites decide whether to maintain that cache by asking *"is the owning object's support branch
default/global?"* — a proxy for *"is this edge `branch_level = 1`?"* that is exact only when the
field's branch support equals its node's. Where they differ, the cache goes stale or advances for an
invisible change, silently.

The approach is uniform: **replace each object-level proxy with the edge-level fact the same code
path already computes.** In Python that is the field's own `get_branch_based_on_support_type()`; in
Cypher it is the `on_global_branch` / `CASE WHEN ... = $global_branch` expression the query already
evaluates to place its edges. Nothing new is derived — the fix makes the gate and the edge it guards
read the same value instead of two independently-computed answers to the same question.

Three further pieces follow. A Node vertex is stamped only when the node itself has a level-1 active
`IS_PART_OF`, which also fixes the migrated-twin and deleted-node guards. A repair migration recomputes
the cache for graphs already written wrong, including the NULLs merge can never fill. And the
failed-merge rollback is widened to reach the rows a merge publishes on `-global-`, which it cannot see
today — so a rollback that leaves those rows and their bumped metadata in place stops doing so.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Neo4j 2026.05 (driver 6.2); no new dependencies

**Storage**: Neo4j graph — `:Node` / `:Attribute` / `:Relationship` vertices and their edges

**Testing**: pytest 9.0, component level (`backend/tests/component/`), database-backed via
testcontainers or a running dev database

**Target Platform**: Linux server (Infrahub backend)

**Project Type**: Backend correctness fix in the graph persistence layer

**Performance Goals**: No measured regression beyond noise on relationship create/delete (SC-003).
The cache exists so default-branch metadata reads stay fast; the fix must not trade that away

**Constraints**: No API or read-shape change. No new vertex or edge properties. The repair migration
must be idempotent (SC-002) and must not touch `previous_updated_at/by`

**Scale/Scope**: 10 production code sites across 7 modules, 1 new graph migration, 1 knowledge-doc
correction, and a cross-product test suite over 4 live branch-support mismatches

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design. Both passes clean.*

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Schema-Driven Integrity** | No schema-layer change. The repair migration alters only derived properties, never data or constraints, and reads `branch_support` already persisted on each vertex rather than loading a schema — correct for a graph migration that may run against a database predating current models | PASS |
| **II. Branch-Safe by Default** | The principle this feature restores. FR-009 extends it to the recovery path: a rollback reaching only one of the two branches a merge wrote to is itself branch-unsafe. Every gate becomes an explicit `branch_level` test; edge activity resolution (`branch_level DESC, from DESC, status ASC`) is untouched; soft-delete semantics preserved. FR-006 documents the cross-branch side effect as the principle requires — replacing a statement that is currently wrong | PASS — remediates a violation |
| **III. Type Safety & Explicit Contracts** | New Python is a predicate over existing typed objects. Cypher parameters stay bound (`$param`), never interpolated. The repair migration follows the existing `Query` + frozen-dataclass `get_data()` pattern | PASS |
| **IV. Test Discipline** | SC-001's matrix is the coverage this area lacks. Component level is correct — the invariant is a claim about what a Cypher read returns after a Cypher write, so it cannot be unit-tested, and it spans no services. Existing fixtures reused (`metadata_helpers.py`, the `test_050.py` schemas) per the reuse rule; a new inline schema is added only for mismatch #2, which has no live instance | PASS |
| **V. Query Performance & Efficiency** | SC-003 guards this explicitly. The FR-004 peer guard adds at most one `OPTIONAL MATCH` in the aware-peer case; `RelationshipCreateQuery` already proves a level-1 `IS_PART_OF` for level-1 peers. `EXPLAIN` on the modified relationship queries is required. The repair migration is scoped to mismatched kinds and batched `IN TRANSACTIONS`, matching m050 | PASS |
| **VI. Security & Input Boundaries** | No new input surface. All Cypher parameterised. Metadata is provenance data, and correcting it strengthens the audit trail the Security Standards section requires | PASS |
| **VII. Simplicity & Maintainability** | Every gate reuses a value its own code path already computes; no new abstraction, no helper extracted for a single caller. FR-004 copies the guard shape from `RelationshipUpdatePropertyQuery`, which already does it right, rather than inventing a second pattern. The two value-correctness questions the investigation surfaced are filed as separate defects rather than absorbed into scope | PASS |

**Complexity Tracking**: no violations to justify — the table is omitted.

**Governance gate crossed**: database/migration change (FR-005), explicitly approved for this ticket
in the spec.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3032-vertex-metadata-correctness/
├── spec.md                              # Phase 1 output (/speckit-specify)
├── plan.md                              # This file
├── research.md                          # Phase 0 output — R1..R9
├── data-model.md                        # Phase 1 output
├── quickstart.md                        # Phase 1 output
├── contracts/
│   └── vertex-metadata-invariant.md     # The normative rule + recompute oracle
├── checklists/
│   └── requirements.md
└── tasks.md                             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/core/
├── node/__init__.py                     # FR-001, FR-002 — Node._update gate, _save_metadata branch
├── rollback.py                          # FR-009 — GraphRollbacker reach
├── query/
│   ├── node.py                          # FR-003 — NodeCreateAllQuery per-field gating
│   │                                    # FR-002 — NodeUpdateMetadataQuery delete guard
│   │                                    # FR-008 — NodeDeleteQuery gate
│   ├── rollback.py                      # FR-009 — Reopen/DeleteEdges branch scope
│   └── relationship.py                  # FR-004 — peer guard on Create/Delete/DeleteAll
└── migrations/
    ├── query/
    │   ├── attribute_add.py             # FR-007 — AttributeAddQuery
    │   └── node_duplicate.py            # FR-007 — NodeDuplicateQuery
    ├── schema/
    │   └── node_remove.py               # FR-007 — NodeRemoveMigrationQueryIn / QueryOut
    └── graph/
        └── m077_repair_vertex_metadata.py   # FR-005 — new; re-check the number before merge

backend/tests/component/core/
├── test_vertex_metadata_invariant.py    # SC-001 — the cross-product suite (new)
├── test_relationship_metadata.py        # FR-004
├── migrations/
│   ├── schema/metadata_helpers.py       # extended with the recompute oracle
│   └── graph/                           # FR-005 repair + SC-002 idempotency

dev/knowledge/backend/database-schema.md # FR-006
changelog/                               # Towncrier fragment — REQUIRED (user-visible: wrong timestamps)
```

**Structure Decision**: Backend-only. Every change lands in `backend/infrahub/core/` (the graph
persistence layer) with tests mirroring that structure under `backend/tests/component/core/`. No
frontend, SDK, or API surface is touched; read shapes are unchanged, so no generated files need
regenerating.

## Design

The eight changes, in the dependency order the spec's sub-task breakdown establishes. Full rationale
and rejected alternatives are in [research.md](research.md).

### D1 — `Node._update` gates on the changed fields' edge level (FR-001)

`core/node/__init__.py::Node._update` currently asks the node
(`self.get_branch_based_on_support_type()`). Replace with: stamp the Node vertex when **any** field
recorded on the `NodeChangelog` has `get_branch_based_on_support_type().hierarchy_level == 1`.

This is not a re-derivation. `core/query/attribute.py::AttributeQuery` sets its `$branch_level` from
exactly that call, and every attribute write query stamps its own vertex behind `WHERE $branch_level = 1`.
The relationship side uses `core/relationship/model.py::Relationship.get_branch_based_on_support_type`
identically. So the new gate reads the same value the edges were written with. (research.md R1, R2)

### D1b — `Node.delete` / `NodeDeleteQuery` take the same gate (FR-008)

`core/query/node.py::NodeDeleteQuery` bumps the Node vertex behind
`if self.branch.is_global or self.branch.is_default`, where the branch arrives from `Node.delete`'s
single `self.get_branch_based_on_support_type()` call — textually the same proxy as D1, on the third
path the ticket names. Apply the same rule: stamp when any **deleted** field wrote a level-1 edge.

The per-field deletion edges are already correct — `core/query/attribute.py`'s delete variants guard on
`$branch_level = 1` from the attribute's own support branch, exactly as the update variants do. Only
the node-level gate is wrong. (research.md R11)

### D2 — `_save_metadata` passes the default branch (FR-002)

`core/node/__init__.py::Node._save_metadata` passes `-global-` for agnostic nodes, which sends
`NodeUpdateMetadataQuery`'s delete guard — `OPTIONAL MATCH ... {status: "deleted", branch: $branch}` —
looking on the wrong branch, so both a deleted node and a migrated-out twin can be bumped. Pass the
default branch instead. `NodeUpdateMetadataQuery` accepts default or global and matches on
`branch_level: 1` regardless, so the level-1 semantics are unchanged; only the guard's target moves
to the branch where deletions and migrations are recorded.

This is a live bug, not a latent one: `core/migrations/query/node_duplicate.py::NodeDuplicateQuery`
applies no `branch_support` restriction and explicitly preserves `-global-` edges, so agnostic nodes
can be kind-migrated and do produce twins. (spec Assumptions; research.md R4)

### D3 — Three migration queries gate on their own edge level (FR-007)

Each query already computes, in Cypher, the branch its edges go to. Reuse that expression as the
gate, OR-ed with the existing `$set_metadata` scalar so default-branch behaviour is bit-for-bit
unchanged. The four consistent migrations keep `set_metadata` as-is.

- **`AttributeAddQuery`** — gate the Attribute vertex on `$set_metadata OR on_global_branch`. Gate the
  Node vertex on that **and** the node's own `is_part_of_e.branch_level = 1`, so a node that exists
  only on a branch is not stamped. Both `on_global_branch` and `is_part_of_e` are currently dropped
  from the `WITH` preceding the metadata `CALL` and must be carried through.
- **`NodeDuplicateQuery`** — gate on whether the node's own `IS_PART_OF` edge is on `-global-`, which
  is what decides the level of the `IS_PART_OF` the migration creates. The existing `CALL (node)`
  subquery returns only `node` and `is_active`; it must also return the matched edge. Gating on the
  matched edge's *level* would be wrong for aware nodes — an aware node's `IS_PART_OF` resolves to
  the level-1 edge on the default branch while the migration writes its new edges at level 2.
- **`NodeRemoveMigrationQueryIn` / `QueryOut`** — gate on `new_branch_level = 1` from the existing
  `_branch_from_existing` helper. This needs a **reordering**: the metadata `CALL` currently runs
  before the `WITH` that computes `new_branch_level`, so that `WITH` moves above it.

**The snapshot half of each write is not carried across.** Each of these `CALL` blocks currently
writes two things: the `updated_at` / `updated_by` bump, and a `previous_updated_at` /
`previous_updated_by` snapshot for rollback. Only the bump follows the new edge-level gate. When the
gate fires on a non-default branch the snapshot MUST be skipped, because
`core/rollback.py::GraphRollbacker` restores snapshots only for default/global target branches — it
raises outright if asked to restore for a user branch. A snapshot written during a user-branch
migration can therefore never be consumed, and a later default/global rollback whose window catches
it could restore a stale value as if it were current. Concretely: the `previous_*` `SET`s stay behind
`$set_metadata`, while the `updated_*` `SET`s move behind `$set_metadata OR <edge-level fact>`.

(research.md R4)

### D4 — `NodeCreateAllQuery` gates per field (FR-003)

`core/query/node.py::NodeCreateAllQuery.query_init` builds `attr_vertex_prop_str` and
`rel_vertex_prop_str` behind a single `if self.branch.is_default or self.branch.is_global`, while the
edges beside them come from the per-field branch that
`core/attribute.py::BaseAttribute.get_create_data` already resolved. Move the metadata properties
into the per-field data so each vertex is stamped iff its own `branch_level` is 1.

Note the deliberate asymmetry with D1: this gate mirrors the **create** path
(`get_create_data`, which downgrades `local`-on-`agnostic` to level 1), while D1 mirrors the
**update** path (`get_branch_based_on_support_type`, which does not). The two paths genuinely
disagree for mismatch #4; each gate follows the edges its own path writes, so the metadata is correct
under either resolution of that separate defect. (research.md R3)

### D5 — Relationship peer guard (FR-004)

`RelationshipCreateQuery`, `RelationshipDeleteQuery`, and `RelationshipDeleteAllQuery` issue a bare
`SET s.updated_at` / `SET d.updated_at` under `if self.branch.is_default or self.branch.is_global`.
Adopt the guard already in `core/query/relationship.py::RelationshipUpdatePropertyQuery`: require a
level-1 active `IS_RELATED` **and** a level-1 active `IS_PART_OF` on the peer being stamped.

Only the **peer Node** stamps change. These queries also stamp the Relationship vertex `rl` itself,
and that stamp is already correct — the relationship's own branch level is the right gate for the
relationship's own vertex. Applying the peer guard to `rl` would reintroduce an under-set.

Staged as its own commit so it can be reverted on performance grounds without disturbing D1–D4. Along
with D4, this is the part of the feature that closes a latent/low-severity finding rather than an
observable one; both are independently droppable if the schedule tightens, without weakening D1, D2,
D3 or D6. (research.md R8)

### D6 — Repair migration (FR-005)

A new graph migration applying the recompute in
[contracts/vertex-metadata-invariant.md](contracts/vertex-metadata-invariant.md) — m050's derivation
with the `IS NULL` guard dropped, so it corrects wrong values as well as filling NULLs, and extended
to `created_by` / `updated_by`, which m050 never set. Since SC-001 asserts on the actor fields, the
repair must set them; edges already carry `from_user_id` / `to_user_id`, so no new data is needed.

Scoped by `field.branch_support <> n.branch_support`, read from properties already stored on the
vertices — no schema load, which matters because graph migrations may run against a database older
than the current models. The filter is a slight superset (it also matches consistent
`local`-on-`aware` pairs, where the recompute is a no-op), which is safe and avoids encoding the
support lattice in Cypher.

Per the contract's scope rule, `:Node` targets are restricted to vertices holding an active level-1
`IS_PART_OF`, so migrated-out twins and nodes deleted on the default branch are left alone — while
`created_at` still takes its uuid-wide `min()`, which is what lets the surviving twin report the true
creation time.

Idempotent by construction: a pure function of edges the migration does not modify, and it does not
touch `previous_updated_at/by` — snapshotting those would make a second run report changes and would
also corrupt the merge-rollback pair that owns them. Ordering follows m050: Attribute, then
Relationship, then Node (whose `updated_at` derives from the field vertices). Batched
`IN TRANSACTIONS`. The migration is `m077` — `m076_heal_missing_attribute_rows` is the highest present
on this branch's base. Re-check before merge: a migration landing on the base first forces a renumber.

**Destructive, and deliberately not reversible.** m050 was purely additive — its `IS NULL` guard meant
it could only fill blanks. Dropping that guard is what fixes the wrong values F1b leaves, and it makes
this migration an overwrite of existing data with no pre-migration snapshot. That is acceptable for one
specific reason, which must be stated rather than assumed: the properties are a **derived cache**, and
the migration never modifies the edges it derives from. The source of truth is untouched, so the
recompute can be re-run at any time. Keeping a snapshot would buy nothing a re-run does not.

**Reports what it changed.** The migration returns the count of vertices it altered, per vertex label.
This is the only signal an operator gets that it did the expected thing on their graph, and it is what
makes SC-002's "zero changes on the second run" observable rather than inferred.

**Cost model.** Unlike m050, whose `IS NULL` guard made it shrink monotonically across runs, this
migration's cost is proportional to the *mismatched-support population*, not to the remaining damage —
every run examines the same set. The `branch_support <> ` scoping is therefore load-bearing for
runtime as well as for blast radius. (research.md R5, R6, R7)

### D6b — Rollback reaches globally-published merge writes (FR-009)

`core/query/rollback.py::RollbackReopenEdgesQuery` and `::RollbackDeleteEdgesQuery` both open with
`MATCH (src)-[edge {branch: $target_branch}]->(dst)`. Widen that to the target branch **plus**
`-global-`, and only when the target is the default branch.

Nothing else moves: the timestamp window, the `RollbackScope` operator, the two-pass reopen-then-delete
ordering, and `_render_restore_metadata_pipeline` all stay as they are. The safety argument is the
guard that already exists — `core/rollback.py::GraphRollbacker.rollback` raises unless the target is
default or global, so `-global-` is only ever added in exactly the case where a merge could have made
level-1 global writes.

**The `-global-` half takes `AT_TIMESTAMP` semantics regardless of the caller's scope.** Both real
callers (`core/merge/failure_recoverer.py`, `core/diff/merger/merger.py`) pass
`RollbackScope.SINCE_TIMESTAMP`, whose documented safety argument is that the merge write-block gives
the caller sole ownership of the target branch for the window. That argument does not transfer:
`core/branch/status_checker.py::BranchStatusChecker._raise_if_blocked` blocks only the merge's source
branch and the default branch, so any *other* branch may write during the merge window — and an
agnostic-field write from such a branch lands on `-global-` at level 1. Reversing every global write
since the timestamp would revert it. An exact match on the merge timestamp reaches the merge's own
global writes and nobody else's.

This rests on the merge's schema-migration portion stamping its global writes at the merge timestamp.
**Verify that before writing the query**; if it does not hold, FR-009's scope needs revisiting rather
than the query being widened anyway.

The widened `MATCH` scans two branches' edges rather than one. It is bounded by the same timestamp
window and runs only on the merge-failure recovery path, which is not hot — noted, not gated.

This is the piece that makes the `previous_updated_at/by` snapshots useful rather than decorative. A
merge into the default branch already writes them for globally-published rows; until now nothing could
consume them. Note the deliberate pairing with D3: FR-007 stops a *user-branch* migration writing a
snapshot no rollback can consume, while FR-009 makes a *default-branch* merge's snapshot reachable.
Different branches, no conflict. (research.md R10)

### D7 — Knowledge-doc correction (FR-006)

`dev/knowledge/backend/database-schema.md` describes these properties as *"When added to
default/global branch"* / *"When last updated on default/global branch"* — the buggy proxy stated as
fact, and the likely origin of every site that implements it. Replace with the level-1-edge
invariant. Constitution II requires cross-branch side effects be documented; documenting them wrongly
is what propagated the defect.

### D8 — Test suite (SC-001, SC-002)

A cross-product suite asserting against the recompute rather than hard-coded timestamps, so the
oracle is shared with D6 and a drift in either shows up as a failure in both.

Axes: the four live mismatches × {create, update, delete} × {write on default branch, write on user
branch} × {via node save, via schema migration}. The migration axis covers only the three queries D3
touches. Mismatch #2 has no live instance and needs an inline test schema — permitted under
Constitution IV, since no fixture supplies an aware kind with an agnostic attribute; follow the
schema pattern in `backend/tests/component/core/migrations/graph/test_050.py`.

Regression pins, from the spec's edge cases: a migration writing only level-2 edges still writes no
metadata; a node deleted on the default branch is not bumped from a pre-delete branch; only the
active twin of a migrated pair is considered; an agnostic relationship with one peer off the default
branch stamps exactly one peer.

Reuse `backend/tests/component/core/migrations/schema/metadata_helpers.py` (`VertexMetadata`,
`get_node_vertex_metadata`, `get_attribute_vertex_metadata`), extending it with the recompute helper.

Two specifics the helpers force:

- `get_node_vertex_metadata` asserts **exactly one** Node vertex per uuid and tells callers that
  duplicate-node scenarios must disambiguate themselves. FR-002's twin pin is exactly such a scenario,
  so it needs a twin-aware helper added alongside — not a one-off query at the call site.
- D3's `node_remove` reorder moves a metadata write across a `WITH` boundary. It gets no new
  assertions; its regression pin is that the existing
  `backend/tests/component/core/migrations/schema/` suite passes unchanged. The reorder is not done
  until that suite is green.

FR-007's snapshot rule needs its own assertion: after a user-branch migration writes global rows,
`previous_updated_at` / `previous_updated_by` on the affected vertices must be untouched.

FR-008 adds the delete cells to SC-001's Mechanism A, which the enumeration already counts.

FR-009 (SC-004) is tested where the rollback already is —
`backend/tests/component/core/test_rollback.py` for the widened branch scope and
`backend/tests/component/core/merge/test_recovery_rollback.py` for the end-to-end failed-merge
scenario — not in the vertex metadata suite. Two scenarios: a merge whose schema portion adds an agnostic field to an aware kind
and fails, and the same removing one. Plus the over-reach pin: an unrelated concurrent `-global-`
write inside the rollback window must survive an `AT_TIMESTAMP` rollback.
(research.md R9)

## Risks

| Risk | Mitigation |
|---|---|
| The repair migration changes values that are currently correct, because m050's `Node.updated_at` derivation (max over field vertices) is not identical to what the write path produces in every case | Scope the sweep to mismatched kinds via `branch_support`, exactly as FR-005 requires. This bounds the blast radius to the vertices the defect could have touched |
| D3's `node_remove` reordering moves a metadata write across a `WITH` boundary and could change which rows reach it | The reorder only hoists a pure `WITH` that computes two scalars from an already-bound edge; no `MATCH` or filter moves. Covered by the existing `backend/tests/component/core/migrations/schema/` suite plus the D8 pins |
| The FR-004 peer guard costs measurable time on relationship create/delete | SC-003 measures it. `RelationshipCreateQuery` already proves a level-1 `IS_PART_OF` for level-1 peers, so only the aware-peer case adds an `OPTIONAL MATCH`. A real regression means the guard is in the wrong place — staged as its own commit so it can be reverted alone |
| FR-007 causes user-branch migrations to write vertex metadata, which `core/rollback.py::GraphRollbacker` documents as happening only for default/global operations — leaving `previous_*` snapshots no rollback can consume | D3 carries only the `updated_*` bump across the new gate and leaves the `previous_*` snapshot behind `$set_metadata`. Asserted directly in D8 |
| Widening the rollback's branch `MATCH` reverts global writes made by branches unrelated to the merge — a real hazard, since the merge write-block covers only the source and default branches, leaving every other branch free to write to `-global-` during the window | The `-global-` half uses exact-timestamp semantics regardless of the caller's `RollbackScope`, so it reaches only writes stamped at the merge timestamp. Contingent on the merge stamping its global writes at that timestamp — verified before the query is written. Pinned by a test asserting an unrelated branch's concurrent global write in the window survives |
| The two value-correctness defects surfaced during investigation (the `local`-on-`agnostic` create/update split; the three migrations with no `-global-` handling) get absorbed into this ticket | Both are in the spec's Out of Scope with the reasoning recorded. Each gate here is edge-derived, so the metadata stays correct under either resolution. File them as separate issues |

## Phase Outputs

- **Phase 0** — [research.md](research.md): R1–R9, all unknowns resolved from the code; no
  NEEDS CLARIFICATION remains
- **Phase 1** — [data-model.md](data-model.md),
  [contracts/vertex-metadata-invariant.md](contracts/vertex-metadata-invariant.md),
  [quickstart.md](quickstart.md); agent context updated
- **Phase 2** — `tasks.md`, generated by `/speckit-tasks` (not by this command)
