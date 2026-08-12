# Implementation Plan: Inherited-Attribute Migration Fix and Healing Migration

**Branch**: `inherited-attr-migration-ifc-2619` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-2619-inherited-attr-migration/spec.md`; confirmed module decisions from `inherited-attribute-migration-prd.md` and the traced forward-fix analysis `inherited-attribute-migration-plan.md` (repo root).

## Summary

When a node kind newly inherits a generic, pre-existing nodes never get attribute rows for the inherited attributes (#9284). Two deliverables, two PRs, one release:

1. **PR 1 — forward fix**: `NodeKindUpdateMigration` runs a `NodeAttributeAddMigration` (with a new `force_inherited=True` opt-in) per newly-inherited attribute after vertex duplication commits; schema-migration execution becomes two-phase (kind-updates first, everything else second, phase 2 skipped on phase-1 errors) via a pure `split_migrations_by_phase` helper.
2. **PR 2 — healing migration**: new numbered graph migration `m076` (`MigrationRequiringRebase`) detects and backfills every missing (active node, generic-inherited attribute) row — the default branch at upgrade time, every other branch during its post-upgrade rebase — with rows created at run time, run-time NumberPool allocation, strict idempotency, and self-validation that fails the upgrade loudly. *(Redesigned 2026-08-04 — tasks.md Phase 7: schema-graph-driven discovery replaced `SchemaBranch` loads, direct `AttributeAddQuery`/inline pool-row query replaced `NodeAttributeAddMigration` reuse, and the branch pool pass moved to rebase time.)*

Both PRs reference IFC-2619 and MUST land in the same release (spec assumption); PR 2's merge checklist includes verifying PR 1 is in the same release milestone.

## Technical Context

**Language/Version**: Python 3.13 (backend only)

**Primary Dependencies**: Existing Infrahub core — migration framework (`backend/infrahub/core/migrations/`), Neo4j driver 6.0 via `InfrahubDatabase`, Pydantic 2.12. No new dependencies.

**Storage**: Neo4j 2025.10 graph — attribute vertices (`Attribute`, `AttributeValue`, `Boolean`) and their branch/time-scoped edges; schema-graph vertices for timestamp derivation.

**Testing**: pytest 9.0 — unit (`backend/tests/unit/`), component with test DB (`backend/tests/component/core/migrations/`), integration (`backend/tests/integration/schema_lifecycle/`).

**Target Platform**: Infrahub server (Linux); healing runs inside the existing `infrahub upgrade` command — no new CLI surface.

**Project Type**: Backend-only change to an existing web service; no GraphQL/REST/SDK/frontend surface.

**Performance Goals**: Detection and repair batched per kind (FR-011); per-node iteration only for NumberPool allocation; query plans reviewed with `EXPLAIN` during development.

**Constraints**: Healing must be idempotent and a strict no-op on healthy data; migration must self-validate and fail the upgrade on violation; two PRs must land in the same release.

**Scale/Scope**: Healing audits only the kinds the schema graph shows as inheriting from generics (on user branches, only kinds whose `inherit_from` changed on the branch); batching per kind bounds memory and round-trips. Forward fix touches 3 existing modules + tests; healing adds 1 migration module (discovery, detection, and pool-row queries inlined) + tests.

## Constitution Check

*GATE evaluated against Constitution v1.0.0 — pre-Phase-0 and re-checked post-design: PASS (no violations; one governance flag).*

- **I. Schema-Driven Integrity** — PASS. The feature *restores* the schema-as-source-of-truth invariant ("every active node has an active attribute row for every schema-defined attribute"). Migration preserves constraints; no generated files hand-edited.
- **II. Branch-Safe by Default** — PASS. Branch/temporal filters in all queries; branch-scoped healing passes designed and tested explicitly; merge behavior covered by the post-upgrade-merge backstop assumption and existing rollback suite; soft-delete semantics respected (tombstone clamp).
- **III. Type Safety & Explicit Contracts** — PASS. Typed Pydantic migration models; query results via structured `get_data()` patterns; no untyped dicts.
- **IV. Test Discipline** — PASS. Unit test for the one pure function; component tests for all migration behavior against the test DB; integration schema-lifecycle test for the #9284 repro; no mocks of graph behavior.
- **V. Query Performance & Efficiency** — PASS. Parameterized Cypher only; batched per-kind queries; `EXPLAIN` review during development; no N+1 outside the sanctioned NumberPool loop.
- **VI. Security & Input Boundaries** — PASS. No user input; parameter binding throughout; no new endpoints.
- **VII. Simplicity & Maintainability** — PASS with justification. Reuses the acknowledged-ugly migration-within-a-migration pattern rather than inventing a parallel mechanism; refactor deferred to a follow-up issue (documented in Complexity Tracking).

**Governance gate (from AGENTS.md "Ask First")**: this is a database migration change — flagged for maintainer review in both PRs (already recorded in spec Governance Gates).

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2619-inherited-attr-migration/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0 — 11 resolved decisions (R1–R11)
├── data-model.md        # Phase 1 — graph entities and invariants
├── quickstart.md        # Phase 1 — validation guide
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created by plan)
```

No `contracts/` directory: the feature exposes no external interface (no GraphQL, REST, SDK, CLI, or frontend changes — spec Out of Scope). The internal contracts are the migration framework's existing `execute() -> MigrationResult` protocol and the graph invariant documented in data-model.md.

### Source Code (repository root)

```text
backend/infrahub/core/
├── graph/__init__.py                                  # GRAPH_VERSION 74 → 75 (PR 2)
├── migrations/
│   ├── schema/
│   │   ├── node_kind_update.py                        # PR 1: execute() override + _newly_inherited_attributes()
│   │   ├── node_attribute_add.py                      # PR 1: force_inherited field + guard change
│   │   └── tasks.py                                   # PR 1: two-phase batching + split_migrations_by_phase()
│   ├── graph/
│   │   └── m076_heal_missing_attribute_rows.py        # PR 2: MigrationRequiringRebase — discovery + detection +
│   │                                                  #       pool-row queries inlined, orchestration, self-validation
│   └── query/
│       └── attribute_add.py                           # PR 2: uuids parameter + agnostic global-branch edges

backend/tests/
├── unit/core/migrations/schema/test_tasks.py          # PR 1: split_migrations_by_phase (pure)
├── component/core/migrations/
│   ├── schema/test_node_kind_update.py                # PR 1: inherited-attr creation, profiles/templates, gating, NumberPool, name-update no-op
│   ├── schema/test_node_attribute_add.py              # PR 1: force_inherited bypass; default guard intact
│   ├── schema/test_all_migrations_rollback.py         # PR 1: run unchanged
│   ├── graph/test_m076_heal_missing_attribute_rows.py # PR 2: damaged default branch, branch-scoped, tombstone, NumberPool (incl. rebase-time branch pass), healthy no-op, idempotent rerun, self-validation
│   └── graph/test_m075_attribute_heal_detection.py    # PR 2: detection completeness + timestamp derivation
└── integration/schema_lifecycle/
    └── test_schema_add_inherited_generic.py           # PR 1: end-to-end #9284 repro

changelog/
├── 9284.fixed.md                                      # PR 1 towncrier fragment
└── +heal-missing-attribute-rows.fixed.md              # PR 2 towncrier fragment
```

**Structure Decision**: Backend-only, following existing migration-framework layout: schema migrations in `migrations/schema/`, the numbered healing migration in `migrations/graph/`, shared query logic in `migrations/query/`, tests mirroring source structure per Constitution IV.

## Design

### PR 1 — Forward fix

1. **`NodeAttributeAddMigration.force_inherited`** (`node_attribute_add.py`): new `force_inherited: bool = False` field; guard becomes `if self.new_attribute_schema.inherited is True and not self.force_inherited: return MigrationResult()`. Preserves #7407 protection (FR-002); nothing in `core/models.py` changes.

2. **`NodeKindUpdateMigration.execute()` override** (`node_kind_update.py`): call `super().execute()` (commits vertex duplication with the new label set), bail on errors, then for each attribute in `_newly_inherited_attributes()` run a `NodeAttributeAddMigration(force_inherited=True, ...)` with a `SchemaPath` targeting that attribute; accumulate errors/counters, stop on first error. Do **not** hook `execute_post_queries` (nested-transaction failure — research R2). `_newly_inherited_attributes()` = attributes in `new_schema` but not `previous_schema`, filtered to `inherited`, sorted (research R3). Name/namespace updates yield an empty set — no-op preserved. NumberPool allocation and profile/template coverage come free and verified from reusing the full sub-migration (research R4, R5) — satisfies FR-001, FR-004.

   **Partial-failure convergence**: a failure mid-sequence leaves duplication committed and some attribute-adds done; the `schema_path_migrate` retry (retries=3) re-runs the whole migration, where `NodeDuplicateQuery` no-ops via `already_migrated` and completed adds no-op via `AttributeAddQuery`'s existence guard — the rerun converges. Pinned by a dedicated component test (rerun of a partially-completed kind-update).

3. **Two-phase batching** (`tasks.py`): pure `split_migrations_by_phase(migrations)` returns (kind-update-backed, rest) derived from `MIGRATION_MAP`; `schema_apply_migrations` executes phase 1 to completion, skips phase 2 if phase 1 errored (FR-003, FR-012). Extract the existing loop body into a per-batch helper. Sole caller `SchemaUpdateCoordinator` unchanged (research R6).

### PR 2 — Healing migration

4. **Discovery + damage detection** (inlined in the m076 module — single-consumer queries, repo convention): discovery walks the persisted schema graph — `InheritedAttributeDiscoveryQuery` pairs every SchemaNode whose latest active `inherit_from` names a generic with that generic's SchemaAttribute vertices (a `branch_scoped` variant restricts to kinds whose `inherit_from` carries a branch-level update); attribute/node properties are hydrated via `NodeManager.get_many` on the schema-vertex UUIDs, with only the in-memory internal schema + core models registered — **no `SchemaBranch` load anywhere**. `AttributeHealDetectionQuery` is batched per kind (FR-011) and returns (node uuid, attribute name) for every active node lacking an active row — treating tombstone-only as damaged, clamping timestamps to not predate tombstones (FR-005, FR-006; research R8, R9); a `branch_scoped` variant considers only damage involving branch-level data changes (FR-009).

   **Duplicated schema vertices (critique E2)**: schema name/namespace/inheritance updates create same-UUID *copies* of schema nodes, so "when did the kind begin inheriting" is not readable off a single vertex's edges. Timestamp derivation resolves the edge timeline across the full same-UUID vertex set of the schema node and its attribute vertices; the heal timestamp is the **later** of the generic→attribute linkage time and the kind's inherit-began time (the heal floor). Component tests include a kind renamed after gaining inheritance.

5. **`m076_heal_missing_attribute_rows`** (`MigrationRequiringRebase`; `GRAPH_VERSION` → 75; research R7):
   - **`execute()` (upgrade time)**: default branch first — per discovered kind, detect → repair. Default-backed attributes: batched `AttributeAddQuery` calls with explicit `uuids`, written at run time. NumberPool attributes: per-node run-time allocation via the reservation-aware `CoreNumberPool.get_resource`, row written by the inline `PoolAttributeRowAddQuery` (runtime row shape: `is_default: false` value vertex + `HAS_SOURCE` to the pool); a missing pool fails the migration loudly (FR-007; research R10). Every other branch is repaired by its own post-upgrade rebase rather than during the upgrade (FR-009).
   - **`execute_against_branch()` (rebase time)**: run during each branch's post-upgrade rebase (the upgrade marks stale branches for rebase); pool-only branch-scoped discovery → per-node run-time allocation, so branch allocations follow the default branch's; re-validates its own pool scope before returning.
   - **Branch-agnostic attributes**: `AttributeAddQuery` and `PoolAttributeRowAddQuery` write AGNOSTIC-support attribute edges on the global branch (this also fixes the forward path, which shares `AttributeAddQuery`).
   - **Self-validation**: re-run discovery + detection across the upgrade-time scope, excluding deferred branch pool pairs; any remaining pair fails the migration with per-kind actionable errors, failing the upgrade (FR-010, SC-001). All repair queries idempotent → rerun-safe, strict no-op on healthy data (FR-008, SC-003).
   - **Audit trail (critique P1)**: on success, the migration logs per-kind repaired-row counts (default branch and per branch) plus deferred-pool counts; zero-count output on healthy installs doubles as the no-op proof.

6. **Implementation-time verification gate (from spec Assumptions)**: before trusting run-time NumberPool allocations, verify `CoreNumberPool.get_resource`'s uniqueness check is correctly branch- and time-scoped; fix or wrap if not.

### Error handling

- Phase-1 schema-migration errors abort phase 2 (FR-003).
- Healing validation failures surface as upgrade errors with per-kind detail (FR-010).
- Partial-failure recovery via idempotent queries + existing retry policy (`schema_path_migrate` retries=3; migration rerun).

## Testing Strategy

Per spec Testing Decisions and Constitution IV — assert on user-observable graph behavior, never on which migration produced rows:

- **Unit**: `split_migrations_by_phase` only (the one pure function).
- **Component**: kind-update suite (inherited-attr creation incl. profiles/templates, unique/read-only gating, NumberPool allocation + single-pool assertion, name-update no-op, partial-failure rerun converges); attribute-add guard/bypass; m076 suite (damaged default branch, branch-scoped damage, tombstone case, NumberPool case, healthy no-op, idempotent rerun, self-validation failure path, branch predating the damage window correctly sees no attribute); detection-query suite (completeness + timestamp derivation incl. a kind renamed after gaining inheritance). "Zero writes" assertions (SC-003) measure objectively via full-graph snapshot equality — before/after snapshots of every vertex and edge compare equal (strictly stronger than driver write-counter deltas), not implementation internals.
- **Integration**: `test_schema_add_inherited_generic.py` — #9284 end-to-end through the public API (load v1 → create node → load v2 → read non-null `id`, update persists with `is_default: false`, filter matches); existing rollback suite unchanged.
- **E2E (manual/CI)**: quickstart.md walks the issue's two schema files against a live stack, and a damaged-install upgrade.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Migration-within-a-migration (kind-update invoking attribute-add) | Only mechanism that runs after vertex duplication commits without nesting transactions; pattern already established in `node_uniqueness_constraints_update.py` | A standalone "inheritance migration" duplicates the attribute-add implementation wholesale; removing the inherited guard reintroduces #7407. Refactor of the shared pattern is an explicit follow-up issue (spec Out of Scope). |

## Post-Design Constitution Re-Check

PASS — design introduces no new violations; the single justified complexity item is tracked above and its remediation deferred to a follow-up issue per Governance.
