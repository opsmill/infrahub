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

**Decision**: One new numbered graph migration, `m075` (next free slot; `GRAPH_VERSION` 74 → 75 in `backend/infrahub/core/graph/__init__.py:1`), built on `ArbitraryMigration` (`migrations/shared.py:284-286`) for free-form orchestration: repair default branch, then iterate existing branches with branch-scoped detection, then self-validate.

**Rationale**: `GraphMigration` runs a fixed query list in a single transaction — too rigid for per-kind batching + per-branch passes + run-time NumberPool allocation. `ArbitraryMigration` is the established escape hatch (precedents: m015, m016, m028, m029, m032). `MigrationRequiringRebase` is explicitly wrong: the PRD requires repair **without** rebase.

**Alternatives considered**: `MigrationRequiringRebase` (assumes rebased branches — contradicts FR-009); continuous background repair job (out of scope per spec).

## R8. Retroactive timestamp derivation

**Decision**: Per (kind, attribute), the healed row's timestamp is the later of "the kind began inheriting the generic" and "the generic gained the attribute", read from the schema graph's own vertices (the generic's schema node and its attribute vertices), clamped to never predate an existing tombstone for the same attribute on the same node.

**Rationale**: The schema graph records when schema elements changed per branch — it is the only durable record of when the damage window opened. Retroactive timestamps are the mechanism that makes default-branch repairs visible to pre-existing branches without rebase (spec assumption; SC-004). The tombstone clamp prevents resurrecting history before a deliberate delete (spec edge case).

## R9. Damage-detection query shape

**Decision**: New batched per-kind query (the feature's one deep module): for a given kind and schema-attribute list, find active nodes lacking an active attribute row per attribute — including tombstone-only cases — and derive each pair's retroactive timestamp in the same pass. Branch-scoped variant filters to data changed on the branch.

**Rationale**: FR-011 mandates per-kind batching; per-node iteration is allowed only for NumberPool allocation. Detection doubles as self-validation (run again post-repair, assert zero rows) — resolves the PRD's self-validation open question at zero extra query surface; fallback (scope validation to touched kinds) documented in spec Assumptions.

## R10. NumberPool allocation during healing

**Decision**: Allocate at migration-run time through the reservation-aware path (`CoreNumberPool.get_resource`), not via retroactive default values. Gate on an implementation-time verification that the pool's uniqueness check is branch- and time-scoped correctly (explicit verification task before healing ships).

**Rationale**: A retroactively-timestamped allocation could collide with a reservation made between the retroactive time and now; run-time allocation with the reservation-aware path cannot. This is the resolved form of the PRD's first open question (spec Assumptions).

## R11. Packaging and sequencing

**Decision**: Two PRs in one release. PR 1: forward fix (kind-update sub-migrations, `force_inherited` bypass, two-phase batching, unit + component + integration tests). PR 2: healing migration m075 + detection query + component tests, reusing PR 1's machinery for repair application.

**Rationale**: PRD packaging decision; PR 2 depends on PR 1's `force_inherited` machinery. Same-release requirement keeps any install from experiencing "new damage stopped, old damage present".
