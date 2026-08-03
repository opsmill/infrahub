---
description: "Task list for Selective Recompute of Transform-Based Computed Attributes (IFC-2804)"
---

# Tasks: Selective Recompute of Transform-Based Computed Attributes

**Input**: Design documents from `/specs/ifc-2804-selective-recompute/`

**Prerequisites**: plan.md, spec.md, research.md, contracts/trigger-and-recompute.md

**Tests**: Included. The spec (SC-001..SC-012), plan (Testing Strategy), and contracts explicitly require unit tests (the transform->attributes resolver; the three trigger match shapes; the commit trigger removed from the builtin set) and integration tests (the six user stories plus the SC-010 data-path regression, the SC-011 UUID case, the SC-012 single-fire case, and the merge/rebase + recompute-write no-double-fire cases).

**Organization**: Tasks are grouped by phase, and within implementation by the setup -> tests -> core -> integration ordering the templates use. User-story slices are called out with their `[US#]` labels. Priority order from spec.md: US1 (P1), US2 (P1), US3 (P1), US4 (P2), US5 (P2), US6 (P2). The MVP is US1 + US2 (the reported defect and its scoped-recompute fix).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1-US6); unlabelled tasks are shared/cross-cutting
- All paths are repository-root relative

## Conventions (from AGENTS.md / research.md / .agents/rules)

- No DB schema, migration, enum, GraphQL, or REST change: the `fingerprint` attribute already exists (IFC-2844). No offline regeneration task is required, and `uv run invoke docs.validate` is expected to stay green.
- The recompute fan-out (`trigger_update_python_computed_attributes`) and the per-node compute (`process_transform_for_node`) are reused unchanged; only the entry point that decides *which* attributes to recompute is replaced.
- No Jira/spec/FR IDs in source comments, docstrings, or test names (repo convention); those live only in the commit message, PR body, and the changelog fragment.
- No mocks: the resolver is pure (schema-branch lookup), trigger shapes are asserted directly on the `EventTrigger` objects, and integration observes recompute via the node value and/or the recorded submitted workflows through the workflow test adapter (`backend/tests/adapters/workflow.py`).
- The over-regenerate-never-under-regenerate invariant governs every fallback: null fingerprint, no-watch, empty/ambiguous resolution all default toward recompute.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the no-schema-change baseline and create the new test/source skeletons.

- [ ] T001 Confirm no schema/generated-file change is needed: verify the `fingerprint` attribute already exists on `CoreTransformPython` (via `CoreTransformation`) and that this feature adds no attribute, enum, migration, GraphQL, or REST change. Record that the offline regeneration tasks (`backend.generate`, `schema.generate-*`, `pnpm codegen`) are NOT required for this feature. (FR-007, out-of-scope IFC-2844 fingerprint storage.)
- [ ] T002 [P] Trace the importer's Python-transform create-vs-update branch in `backend/infrahub/git/integrator.py` (around `import_python_transforms` / `update_python_transform`, ~lines 1772/1782/1806) to confirm each transform is written exactly once per import (create XOR update, never a create AND a separate fingerprint update in the same import). Record the finding in a comment on this task; if both writes can occur in one import, flag that the lifecycle flow must dedupe. De-risks FR-015 / SC-012 (exactly one recompute on first import).
- [ ] T003 [P] Create the new integration test package `backend/tests/integration/computed_attribute/` with an empty `__init__.py`.
- [ ] T004 [P] Create the changelog fragment `changelog/+ifc-2804.changed.md` describing the behaviour change (commit-driven full-sweep recompute replaced by transform-lifecycle, fingerprint-scoped recompute), the one-time first-import recompute cost per transform (FR-021/FR-022), and the deferred API-query-edit limitation (FR-020).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure resolver and the lifecycle flow must exist before the triggers can be wired to it, and the triggers must be swapped in the catalogues before any end-to-end behaviour can be observed.

**⚠️ CRITICAL**: No user story integration work can pass until this phase is complete.

### Core resolver (FR-010, the name-or-id rule)

- [ ] T005 Implement the pure transform->attributes resolver in `backend/infrahub/computed_attribute/recompute_resolution.py`: given `(branch, transform name AND id)`, resolve to `list[PythonDefinition]` via `schema_branch.computed_attributes.python_attributes_by_transform` (`core/schema/schema_branch_computed/facade.py:56`). Look up by BOTH name and id (`mapping.get(name) or mapping.get(id)`), handle name-or-id wiring (FR-010), return the empty set cheaply with NO node fetch when the transform feeds no attribute (FR-010 / "transform feeding no computed attribute" edge case), and default toward recompute (log loudly) on an ambiguous-empty state (FR-010/FR-017 invariant). Single pure entry point, unit-testable without a stack. (FR-009, FR-010.)

### Core lifecycle flow (FR-002/FR-003/FR-005/FR-006)

- [ ] T006 Implement the transform-lifecycle flow `process_transform_lifecycle` in `backend/infrahub/computed_attribute/tasks.py` with its two duties (depends on T005):
  (a) **recompute fan-out** on create and update-of-fingerprint: resolve the transform to its attributes (T005 resolver) and submit the existing `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` (`workflows/catalogue.py:414`, flow at `tasks.py:221`) once per `PythonDefinition`, threading `context` into BOTH `submit_workflow(context=...)` and `parameters["context"]` per contract section 4;
  (b) **node-input automation reconciliation** on EVERY lifecycle event (create/update/delete): run `setup_triggers(..., TriggerType.COMPUTED_ATTR_PYTHON)` and `setup_triggers(..., TriggerType.COMPUTED_ATTR_PYTHON_QUERY)` built from `gather_trigger_computed_attribute_python` (`computed_attribute/gather.py`), reusing the schema path's reconciliation so a transform-only import never leaves the node-input automations unbuilt and a delete drops the gone transform's automation via `to_delete = existing - desired`. Delete does duty (b) only, not (a). (FR-002, FR-003, FR-004, FR-005, FR-006, FR-011 the reconciliation-preservation fix.)
- [ ] T007 Register the new flow in `backend/infrahub/workflows/catalogue.py`: add a `WorkflowDefinition` (e.g. `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM_LIFECYCLE`) pointing at `infrahub.computed_attribute.tasks:process_transform_lifecycle`, and add it to the workflow list. (Depends on T006.)

### Trigger set swap (FR-001/FR-008/FR-011/FR-012/FR-013)

- [ ] T008 In `backend/infrahub/computed_attribute/triggers.py`, ADD three static `BuiltinTriggerDefinition`s on the `CoreTransformPython` lifecycle, all firing `process_transform_lifecycle` (depends on T007), per contract section 1:
  - **created**: `events={NodeCreatedEvent.event_name}`, `match={kind: CoreTransformPython, NODE_ORIGIN_LABEL: LIVE}`, no `match_related` (create is itself the first-compute signal, FR-002);
  - **updated**: `events={NodeUpdatedEvent.event_name}`, same `match`, `match_related={"prefect.resource.role": ["infrahub.node.attribute_update"], "infrahub.field.name": ["fingerprint"]}` (FR-008 fingerprint-only);
  - **deleted**: `events={NodeDeletedEvent.event_name}`, same `match`, no `match_related`.
  Thread `branch_name`, transform `id`, and `context` into parameters via `jinja_parameter` / the `__prefect_kind: json` context wrapper, matching the existing triggers. (FR-001, FR-008, FR-012 origin=LIVE, FR-013 kind+field guard.)
- [ ] T009 REMOVE `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` from `backend/infrahub/computed_attribute/triggers.py` (its `CommitUpdatedEvent` -> `COMPUTED_ATTRIBUTE_SETUP_PYTHON` definition) and drop the now-unused `CommitUpdatedEvent` import if nothing else uses it. Keep `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` untouched. (Depends on T008 so the replacement exists first.) (FR-011.)
- [ ] T010 In `backend/infrahub/trigger/catalogue.py`, REMOVE `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` from the import block and from `builtin_triggers`, and ADD the three new lifecycle trigger definitions to both. (Depends on T008, T009.) (FR-001, FR-011.)
- [ ] T011 Confirm the untouched paths stay intact: the schema path (`TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` -> `computed_attribute_setup_python`) still reconciles + scoped-recomputes on schema change, and the coalesced merge/rebase recompute (`core/merge/recompute_coalescing`, driven from `post_merge.py` / `branch/tasks.py`) is not modified. Grep-verify `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` has zero remaining references. (FR-011, FR-012, Decision 8.)

**Checkpoint**: Resolver + lifecycle flow exist, the flow is registered, the three lifecycle triggers replace the commit trigger in both catalogues, and the schema / merge-rebase paths are confirmed untouched. User story tests can now run.

---

## Phase 3: Unit tests (pure resolver + trigger shapes)

**Purpose**: Prove the resolver and the trigger definitions without a stack. Write these to FAIL before the Phase 2 implementation is wired, then make them pass.

- [ ] T012 [P] Unit test the resolver in `backend/tests/unit/computed_attribute/test_recompute_resolution.py`: a transform feeding ONE attribute resolves to exactly that `PythonDefinition`; feeding MANY resolves to all and only those; feeding ZERO resolves to `[]`; a computed attribute wiring its transform by UUID (not name) resolves to the same attribute(s) as the name-wired case; and the empty path returns before any node fetch (no `client.all`). No stack, no mocks. (FR-009, FR-010, SC-002, SC-011, SC-010 cheap-empty.)
- [ ] T013 [P] Extend `backend/tests/unit/computed_attribute/test_triggers.py`: assert the three new `BuiltinTriggerDefinition`s have the expected `events`, `match` (kind + origin=LIVE), and `match_related` (role + `field.name == ["fingerprint"]` on update only; absent on create/delete); and assert `TRIGGER_COMPUTED_ATTRIBUTE_PYTHON_SETUP_COMMIT` is gone and no longer present in `builtin_triggers`. (FR-001, FR-008, FR-011, FR-012, FR-013, SC-006.)

**Checkpoint**: The resolver and trigger shapes are locked by unit tests, including the commit-trigger-removal assertion.

---

## Phase 4: User Story 1 - An unrelated commit triggers no recompute (Priority: P1) 🎯 MVP

**Goal**: A commit that touches nothing feeding a watch-declared transform produces zero recompute jobs for its attribute(s).

**Independent Test**: Import a repo with a watch-declared Python transform computed attribute; commit and import an unrelated-file change; assert the transform fingerprint is unchanged and no fan-out is submitted for its attribute.

- [ ] T014 [US1] Integration test in `backend/tests/integration/computed_attribute/test_selective_recompute.py` (mirror `backend/tests/integration/git/fingerprint_base.py`; observe recompute via the node value and/or recorded submitted workflows through the workflow adapter): import a watch-declared transform (attribute populated on create), then commit+import a change to an unrelated file; assert the transform fingerprint is unchanged, no update event fires, and no `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` is submitted for the attribute. (FR-007, FR-011, SC-001, US1.)

**Checkpoint**: An unrelated commit no longer recomputes transform-based attributes.

---

## Phase 5: User Story 2 - A transform change recomputes only the attributes it feeds (Priority: P1) 🎯 MVP

**Goal**: Changing one transform recomputes exactly the attribute(s) it feeds, across all nodes of each attribute's kind; other transforms' attributes are untouched.

**Independent Test**: Two transforms A, B feeding two attributes; change an input of A; import; assert A's attribute is recomputed for all nodes of its kind and B's attribute is not recomputed at all.

**Depends on**: Foundational (resolver + lifecycle flow + update trigger).

- [ ] T015 [US2] Integration test in `test_selective_recompute.py`: two transforms A and B feeding two different computed attributes; change A's connected query (or a closure file / own source / output-affecting manifest field), import; assert A's fingerprint changes, one update fires, A's attribute recomputes for every node of its kind, and B's attribute is not recomputed. Also cover a transform feeding more than one attribute -> every attribute it feeds recomputes, none outside the set. (FR-003, FR-004, FR-009, SC-002, SC-003, SC-005, US2.)

**Checkpoint (MVP)**: US1 + US2 deliver the core value — unrelated commits are inert, and a transform change recomputes only its own attributes across all nodes.

---

## Phase 6: User Story 3 - An edit followed by its revert triggers no recompute (Priority: P1)

**Goal**: An edit then an exact revert nets zero: the reverted content hashes back to the original fingerprint, so the revert import fires no recompute.

**Independent Test**: Import (fingerprint stored), edit + import (one recompute), revert to identical bytes + import; assert the fingerprint returns to the original and the revert import produces no recompute.

- [ ] T016 [US3] Integration test in `test_selective_recompute.py`: import a transform, edit its content and import (assert one recompute), then revert to identical bytes and import; assert the fingerprint equals the original, no update event fires for the revert, and no fan-out is submitted for its attribute on the revert import. (FR-007, SC-004, US3.)

**Checkpoint**: The change signal is proven content-based, not commit-based.

---

## Phase 7: User Story 4 - A no-watch transform keeps per-commit recompute, scoped (Priority: P2)

**Goal**: A no-watch transform (commit id folded into its fingerprint) recomputes on every commit, but scoped to only its own attribute(s), never fanning out to unrelated attributes.

**Independent Test**: A no-watch transform A and a watch-declared, unaffected transform B; import an unrelated commit; assert A's attribute recomputes (safe per-commit default) while B's attribute does not.

**Depends on**: Foundational (update trigger + scoped resolution).

- [ ] T017 [US4] Integration test in `test_selective_recompute.py`: no-watch transform A + watch-declared transform B on the same branch; commit an unrelated change and import; assert A's fingerprint changes (commit id folded in), A's attribute recomputes, and B's attribute is not recomputed. (FR-016, FR-017, SC-009, US4.)

**Checkpoint**: No-watch transforms are never starved and never over-reach.

---

## Phase 8: User Story 5 - Deleting a transform stops its recompute and reconciles away its node-input automations (Priority: P2)

**Goal**: After a delete, no recompute fires for the attribute(s) it fed AND the node-input recompute automation tied to it is gone.

**Independent Test**: Import a transform (node-input automation built); delete + import; assert no further recompute fires for the attribute it fed and the node-input automation for the removed transform no longer exists.

**Depends on**: Foundational (delete trigger + reconciliation duty).

- [ ] T018 [US5] Integration test in `test_selective_recompute.py`: import a transform feeding an attribute (node-input automation built by the create-event reconciliation), delete the transform and import; assert (a) subsequent node/data changes and commits produce zero recompute for the attribute it fed, and (b) the node-input recompute automation for the removed transform no longer exists after the delete-event `setup_triggers` run (the `to_delete = existing - desired` diff dropped it). The delete event is NOT a no-op. (FR-005, FR-006, SC-007, US5.)

**Checkpoint**: A deleted transform leaves no dangling recompute and no orphaned node-input automation.

---

## Phase 9: User Story 6 - Upgrade path: null fingerprints self-heal with one recompute per transform (Priority: P2)

**Goal**: Post-upgrade, each transform's null->value first import fires exactly one recompute; a subsequent no-op import of a watch-declared transform fires none.

**Independent Test**: Start from a transform with a null fingerprint; import once; assert the fingerprint is stamped and its attribute recomputes exactly once; import again with no change; assert zero further recompute.

**Depends on**: Foundational (create/update triggers).

- [ ] T019 [US6] Integration test in `test_selective_recompute.py`: start from a transform with a null fingerprint (pre-feature state); import once; assert the null is treated as changed, the fingerprint is stamped, and exactly one recompute fires; then import again with no content change (watch-declared) and assert zero further recompute. (FR-014, FR-015, FR-021, SC-008, US6.)

**Checkpoint**: The upgrade path self-heals, bounded to one pass per transform.

---

## Phase 10: Cross-cutting regression tests (the corrected-design holes)

**Purpose**: Guard the critical fixes the corrected design added — the node-input reconciliation hole (SC-010), the name-or-id resolution (SC-011), single-fire on first import (SC-012), and live-edit-only reaction (SC-006).

- [ ] T020 [P] Integration test in `test_selective_recompute.py` — the SC-010 regression (the critical hole): import a NEW transform (no schema diff, so the schema path never runs), then change a NODE that feeds the transform's query; assert the attribute recomputes. This proves the lifecycle flow built the node-input automation on the create event even though the schema path never ran; without the reconciliation duty this recompute would silently never happen. (FR-006, SC-010.)
- [ ] T021 [P] Integration test in `test_selective_recompute.py` — the SC-011 UUID case: a computed attribute wires its transform by UUID (not name); change the transform and import; assert the attribute recomputes exactly as for a name-wired attribute. (FR-010, SC-011.)
- [ ] T022 [P] Integration test in `test_selective_recompute.py` — the SC-012 single-fire case: on a transform's first import, assert exactly one recompute fires for it (guard against a create AND a separate fingerprint update in the same import double-firing). Relies on the T002 finding; if the importer can write twice, this test drives the dedupe in the lifecycle flow. (FR-015, SC-012.)
- [ ] T023 [P] Integration test in `test_selective_recompute.py` — merge/rebase replay + recompute-write no-re-fire: create the attribute on a branch, merge (or rebase) into main; assert the coalesced merge/rebase path handles recompute and the lifecycle trigger does NOT double-fire (fingerprint replay carries MERGE/REBASE origin, filtered by origin=LIVE); and assert a recompute write (kind != CoreTransformPython, field != fingerprint) does not re-fire the trigger (the kind+field guard). (FR-012, FR-013, SC-006.)

**Checkpoint**: Every corrected-design hole has a regression test.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Format, lint, run the suites, and confirm no generated-file drift.

- [ ] T024 Run `uv run invoke format lint` and fix any findings in the new/changed backend files.
- [ ] T025 Run the relevant unit tests (`backend/tests/unit/computed_attribute/test_recompute_resolution.py`, `test_triggers.py`) and the new integration suite (`backend/tests/integration/computed_attribute/test_selective_recompute.py`) via testcontainers; all green.
- [ ] T026 Run `uv run invoke docs.validate` and confirm it stays green (no generated-file drift expected, since no schema/enum/GraphQL/REST change was made). (Confirms T001.)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: No dependencies — start immediately. T002/T003/T004 are independent files/investigations and run in parallel.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user-story integration. Internal order: T005 (resolver) -> T006 (flow, uses resolver) -> T007 (register flow) -> T008 (triggers, fire the flow) -> T009 (remove old trigger def) -> T010 (catalogue swap) -> T011 (confirm untouched paths).
- **Unit tests (Phase 3)**: T012 needs T005; T013 needs T008+T010. Authored first-to-fail, then made green.
- **User Stories (Phases 4-9)**: All depend on Foundational. Once Foundational is done they can be authored in parallel (all in one integration test file, so writing them is serialized only by that shared file — split into sibling test files if parallel authoring is needed).
- **Cross-cutting regression (Phase 10)**: Depends on Foundational; T020 specifically depends on the T006 reconciliation duty; T022 depends on the T002 finding.
- **Polish (Phase 11)**: Depends on all targeted tasks being complete.

### User story dependency graph

```text
Foundational (T005 resolver ─► T006 flow ─► T007 register ─► T008 triggers ─► T009/T010 swap ─► T011 confirm)
        │
        ├─► US1 (T014)   unrelated commit -> no recompute        ┐
        ├─► US2 (T015)   transform change -> only its attributes  ├─ MVP = US1 + US2
        ├─► US3 (T016)   edit-then-revert -> no recompute
        ├─► US4 (T017)   no-watch -> per-commit but scoped
        ├─► US5 (T018)   delete -> no recompute + automation gone
        ├─► US6 (T019)   null fingerprint -> one recompute
        └─► Regression (T020 SC-010, T021 SC-011, T022 SC-012, T023 SC-006)
```

### Within each user story

- The resolver (T005) is written and unit-tested (T012) before any integration relies on it.
- Composer/flow before trigger wiring; trigger wiring before end-to-end observation.
- The lifecycle flow both fans out AND reconciles on every event; the reconciliation is the mechanism the SC-010 test (T020) and the US5 delete test (T018) guard.

### Parallel opportunities

- Setup: T002, T003, T004 in parallel (independent investigation / files).
- Unit tests: T012 and T013 in parallel (different files) once their deps land.
- Regression tests: T020, T021, T022, T023 are independent scenarios and can be authored in parallel if placed in sibling test files (they share `test_selective_recompute.py` by default, which serializes authoring, not execution).

---

## Parallel Example: Foundational core

```bash
# T005 (resolver) is the single dependency of T006; author it first, then:
Task: "Implement process_transform_lifecycle flow in computed_attribute/tasks.py"   # T006
# Then register + swap triggers sequentially (same two catalogue files):
Task: "Register the flow in workflows/catalogue.py"                                  # T007
Task: "Add the three lifecycle BuiltinTriggerDefinitions in triggers.py"            # T008
Task: "Remove the commit trigger from triggers.py + trigger/catalogue.py"           # T009, T010
```

---

## Implementation Strategy

### MVP first (User Story 1 + User Story 2)

1. Phase 1: Setup (confirm no schema change; trace importer create-vs-update; scaffolds; changelog).
2. Phase 2: Foundational (resolver + lifecycle flow + register + trigger swap + confirm untouched paths).
3. Phase 3: Unit tests (resolver + trigger shapes, incl. commit-trigger-removal).
4. Phase 4 (US1) + Phase 5 (US2): unrelated commit inert; transform change scoped to its own attributes.
5. **STOP and VALIDATE**: this is the reported defect fixed and the core value delivered.

### Incremental delivery

1. Setup + Foundational -> resolver, flow, triggers swapped, paths confirmed.
2. Unit tests -> resolver + trigger shapes locked.
3. US1 + US2 (MVP) -> validate the narrowing.
4. US3 -> content-based revert proof.
5. US4 -> no-watch safe default, scoped.
6. US5 -> delete teardown of the node-input automation.
7. US6 -> null-fingerprint self-heal, one pass per transform.
8. Regression (SC-010 / SC-011 / SC-012 / SC-006) -> the corrected-design holes.
9. Polish -> format, lint, tests, docs.validate.

---

## Definition of Done (task -> success-criteria mapping)

| Success criterion | Covered by |
|-------------------|------------|
| SC-001 unrelated commit -> zero recompute | T014 (US1) |
| SC-002 only the K changed transforms' attributes recompute | T012, T015 (US2) |
| SC-003 work scales with changed transforms, not attribute count | T015 (US2) |
| SC-004 edit-then-revert nets zero | T016 (US3) |
| SC-005 changed inputs converge; no permanently stale values | T015, T017, T019 |
| SC-006 merge/rebase no double-fire; recompute write no re-fire | T013, T023 |
| SC-007 delete -> zero recompute + node-input automation gone | T018 (US5) |
| SC-008 null-upgrade -> one recompute; no-op re-import -> zero | T019 (US6) |
| SC-009 no-watch never starved, scoped | T017 (US4) |
| SC-010 node-input change after transform-only import recomputes | T006, T020 (the critical-hole regression) |
| SC-011 UUID-wired transform resolves and recomputes | T012, T021 |
| SC-012 first import -> exactly one recompute per transform | T002, T022 |

**Done** when: every SC row above has a passing test, `uv run invoke format lint` is clean (T024), the unit + integration suites are green (T025), and `uv run invoke docs.validate` stays green with no generated-file drift (T026).

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- The lifecycle flow (T006) has TWO duties: the recompute fan-out (create + update-of-fingerprint) AND the node-input automation reconciliation (every create/update/delete). Dropping the reconciliation is the exact under-regeneration hole the corrected design fixes (FR-006); T020 is its regression guard.
- The resolver (T005) looks up `python_attributes_by_transform` by BOTH name and id, because a computed attribute may wire its transform either way (FR-010); T021 guards the UUID case.
- Loop safety (FR-013) comes from the kind+field match, not from an origin value — there is no `RECOMPUTE` origin; origin=LIVE is load-bearing only for merge/rebase (FR-012). T023 guards both.
- No schema/generated-file change (T001) means no `backend.generate` / `schema.generate-*` / `pnpm codegen` task; `docs.validate` (T026) should stay green.
- Per repo convention, no Jira/spec/FR IDs appear in test names, docstrings, or source comments — only in the commit message, PR body, and `changelog/+ifc-2804.changed.md` (T004).
