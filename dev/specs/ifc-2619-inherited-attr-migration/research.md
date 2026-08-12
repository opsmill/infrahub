# Research: Inherited-Attribute Migration Fix and Healing Migration

**Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

All unknowns from Technical Context were resolved against the codebase (file:line references verified on branch `inherited-attr-migration-ifc-2619`) and the prior traced analysis in `inherited-attribute-migration-plan.md`.

## R1. Root cause of #9284 (why inherited attributes never materialize)

**Decision**: Fix ownership structurally — `NodeKindUpdateMigration` becomes the owner of "a node just gained inheritance" and runs `NodeAttributeAddMigration` per newly-inherited attribute.

**Rationale** (traced root cause, three interacting gaps):
- `SchemaUpdateValidationResult.process_diff` (`backend/infrahub/core/models.py:187`) only walks `diff.removed` and `diff.changed`. A brand-new generic lands in `diff.added` and emits no migrations at all.
- `GenericSchema._get_field_names_for_diff` (`generic_schema.py:51-54`) drops `used_by`, so an existing generic gaining a new inheritor is not in `diff.changed` either.
- The node-scoped `node.attribute.add` migration returns an empty result for inherited attributes (`node_attribute_add.py:73-74`) — a guard added in `a30f870fd` (#7407) to stop the generic-scoped run and N node-scoped runs racing into duplicate rows. The guard is correct for its case; removing it reintroduces #7407.

**Alternatives considered**:
- *Remove the inherited-attribute guard*: reintroduces the #7407 duplicate-row race. Rejected.
- *Add `used_by` back to the generic's diff fields*: fires generic-scoped migrations on every inheritor change, wrong granularity, and still misses the brand-new-generic (`diff.added`) case. Rejected.
- *Walk `diff.added` in `process_diff`*: turns every new generic into a migration source even when no pre-existing inheritor exists; broader blast radius and still needs the guard bypass. Rejected in the prior analysis in favor of hooking the migration that already owns the label change.

## R2. How the kind-update migration invokes the attribute-add migration

**Decision**: Override `execute()` on `NodeKindUpdateMigration` (never `execute_post_queries`), following the existing migration-within-a-migration pattern from `node_uniqueness_constraints_update.py:47-65`. Sub-migrations get `force_inherited=True`.

**Rationale**: `SchemaMigration.execute` wraps its body in `db.start_transaction()` (`shared.py:169`), and `InfrahubDatabase.start_transaction` returns a new object sharing `_session` whose `__aenter__` calls `session.begin_transaction()` again (`database/__init__.py:237-291`) — nesting fails. `NodeUniquenessConstraintsUpdateMigration` avoids this by overriding `execute()` and never opening its own transaction. `super().execute()` commits vertex duplication first, so sub-migrations see the new label set. Atomicity across steps is lost, but `NodeDuplicateQuery` (`render_match` filters `already_migrated`) and `AttributeAddQuery` (`WHERE ... has_attr_e IS NULL OR has_attr_e.status = "deleted"`, `migrations/query/attribute_add.py:106`) are idempotent, and `schema_path_migrate` retries 3×, so partial failure heals.

**Alternatives considered**: hooking `execute_post_queries` (fails on nested transactions); a new standalone migration kind (parallel implementation, violates Simplicity principle; the refactor of the shared pattern is an explicit follow-up).

## R3. Newly-inherited attribute set derivation

**Decision**: `set(new_schema.attribute_names) - set(previous_schema.attribute_names)`, filtered to `inherited` attributes, sorted for determinism.

**Rationale**: Non-inherited additions already have their own `node.attribute.add` migration (made safe by two-phase ordering). `NodeKindUpdateMigration` also backs `node.name.update`/`node.namespace.update` (`migrations/__init__.py:19-21`); for those the newly-inherited set is empty, so no special-casing is needed (FR from spec: name-update no-op).

## R4. NumberPool correctness on the forward path

**Decision**: Reuse `NodeAttributeAddMigration` wholesale so its `execute_post_queries` (`node_attribute_add.py:77-124`) performs pool upsert + allocation.

**Rationale** (verified): `SchemaNumberPoolUpserter._get_pool_kind` returns the **generic's** kind for inherited attributes (`pools/schema_number_pool_upserter.py:229-238`) — no duplicate pool under the node kind. `CoreNumberPool.get_resource` returns an existing reservation for the same identifier (`core/node/resource_manager/number_pool.py:97-101`) — a later generic-scoped run does not re-allocate. Satisfies FR-004 with no new code.

## R5. Profile and Template instance coverage

**Decision**: No extra work needed — `_get_node_kinds` (`node_attribute_add.py:30-42`) expands target labels to `Profile{kind}` and `Template{kind}`, which are already present on existing profile/template vertices.

**Rationale**: Gating predicates match the schema generators exactly: `check_if_attr_supports_profiles` (`basenode_schema.py:748`) is the same predicate `generate_profile_from_node` uses (`schema_branch.py:2634-2642`); `support_templates` (`attribute_schema.py:88-90`) matches `generate_object_template_from_node` (`schema_branch.py:2937-2938`). `Template{generic}` is generated as a `GenericSchema` (`schema_branch.py:2892-2904`) with no instances — nothing to migrate. Stale `Template{generic}` labels on existing template vertices are a distinct pre-existing gap, explicitly out of scope (follow-up issue).

## R6. Two-phase migration batching

**Decision**: Split `schema_apply_migrations` (`backend/infrahub/core/migrations/schema/tasks.py:28-71`) into two sequential batches: phase 1 = migrations whose `MIGRATION_MAP` entry is `NodeKindUpdateMigration` (derived from the map, not hard-coded); phase 2 = everything else, skipped when phase 1 errored. The split lives in a pure helper `split_migrations_by_phase(migrations) -> tuple[list, list]` (FR-012).

**Rationale**: Today all migrations fan into one `InfrahubBatch()` (`max_concurrent_execution=5`) with no ordering. `NodeDuplicateQuery` creating replacement vertices concurrently with `AttributeAddQuery` can drop an attribute onto a dead vertex — a pre-existing latent race that the forward fix would hit directly in the overlap case (generic gains an attribute *and* a node newly inherits it in one load). `SchemaUpdateCoordinator` (`update_coordinator.py:316-368`) is the sole caller. Case coverage table in `inherited-attribute-migration-plan.md` §2 confirms all five schema-change shapes converge.

**Alternatives considered**: full topological ordering of migrations by dependency (over-engineered for one known dependency edge; YAGNI); serializing the whole batch (loses concurrency for the common case).

## R7. Healing migration vehicle

**Decision**: One new numbered graph migration, `m076` (`GRAPH_VERSION` 75 → 76 in `backend/infrahub/core/graph/__init__.py:1`), built on `MigrationRequiringRebase`: `execute()` repairs the default branch and self-validates at upgrade time, and `execute_against_branch()` repairs each branch during its post-upgrade rebase. *(Revised 2026-08-04 — originally `ArbitraryMigration`, on the assumption that retroactive timestamps would let one upgrade pass repair every branch.)*

**Rationale**: `GraphMigration` runs a fixed query list in a single transaction — too rigid for per-kind batching and run-time NumberPool allocation. `MigrationRequiringRebase` supplies the per-branch entry point the run-time timestamps require, and the upgrade already marks stale branches `NEED_UPGRADE_REBASE`, so the rebase that carries the repair is one the operator performs anyway.

**Alternatives considered**: `ArbitraryMigration` with retroactive timestamps repairing every branch in the upgrade pass (dropped — see R8); continuous background repair job (out of scope per spec).

## R8. Retroactive timestamp derivation (superseded)

**Decision**: Per (kind, attribute), the healed row's timestamp is the later of "the kind began inheriting the generic" and "the generic gained the attribute", read from the schema graph's own vertices (the generic's schema node and its attribute vertices), clamped to never predate an existing tombstone for the same attribute on the same node.

**Rationale**: The schema graph records when schema elements changed per branch — it is the only durable record of when the damage window opened. The tombstone clamp prevents resurrecting history before a deliberate delete (spec edge case).

**Superseded 2026-08-04**: healed rows are created at run time, so no timestamp is derived. Branches receive their repairs by rebasing instead (R7, FR-009). The derivation is kept because it still documents how the damage window is bounded.

**Caveat (critique E2)**: schema name/namespace/inheritance updates create same-UUID copies of schema vertices, so derivation must resolve the edge timeline across the full same-UUID vertex set (UUID for identity, internal vertex id only within a single copy's edges) rather than reading one vertex's edge history.

## R9. Damage-detection query shape

**Decision**: New batched per-kind query (the feature's one deep module): for a given kind and schema-attribute list, find active nodes lacking an active attribute row per attribute — including tombstone-only cases — and derive each pair's retroactive timestamp in the same pass. Branch-scoped variant filters to data changed on the branch.

**Rationale**: FR-011 mandates per-kind batching; per-node iteration is allowed only for NumberPool allocation. Detection doubles as self-validation (run again post-repair, assert zero rows) — resolves the PRD's self-validation open question at zero extra query surface; fallback (scope validation to touched kinds) documented in spec Assumptions.

## R10. NumberPool allocation during healing

**Decision**: Allocate at migration-run time through the reservation-aware path (`CoreNumberPool.get_resource`), not via retroactive default values. Gate on an implementation-time verification that the pool's uniqueness check is branch- and time-scoped correctly (explicit verification task before healing ships).

**Rationale**: A retroactively-timestamped allocation could collide with a reservation made between the retroactive time and now; run-time allocation with the reservation-aware path cannot. This is the resolved form of the PRD's first open question (spec Assumptions).

**Verification (T012, 2026-08-03)**: `CoreNumberPool.get_resource` scoping is correct for migration-run-time allocation on the default branch — no fix or wrapper needed. Evidence:

1. **Idempotency check is correctly branch-scoped.** `NumberPoolGetReserved` (keyed on identifier) uses the branch-aware filter; for the default branch that filter set is `{-global-, <default>}` (`Branch.get_branches_and_times_to_query_global`, `backend/infrahub/core/branch/models.py:269-270`), and reservations are always written on the global branch (`NumberPoolSetReserved` builds `rel_prop` from `registry.get_global_branch()`). A prior reservation for the same identifier is therefore always visible, so a re-run of the migration returns the previously allocated number instead of allocating a new one.
2. **Uniqueness check is correctly branch- and time-scoped.** The free-number search (`NumberPoolGetFree`, also `NumberPoolGetUsed`) runs `branch_agnostic=True`: the filter is `r.from < $at AND (r.to IS NULL OR r.to > $at)` with no branch predicate (`models.py:391-396`), and `at` defaults to query-construction time (`Timestamp(None)` = now) — `get_resource` never forwards a caller-supplied `at` into the read queries. The check therefore sees active reservations from **every** branch as of migration run-time, closing the collision window between the retroactive timestamp and now by construction.
3. **The reservation write is visible everywhere immediately.** `NumberPoolSetReserved` creates the `IS_RESERVED` edge on the global branch with `from = at`; with the migration-run `at`, all branches see it from that moment.

Implementation obligations for m076 (T018), both already demonstrated by the precedent in `backend/infrahub/core/migrations/schema/node_attribute_add.py:109-124`:

- **Initialize the lock registry first.** `get_resource` acquires the pool lock from `lock.registry`, which is not initialized in the CLI migration context — call `initialize_lock()` in the migration, as m031/m038/m039 do.
- **Interleave allocate → write per node inside one transaction.** `NumberPoolGetFree` only counts a value as used when the reserving node's active `HAS_VALUE`/`HAS_ATTRIBUTE` path exists (`n.uuid = res.identifier`); a reserved-but-not-yet-written value looks free to the next allocation. The precedent saves each node inside the same transaction before the next `get_resource` call, so reads observe the transaction's own writes; batching all allocations before any node writes would produce duplicates.
- **Pass the migration-run `at`, not the retroactive timestamp** (FR-007 requires pool-backed rows created at migration-run time). A backdated `at` would only affect the reservation edge's `from` (the uniqueness read still runs at now), but it would fabricate reservation history for time-travel reads.

Pre-existing limitation, out of scope: values inside the pool range set manually (no pool source, hence no `IS_RESERVED` edge) are invisible to `NumberPoolGetFree`. FR-007 only requires non-collision with reservations, and this behavior predates the feature.

## R11. Packaging and sequencing

**Decision**: Two PRs in one release. PR 1: forward fix (kind-update sub-migrations, `force_inherited` bypass, two-phase batching, unit + component + integration tests). PR 2: healing migration m076 + detection query + component tests, reusing PR 1's machinery for repair application.

**Rationale**: PRD packaging decision; PR 2 depends on PR 1's `force_inherited` machinery. Same-release requirement keeps any install from experiencing "new damage stopped, old damage present".
