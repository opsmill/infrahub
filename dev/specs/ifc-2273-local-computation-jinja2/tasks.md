# Tasks: Local Computation of Jinja2 Computed Attributes

**Input**: Design documents from `/specs/ifc-2273-local-computation-jinja2/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: Test tasks included — computed attributes require integration_docker tests per constitution (Principle IV).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No project initialization needed — this modifies existing code. Skip to foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Registry enhancements and extra_filters extension that ALL user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T001 Add `relationship_fields` property to `RegisteredNodeComputedAttribute` in `backend/infrahub/core/schema/schema_branch_computed.py` that returns `dict[str, set[str]]` mapping relationship names to peer attribute names needed for Jinja2 template rendering, derived from the relationship entries and their associated `ComputedAttributeTarget.attribute.computed_attribute.jinja2_template` variable paths
- [ ] T002 Add `get_local_jinja2_targets(kind, updates)` method to `ComputedAttributes` in `backend/infrahub/core/schema/schema_branch_computed.py` that wraps `get_impacted_jinja2_targets()` and filters results to only return `ComputedAttributeTarget` entries where `target.kind == kind` (local changes only)
- [ ] T003 Extend `Node._collect_extra_filters()` in `backend/infrahub/core/node/__init__.py` to include computed attribute `relationship_fields` from `schema_branch.computed_attributes`, merging them with existing display_label/HFID extra_filters via `_merge_relationship_fields()`, gated by a check that the node has Jinja2 computed attributes and is an update (existing node)
- [ ] T004 [P] Add unit tests for `relationship_fields` property and `get_local_jinja2_targets()` in `backend/tests/unit/core/schema/test_schema_branch_computed.py` — test local vs remote target filtering, relationship field extraction, and empty/missing cases

**Checkpoint**: Registry and peer loading infrastructure ready. User story implementation can begin.

---

## Phase 3: User Story 1 — Immediate Computed Attribute Updates on Local Attribute Changes (Priority: P1) MVP

**Goal**: When a user updates a local attribute that a Jinja2 computed attribute depends on, the computed attribute is recalculated inline within `_update()` and included in the mutation response.

**Independent Test**: Update an attribute used by a computed attribute on the same node; verify the mutation response contains the updated computed value and no background task is spawned.

### Implementation for User Story 1

- [ ] T005 [US1] Create `_recompute_local_jinja2()` async method on `Node` in `backend/infrahub/core/node/__init__.py` that: (1) gets the schema_branch, (2) calls `computed_attributes.get_local_jinja2_targets(kind=self._schema.kind, updates=fields)`, (3) for each target, resolves Jinja2 template variables from the node's in-memory attribute values and resolved relationship peers (reusing the variable resolution pattern from `_process_macros()`), (4) renders the template via `InfrahubJinja2Template.render()`, (5) if value changed, updates the attribute on `self` and saves it via `attr.save()`, (6) records in `NodeChangelog`, (7) on Jinja2 rendering error: logs warning and leaves value unchanged (FR-013)
- [ ] T006 [US1] Call `_recompute_local_jinja2()` from `Node._update()` in `backend/infrahub/core/node/__init__.py` — insert the call after attribute and relationship saves (after line ~924) but before HFID/display_label recomputation (before line ~934), passing the `fields` parameter to scope which computed attributes to check
- [ ] T007 [US1] Handle chained computed attribute dependencies in `_recompute_local_jinja2()`: when multiple computed attributes on the same node are affected, sort by dependency order (if computed attr A references computed attr B, compute B first) using iterative resolution — in `backend/infrahub/core/node/__init__.py`
- [ ] T008 [US1] Add functional test in `backend/tests/functional/computed_attribute/test_local_computation.py`: create a schema with a Jinja2 computed attribute referencing a local attribute, create a node, update the local attribute, verify the computed attribute is recalculated in the same mutation and the response value is correct
- [ ] T009 [US1] Add functional test in `backend/tests/functional/computed_attribute/test_local_computation.py`: verify that updating an attribute NOT used by the computed attribute template does NOT trigger recomputation (FR-005 — acceptance scenario 3)
- [ ] T010 [US1] Add functional test in `backend/tests/functional/computed_attribute/test_local_computation.py`: verify that inline Jinja2 evaluation failure logs an error and leaves the computed attribute unchanged while the mutation succeeds (FR-013)

**Checkpoint**: Local attribute changes trigger inline computed attribute recomputation. Core value proposition delivered.

---

## Phase 4: User Story 2 — Immediate Computed Attribute Updates on Local Relationship Changes (Priority: P1)

**Goal**: When a user changes a relationship on a node, computed attributes referencing that relationship's peer attributes are recalculated inline.

**Independent Test**: Re-assign a Device to a different Site; verify the computed `name` attribute reflects the new Site's name in the mutation response.

### Implementation for User Story 2

- [ ] T011 [US2] Ensure `_recompute_local_jinja2()` handles relationship-type template variables in `backend/infrahub/core/node/__init__.py`: when a template variable references a relationship peer attribute (e.g., `site__name__value`), resolve the value from the already-resolved `RelationshipManager` peer objects loaded via the extended `_collect_extra_filters()` — the peer attributes should already be available after `resolve_relationships()`
- [ ] T012 [US2] Handle null/empty relationship case in `_recompute_local_jinja2()` in `backend/infrahub/core/node/__init__.py`: when a relationship is being set to null, pass `None` for that variable to the Jinja2 template and let it render accordingly (edge case from spec)
- [ ] T013 [US2] Add functional test in `backend/tests/functional/computed_attribute/test_local_computation.py`: create a Device with computed `name` = `{{ instance__value }}-{{ site__name__value }}`, assign to SiteA, then re-assign to SiteB, verify computed name uses SiteB's name in mutation response
- [ ] T014 [US2] Add functional test in `backend/tests/functional/computed_attribute/test_local_computation.py`: set a relationship to null on a node with a computed attribute referencing that relationship, verify the template renders with null context and the mutation succeeds

**Checkpoint**: Both local attribute and relationship changes trigger inline recomputation.

---

## Phase 5: User Story 3 — Convert Self-Targeting Triggers to Placeholders (Priority: P2)

**Goal**: Convert self-targeting computed attribute triggers to use `_trigger_placeholder` fields (matching the HFID/display label pattern), so they never fire on per-node changes but still exist for schema-change detection. Remote triggers keep real field names and continue firing via Prefect.

**Independent Test**: Update a Site's name; verify Devices referencing that Site have their computed attributes updated via background tasks. Verify self-targeting triggers use `_trigger_placeholder`.

### Implementation for User Story 3

- [ ] T015 [US3] In `backend/infrahub/computed_attribute/gather.py`, modify `gather_trigger_computed_attribute_jinja2()` so that `targets_self=True` trigger nodes have their fields replaced with `["_trigger_placeholder"]` before calling `ComputedAttrJinja2TriggerDefinition.from_computed_attribute()` — matching the pattern in `hfid/models.py:59-61` and `display_labels/models.py:59-61`. Remote trigger nodes (`targets_self=False`) keep their real field names.
- [ ] T016 [US3] Add unit test in `backend/tests/unit/computed_attribute/test_trigger_definition.py`: verify that self-targeting triggers are created with `_trigger_placeholder` fields, remote triggers keep real field names, and a computed attribute with only local dependencies still produces one placeholder trigger (not zero)
- [ ] T017 [US3] Add functional test in `backend/tests/functional/computed_attribute/test_local_computation.py`: update a peer node attribute (e.g., rename a Site) and verify that computed attributes on related nodes (Devices) are still updated via background tasks (existing behavior preserved)

**Checkpoint**: Self-targeting triggers are placeholders. Remote triggers work via background tasks. Both paths coexist correctly.

---

## Phase 6: User Story 4 — Consolidated Events for Local Changes (Priority: P2)

**Goal**: Each node mutation that triggers local computed attribute recomputation emits exactly one event/webhook, not two.

**Independent Test**: Subscribe to node change events, perform a local change triggering computed attribute recomputation, verify exactly one event is received.

### Implementation for User Story 4

- [ ] T018 [US4] Verify event consolidation works automatically: since `_recompute_local_jinja2()` saves computed attributes within `_update()` and records changes in the same `NodeChangelog`, the single `NodeUpdatedEvent` emitted by `generate_node_mutation_events()` should already include both the original change and the computed attribute update — add a functional test in `backend/tests/functional/computed_attribute/test_local_computation.py` that asserts only one event is emitted and it contains both the original field and the computed attribute field in `updated_fields`

**Checkpoint**: Single consolidated event per mutation confirmed.

---

## Phase 7: User Story 5 — Bulk Update Performance (Priority: P2)

**Goal**: Bulk update of existing nodes with computed attributes does not spawn background tasks for local changes.

**Independent Test**: Create 100+ nodes, then bulk-update their local attributes; verify zero background tasks spawned for computed attribute recomputation and all computed values are correct.

### Implementation for User Story 5

- [ ] T019 [US5] Add functional test in `backend/tests/functional/computed_attribute/test_local_computation.py`: create 50+ nodes with Jinja2 computed attributes depending on local attributes, then bulk-update a local attribute on each node, verify all computed values are correct post-update (functional tests have no Prefect server, so correct values prove the inline path handled everything)

**Checkpoint**: Bulk update performance validated.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, knowledge base updates, and changelog.

- [ ] T020 [P] Update `dev/knowledge/backend/` with computed attribute local computation documentation — add a section to an existing knowledge doc or create `dev/knowledge/backend/computed-attributes.md` covering the dual evaluation path (inline for local, Prefect for remote), the `_recompute_local_jinja2()` method, and the `_collect_extra_filters()` extension
- [ ] T021 [P] Add towncrier changelog fragment in `changelog/` for the user-facing improvement: computed attributes now update immediately on local changes
- [ ] T022 Run existing computed attribute test suite to verify no regressions: `uv run invoke backend.test-unit -- -k computed_attribute`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — can start immediately
- **US1 (Phase 3)**: Depends on Phase 2 completion (T001-T004)
- **US2 (Phase 4)**: Depends on Phase 3 completion (US1 provides the core `_recompute_local_jinja2()` method)
- **US3 (Phase 5)**: Depends on Phase 2 completion only (trigger suppression is independent of inline recomputation)
- **US4 (Phase 6)**: Depends on Phase 3 completion (needs inline recomputation working to verify event consolidation)
- **US5 (Phase 7)**: Depends on Phase 3 completion (needs inline recomputation working for bulk test)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational — core inline recomputation
- **US2 (P1)**: Depends on US1 — extends `_recompute_local_jinja2()` for relationship variables
- **US3 (P2)**: Depends on Foundational only — trigger suppression is independent
- **US4 (P2)**: Depends on US1 — event verification needs inline recomputation
- **US5 (P2)**: Depends on US1 — bulk test needs inline recomputation

### Parallel Opportunities

- **Phase 2**: T001 and T002 are sequential (T002 depends on registry), T003 depends on T001+T002, T004 can start after T001+T002
- **After Phase 3 (US1)**: US2, US4, and US5 can all run in parallel (they touch different test files and different aspects)
- **US3**: Can run in parallel with US1 (touches `computed_attribute/models.py`, not `core/node/__init__.py`)
- **Phase 8**: T020 and T021 can run in parallel

---

## Parallel Example: After Foundational

```bash
# US1 and US3 can run in parallel (different files):
# US1 agent: backend/infrahub/core/node/__init__.py (inline recomputation)
# US3 agent: backend/infrahub/computed_attribute/models.py (trigger suppression)

# After US1 completes, US2, US4, US5 can run in parallel:
# US2: extends _recompute_local_jinja2() + relationship tests
# US4: event consolidation test
# US5: bulk import test
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (registry + extra_filters)
2. Complete Phase 3: US1 (inline recomputation for local attribute changes)
3. **STOP and VALIDATE**: Test US1 independently
4. This alone eliminates the majority of unnecessary background tasks

### Incremental Delivery

1. Foundational → ready
2. US1 → inline attr recomputation → Test → **(MVP!)**
3. US1 + US2 → add relationship changes → Test
4. US3 → suppress background tasks for local → Test
5. US4 + US5 → verify events + bulk → Test
6. Polish → docs, changelog

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- All inline rendering reuses the existing `_process_macros()` variable resolution pattern
- The `_collect_extra_filters()` extension ensures peer attributes are loaded without extra DB queries
- Trigger suppression (US3) and inline recomputation (US1) are independent and can be developed in parallel
