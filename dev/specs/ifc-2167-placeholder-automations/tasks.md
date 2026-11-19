---

description: "Task list for recording template fingerprints in the database instead of placeholder automations"
---

# Tasks: Record template fingerprints in the database instead of placeholder automations

**Input**: Design documents from `dev/specs/ifc-2167-placeholder-automations/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/recompute-decision.md](./contracts/recompute-decision.md), [contracts/fingerprint-store.md](./contracts/fingerprint-store.md), [quickstart.md](./quickstart.md)

**Tests**: Included. plan.md (Technical Context, Testing) lists unit, component and functional tests, and the constitution (Principle IV) requires them. Write each test task before the implementation task it covers, and check that it fails for the expected reason.

**Organization**: Tasks are grouped by user story. Display labels and HFIDs cannot stop creating their placeholder automations until their setup flows read the recorded fingerprints, so the display label and HFID part of User Story 1 is delivered in the User Story 2 phase (see Dependencies).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1, US2, US3, US4)
- All paths are relative to the repository root. Sites inside a file are named by their function or class.

## Path conventions

- Backend code: `backend/infrahub/`
- Backend tests: `backend/tests/unit/`, `backend/tests/component/`, `backend/tests/functional/`, `backend/tests/integration_docker/`
- No frontend change, no generated file change, no graph migration, no new index (plan.md, research Decision 3).

---

## Phase 1: Setup

**Purpose**: Create the new packages and load the domain knowledge.

- [X] T001 Read `dev/knowledge/backend/display-labels-and-hfid.md` (section "Async Backfill After Schema Changes"), `dev/knowledge/backend/computed-attributes.md` (self-targeting triggers), `dev/knowledge/backend/events.md` (section "Branch scoping of automations"), `dev/knowledge/backend/query-pattern.md`, `dev/knowledge/backend/database-schema.md` and `dev/knowledge/backend/testing.md` before writing code
- [X] T002 Create the empty packages `backend/infrahub/core/template_fingerprint/__init__.py`, `backend/tests/unit/core/template_fingerprint/__init__.py`, `backend/tests/component/core/template_fingerprint/__init__.py` and `backend/tests/component/hfid/__init__.py`

---

## Phase 2: Foundational (fingerprint store, collector and decision)

**Purpose**: The record, its queries, its repository, the schema collector and the pure recompute decision. User Stories 2, 3 and 4 depend on them. User Story 1 for Jinja2 computed attributes does not.

**Blocks**: no task of User Stories 2, 3 or 4 starts before this phase is complete.

- [X] T003 [P] Write unit tests for the decision in `backend/tests/unit/core/template_fingerprint/test_decision.py`: one test per row of the two tables in `contracts/recompute-decision.md`:
  - deletion of a record whose branch is not in scope;
  - deletion of a record whose kind or template is no longer in the schema of an in-scope branch;
  - nothing recomputed or recorded when `branch_deleted` is true, when `event_branch` is `None`, and when the event branch is not in scope;
  - recorded fingerprint equal to the schema fingerprint: nothing;
  - default branch, missing or different record: recompute and record;
  - other branch, template identical to the default branch: no recompute, record, kind listed in `skipped_identical`;
  - other branch, template different from the default branch or kind missing on the default branch: recompute and record;
  - records of branches other than the event branch are never in `to_record`.
- [X] T004 [P] Create `backend/infrahub/core/template_fingerprint/models.py`:
  - `TemplateFamily` (`StrEnum`) with the values `display_label_jinja2` and `human_friendly_id`, equal to the `TriggerType` values of the two families (data-model.md, "TemplateFamily");
  - frozen dataclasses `FingerprintKey(family, branch, kind)`, `RecordedFingerprint(key: FingerprintKey, fingerprint: str)`, `SchemaFingerprints(family, by_branch: dict[str, dict[str, str]])` and `FingerprintDecision(to_recompute: list[str], to_record: list[RecordedFingerprint], to_delete: list[FingerprintKey], skipped_identical: list[str])`;
  - `TemplateFingerprint`, a `StandardNode` subclass with the properties `family`, `branch`, `kind` and `fingerprint` (all `str`), and no persistence method, following `backend/infrahub/core/preferences/models.py::Preference`.
- [X] T005 Create `backend/infrahub/core/template_fingerprint/decision.py` with a pure function that takes `family`, `event_branch: str | None`, `branch_deleted: bool`, `default_branch: str`, `schema: SchemaFingerprints` and `recorded: list[RecordedFingerprint]` and returns a `FingerprintDecision`, following the rules of `contracts/recompute-decision.md`. No database, task manager or registry access. Make T003 pass (depends on T003, T004)
- [X] T006 [P] Write component tests for the repository in `backend/tests/component/core/template_fingerprint/test_repository.py`, modeled on `backend/tests/component/core/test_preference_repository.py`:
  - `get_by_family` returns only the records of the requested family;
  - `upsert` creates a record, overwrites `fingerprint` on a second call and leaves one vertex per `(family, branch, kind)`;
  - `upsert` and `insert_missing` write nothing for a branch that has no `Branch` vertex (research Decision 10);
  - `insert_missing` creates missing records, never overwrites an existing one, and returns the number created;
  - `delete` removes only the listed keys; `delete_branch` removes every record of one branch and no other;
  - `upsert`, `insert_missing` and `delete` on an empty list send no query.
- [X] T007 Create the Query classes in `backend/infrahub/core/query/template_fingerprint.py`, one per repository method, following `backend/infrahub/core/query/preference.py`. Build the Cypher text in `__init__`, bind every value as a parameter, name the `TemplateFingerprint` label in every query, and return results through a frozen `*QueryResult` dataclass `get_data()`. Query shapes, quoted from `contracts/fingerprint-store.md`:
  - get: `MATCH (f:TemplateFingerprint {family: $family}) RETURN f.branch, f.kind, f.fingerprint`;
  - upsert: `UNWIND $records AS r MATCH (:Branch {name: r.branch}) MERGE (f:TemplateFingerprint {family: r.family, branch: r.branch, kind: r.kind}) ON CREATE SET f.uuid = r.uuid SET f.fingerprint = r.fingerprint`;
  - insert missing: the same `MATCH` on `Branch` and `MERGE`, with `ON CREATE SET f.uuid = r.uuid, f.fingerprint = r.fingerprint` only, returning the number of created vertices;
  - delete: `UNWIND $keys AS k MATCH (f:TemplateFingerprint {family: k.family, branch: k.branch, kind: k.kind}) DETACH DELETE f`;
  - delete branch: `MATCH (f:TemplateFingerprint {branch: $branch}) DETACH DELETE f` (depends on T004)
- [X] T008 Create `TemplateFingerprintRepository(db: InfrahubDatabase)` in `backend/infrahub/core/template_fingerprint/repository.py` with `get_by_family(family) -> list[RecordedFingerprint]`, `upsert(records) -> None`, `insert_missing(records) -> int`, `delete(keys) -> None` and `delete_branch(branch) -> None`, each running one Query class from T007 and returning immediately on an empty list. A record read from the database whose `family` is not a `TemplateFamily` value is skipped (data-model.md, "Validation rules"). Make T006 pass (depends on T006, T007)
- [X] T009 [P] Write unit tests for the collector in `backend/tests/unit/core/template_fingerprint/test_collector.py`, reusing existing schema fixtures: for each family, the collector returns the default branch and every branch from `get_altered_schema_branches()`, with `get_hash()` of each entry of `display_labels.get_template_nodes()` or `hfids.get_template_nodes()`, and the same values that `DisplayLabelTriggerDefinition.from_schema_display_labels` and `HFIDTriggerDefinition.from_schema_hfids` put in `template_hash` (research Decision 11)
- [X] T010 Create `collect_schema_fingerprints(family) -> SchemaFingerprints` in `backend/infrahub/core/template_fingerprint/collector.py`, reading `registry.default_branch`, `registry.get_altered_schema_branches()` and `registry.schema.get_schema_branch(name=...)` as described in `contracts/fingerprint-store.md`, "Collector". No database or task manager access. Make T009 pass (depends on T004, T009)

**Checkpoint**: `uv run pytest backend/tests/unit/core/template_fingerprint/ backend/tests/component/core/template_fingerprint/` passes.

---

## Phase 3: User Story 1 - Keep the task manager free of automations that never run (Priority: P1), Jinja2 computed attributes

**Goal**: Infrahub no longer creates the self-targeting Jinja2 computed attribute automations, and the computed attribute setup flow submits the same recomputes as today (research Decision 1). This phase does not use the fingerprint store and can start after Phase 1.

**Independent test**: On a schema with Jinja2 computed attributes that read only their own node, run the computed attribute setup flow. The task manager holds no `computed_attr_jinja2` automation whose trigger matches `_trigger_placeholder`, the automations for peer-driven computed attributes still exist, and the recorded submissions are the same as before the change.

### Tests for User Story 1

- [ ] T011 [P] [US1] Update `backend/tests/component/computed_attribute/test_gather.py`: `gather_trigger_computed_attribute_jinja2` returns no trigger definition for a `targets_self` trigger node, and still returns the definitions for trigger nodes that read a peer, including for a computed attribute that reads both its own node and a peer (spec, Edge Cases)
- [ ] T012 [P] [US1] Replace the placeholder-field assertions in `backend/tests/functional/computed_attributes/test_local_computation.py` (the test that expects `TestingTShirt` triggers to use `TRIGGER_PLACEHOLDER_FIELD`, and the one that checks the constant is absent from peer fields) with assertions that no self-targeting trigger definition is gathered and that peer trigger definitions keep their real fields
- [ ] T013 [P] [US1] Update `backend/tests/component/computed_attribute/test_scoped_recompute_jinja2.py` and add cases with a `WorkflowRecorder` from `backend/tests/adapters/workflow.py`:
  - with `changed_elements`, only the computed attributes selected by `RecomputeScoper` are submitted;
  - without `changed_elements`, every self-targeting computed attribute of the event branch is submitted;
  - on a branch whose template equals the default branch template, nothing is submitted for that attribute (spec, User Story 2 scenario 5);
  - on a branch whose template differs, the attribute is submitted on that branch only (User Story 2 scenario 6);
  - on a branch that does not own its schema, nothing is submitted;
  - on `BranchDeletedEvent`, nothing is submitted.

### Implementation for User Story 1

- [ ] T014 [US1] In `backend/infrahub/computed_attribute/gather.py::gather_trigger_computed_attribute_jinja2`, skip trigger nodes with `targets_self` instead of copying them with `TRIGGER_PLACEHOLDER_FIELD`, and remove the now unused import of `TRIGGER_PLACEHOLDER_FIELD`. Make T011 and T012 pass
- [ ] T015 [US1] In `backend/infrahub/computed_attribute/tasks.py::computed_attribute_setup_jinja2`, stop reading self-targeting triggers from the setup report:
  - build the candidates from the `targets_self` entries of `registry.schema.get_schema_branch(name=branch_name).computed_attributes.get_jinja2_trigger_nodes()`, and only when `branch_name` is the default branch or is returned by `registry.get_altered_schema_branches()`; otherwise the candidate list is empty;
  - keep the `changed_elements` scoping through `RecomputeScoper` and the fallback to every candidate when `changed_elements` is `None`;
  - compare the branch template hash with `computed_attribute.attribute.computed_attribute.get_hash()` of the same kind and attribute in the default branch schema, instead of the `template_hash` of the default branch automation;
  - keep `setup_triggers_specific` for the peer automations, and submit the same workflow with the same parameters as today.
  Make T013 pass (depends on T014)
- [ ] T016 [US1] Add a component test in `backend/tests/component/computed_attribute/test_placeholder_removal.py` that runs the computed attribute setup flow on the Prefect test server and checks that no automation of the `computed_attr_jinja2` family has a trigger matching `_trigger_placeholder`, and that a placeholder automation created by the previous release (built with `ComputedAttrJinja2TriggerDefinition.from_computed_attribute` and a trigger node whose attributes are `[TRIGGER_PLACEHOLDER_FIELD]`) is deleted (spec, User Story 1 scenario 2, User Story 3 scenario 1) (depends on T015)

**Checkpoint**: `uv run pytest backend/tests/component/computed_attribute/ backend/tests/functional/computed_attributes/test_local_computation.py` passes. User Story 1 is complete for Jinja2 computed attributes; display labels and HFIDs follow in Phase 4.

---

## Phase 4: User Story 2 - Stored values are recomputed exactly when a template changes (Priority: P1), display labels and HFIDs

**Goal**: The display label and HFID setup flows decide each recompute from the recorded fingerprints instead of the placeholder automations, and the placeholders are no longer created. This phase also completes User Story 1 scenarios 1 to 4 for display labels and HFIDs.

**Independent test**: Load a schema, then a second version that changes only the display label template of one kind. Exactly one display label recompute is submitted, for that kind on that branch, and none for HFIDs or computed attributes. Loading the same schema again submits nothing.

### Tests for User Story 2

- [ ] T017 [P] [US2] Update `backend/tests/component/display_labels/test_gather.py`: `gather_trigger_display_labels_jinja2` returns no definition whose fields are `[TRIGGER_PLACEHOLDER_FIELD]`, and still returns the definitions for templates that read a peer attribute (spec, User Story 1 scenario 4)
- [ ] T018 [P] [US2] Write `backend/tests/component/display_labels/test_setup.py` that runs `display_labels_setup_jinja2` on the Prefect test server with a `WorkflowRecorder` and asserts the exact list of submitted `TRIGGER_UPDATE_DISPLAY_LABELS` workflows and the records left in the database:
  - template changed on the default branch: one submission for that kind, record updated (User Story 2 scenario 1);
  - no template changed: no submission (scenario 4);
  - branch template identical to the default branch: no submission, record written for the branch (scenario 5);
  - branch template different: one submission on that branch, none on the default branch (scenario 6);
  - two runs in a row for the same change: the second run submits nothing (FR-007);
  - submission raises: no record written, and the next run submits again (FR-006, spec Edge Cases);
  - kind or template removed: its record deleted, no submission (spec Edge Cases);
  - no automation of the family has a trigger matching `_trigger_placeholder` after the run, and the peer-driven automation exists (User Story 1 scenarios 1, 3 and 4).
- [ ] T019 [P] [US2] Write `backend/tests/component/hfid/test_setup.py` with the same cases for `hfid_setup` and `TRIGGER_UPDATE_HFID`, plus HFID added to a kind that had none: one submission (User Story 2 scenario 2), and one schema update that changes the display label template of one kind and the HFID of another: exactly one submission per family (scenario 7, run both setup flows)

### Implementation for User Story 2

- [ ] T020 [P] [US2] In `backend/infrahub/display_labels/models.py::DisplayLabelTriggerDefinition.from_schema_display_labels`, stop creating the definitions for `get_template_nodes()` (the ones with `fields=[TRIGGER_PLACEHOLDER_FIELD]` and `target_kind == node_kind`). Keep the definitions built from `get_related_trigger_nodes()`, and keep `TRIGGER_PLACEHOLDER_FIELD` in `backend/infrahub/trigger/constants.py` because the carry-over matches on it (plan.md structure). Make T017 pass
- [ ] T021 [P] [US2] In `backend/infrahub/hfid/models.py::HFIDTriggerDefinition.from_schema_hfids`, make the same change as T020
- [ ] T022 [US2] Rewrite the body of `backend/infrahub/display_labels/tasks.py::display_labels_setup_jinja2` after `wait_for_schema_to_converge`, following "Order of execution in the setup flow" in `contracts/recompute-decision.md`, without step 2 (added in T029):
  - build `TemplateFingerprintRepository(db=db)` at the top of the flow;
  - take the lock with `lock.registry.get(name=f"configure-action-rules-{TriggerType.DISPLAY_LABEL_JINJA2.value}", namespace="trigger-rules", local=False)` and hold it until the records are written;
  - inside the lock, gather and call `setup_triggers` (not `setup_triggers_specific`) for the peer automations and keep the report;
  - read the records with `get_by_family`, collect the schema fingerprints with `collect_schema_fingerprints`, and compute the decision with `branch_deleted=(event_name == BranchDeletedEvent.event_name)`;
  - delete `to_delete`, submit one `TRIGGER_UPDATE_DISPLAY_LABELS` per kind in `to_recompute` with the parameters `branch_name` and `kind`, then `upsert(to_record)` in one call; a submission that raises skips the write;
  - stop submitting from `report.modified_triggers_with_type(...)`, and log the kinds in `skipped_identical` at debug level.
  Make T018 pass (depends on T005, T008, T010, T020)
- [ ] T023 [US2] Make the same change as T022 in `backend/infrahub/hfid/tasks.py::hfid_setup`, with `TriggerType.HUMAN_FRIENDLY_ID`, `TemplateFamily` `human_friendly_id` and `TRIGGER_UPDATE_HFID`. Make T019 pass (depends on T005, T008, T010, T021)
- [ ] T024 [US2] In `backend/infrahub/workflows/initialization.py::setup_task_manager_identifiers`, after the two `setup_triggers` calls, open a database session, build `TemplateFingerprintRepository`, and call `insert_missing` with the collector output of both families for every branch in scope. Submit no recompute (research Decision 9). Add a test in `backend/tests/component/core/test_initialization.py` that the first start writes one record per kind with a display label template or an HFID, and that a following unchanged schema update submits nothing (depends on T008, T010)

**Checkpoint**: `uv run pytest backend/tests/component/display_labels/ backend/tests/component/hfid/ backend/tests/component/core/test_initialization.py` passes. User Stories 1 and 2 are complete for all three families.

---

## Phase 5: User Story 3 - Upgrade an existing instance without a full recompute (Priority: P2)

**Goal**: The fingerprints held by the display label and HFID placeholder automations are copied into records where those automations are deleted, so an unchanged schema submits no recompute after the upgrade (research Decision 8).

**Independent test**: Create placeholder automations as the previous release does, for the default branch and two branches, run `trigger_configure_all`, then run the display label and HFID setup flows on the unchanged schema. The placeholders are gone, one record exists per carried-over automation, and nothing is submitted.

### Tests for User Story 3

- [ ] T025 [P] [US3] Write unit tests in `backend/tests/unit/trigger/test_placeholder_carry_over.py` for each condition in `contracts/fingerprint-store.md`, "Carry-over":
  - name prefix other than `display_label_jinja2::` or `human_friendly_id::`: skipped;
  - trigger matching a field other than `TRIGGER_PLACEHOLDER_FIELD` (the self-peer `<kind>::by::<kind>` automation): skipped;
  - branch names that contain `/` and `-` are parsed correctly by splitting from the right on `::`;
  - `<kind>` different on each side of `by`: skipped;
  - description without a `| hash:` suffix, or with an empty value: skipped;
  - branch not in scope: skipped;
  - a matching automation becomes one `RecordedFingerprint` with the parsed family, branch, kind and hash.
- [ ] T026 [P] [US3] Write a component test in `backend/tests/component/trigger/test_placeholder_carry_over.py` on the Prefect test server and Neo4j:
  - create display label and HFID placeholder automations for the default branch and two branches with `DisplayLabelTriggerDefinition.new` and `HFIDTriggerDefinition.new` and `fields=[TRIGGER_PLACEHOLDER_FIELD]`, delete one by hand;
  - run `trigger_configure_all`: no placeholder automation remains and one record exists per remaining placeholder (User Story 3 scenario 1, SC-003);
  - run the two setup flows on the unchanged schema with a `WorkflowRecorder`: nothing is submitted except the kind whose automation was deleted by hand (scenarios 2 and 4);
  - run `trigger_configure_all` a second time: no record is created or overwritten.

### Implementation for User Story 3

- [ ] T027 [US3] Create `backend/infrahub/trigger/placeholder_carry_over.py` with a pure parsing function that turns one Prefect `Automation` into a `RecordedFingerprint` or `None` following the five conditions, and `carry_over_placeholder_fingerprints(deleted, schema, repository) -> int` that parses `TriggerSetupReport.deleted`, passes the matches to `repository.insert_missing`, logs each skipped automation at debug level and returns the number created. Make T025 pass (depends on T008)
- [ ] T028 [US3] In `backend/infrahub/trigger/tasks.py::trigger_configure_all`, keep the report returned by `setup_triggers`, build `TemplateFingerprintRepository(db=db)` and the collector output of both families, and call `carry_over_placeholder_fingerprints` with `report.deleted` (depends on T010, T027)
- [ ] T029 [US3] Add step 2 of `contracts/recompute-decision.md` to `backend/infrahub/display_labels/tasks.py::display_labels_setup_jinja2` and `backend/infrahub/hfid/tasks.py::hfid_setup`: inside the lock, after `setup_triggers` and before `get_by_family`, call `carry_over_placeholder_fingerprints` with `report.deleted`. Make T026 pass (depends on T022, T023, T027, T028)

**Checkpoint**: `uv run pytest backend/tests/unit/trigger/test_placeholder_carry_over.py backend/tests/component/trigger/` passes.

---

## Phase 6: User Story 4 - Branch lifecycle keeps the recorded fingerprints consistent (Priority: P3)

**Goal**: Records disappear with their branch, a late setup run cannot write records for a deleted branch, and a branch that stops owning its schema loses its records (research Decision 10).

**Independent test**: Create a branch with a schema change on a kind with a display label, delete the branch, create a branch with the same name and the same change, and check that its nodes are recomputed.

### Tests for User Story 4

- [ ] T030 [P] [US4] Write `backend/tests/component/branch/test_template_fingerprint_cleanup.py`:
  - `BranchDataDeleter.delete` removes every record of the branch and none of other branches (User Story 4 scenario 1, SC-004);
  - a setup flow whose worker registry still holds the deleted branch writes no record for it (spec Edge Cases);
  - a new branch with the same name and the same diverging template gets one display label submission from `display_labels_setup_jinja2` (scenario 2).
- [ ] T031 [P] [US4] Add to `backend/tests/component/display_labels/test_setup.py` a case where a branch stops owning its schema (its schema becomes equal to the default branch schema): the next setup run deletes the branch's records and submits nothing for it (User Story 4 scenario 3)

### Implementation for User Story 4

- [ ] T032 [US4] In `backend/infrahub/core/branch/data_deleter.py::BranchDataDeleter.delete_branch_data`, delete the branch's records before the edges, so a resumed delete also removes them. `BranchDataDeleter(` appears 31 times in `backend/infrahub` and `backend/tests`, and the class already runs its own Query classes, so run the delete-branch Query class from T007 directly, as it does for its other queries, instead of adding a constructor parameter. Then update `contracts/fingerprint-store.md` (repository table and "Callers that write") so it states that `BranchDataDeleter` runs the query, and remove `delete_branch` from the repository and its test if nothing else calls it. Make T030 pass (depends on T007, T022)

**Checkpoint**: `uv run pytest backend/tests/component/branch/ backend/tests/component/display_labels/` passes.

---

## Phase 7: Polish and cross-cutting concerns

**Purpose**: Documentation, changelog, regression runs and measurements.

- [ ] T033 [P] Update `dev/knowledge/backend/display-labels-and-hfid.md`, section "Async Backfill After Schema Changes": the setup flows compare the schema fingerprints with `TemplateFingerprint` records under the per-family lock, record after submission, carry over placeholders, and the branch deleter removes the records
- [ ] T034 [P] Update `dev/knowledge/backend/computed-attributes.md` (self-targeting triggers): no automation is created for self-targeting Jinja2 trigger nodes; candidates and the default-branch hash come from the schema
- [ ] T035 [P] Update `dev/knowledge/backend/events.md`, section "Branch scoping of automations": remove the three placeholder families from the list of automations created per diverging branch
- [ ] T036 Create the changelog fragment `changelog/+ifc-2167.changed.md` with `towncrier create` through the `creating-changelog-entries` skill: the task manager no longer holds one automation per kind and per diverging branch for display labels, HFIDs and Jinja2 computed attributes; the upgrade removes the existing ones without recomputing values. Lint it with Vale
- [ ] T037 Check that `TRIGGER_PLACEHOLDER_FIELD` is used only in `backend/infrahub/trigger/constants.py`, `backend/infrahub/trigger/placeholder_carry_over.py` and tests (`grep -rn TRIGGER_PLACEHOLDER_FIELD backend/infrahub backend/tests`)
- [ ] T038 Run `EXPLAIN` on the get query of `backend/infrahub/core/query/template_fingerprint.py` on a database with at least 50 kinds and 3 diverging branches, and record the plan in the PR description; propose an index only with maintainer approval (research Decision 3)
- [ ] T039 Run the regression suite `uv run pytest backend/tests/integration_docker/test_computed_attributes.py`
- [ ] T040 Run `uv run invoke format`, `uv run invoke lint`, `uv run invoke backend.mypy`, `uv run ty check` and `uv run invoke docs.validate`, and fix every finding without adding a suppression
- [ ] T041 Run the live scenarios 1 to 4 of `dev/specs/ifc-2167-placeholder-automations/quickstart.md` on a local stack built from this branch, and measure SC-005 as described in its "Performance check" section (durations of `display-labels-setup-jinja2` and `hfid-setup` on the previous release and on this branch); record the results in the PR description

---

## Dependencies and execution order

### Phase dependencies

- **Setup (Phase 1)**: no dependency.
- **Foundational (Phase 2)**: depends on Phase 1. Blocks Phases 4, 5 and 6.
- **User Story 1, Jinja2 part (Phase 3)**: depends on Phase 1 only. Can run in parallel with Phase 2.
- **User Story 2 (Phase 4)**: depends on Phase 2. Completes User Story 1 for display labels and HFIDs.
- **User Story 3 (Phase 5)**: depends on Phase 4, because T029 changes the setup flows rewritten in T022 and T023.
- **User Story 4 (Phase 6)**: depends on Phase 2 for T032 and on Phase 4 for the setup-flow tests.
- **Polish (Phase 7)**: depends on every story phase.

### Why the display label and HFID part of User Story 1 sits in Phase 4

The display label and HFID setup flows decide a recompute from the modified placeholder automations. Removing those placeholders (T020, T021) before the flows read the records (T022, T023) would stop every display label and HFID recompute. T020 to T023 must land together.

### Release constraint

Phases 4 and 5 must ship in the same release. A release with Phase 4 and without Phase 5 deletes the placeholder automations without carrying their fingerprints over, so the first schema update after the upgrade recomputes every kind on every diverging branch (spec, User Story 3).

### Within each phase

- Tests before the implementation task they cover, and failing first.
- Models (T004) before queries (T007), queries before the repository (T008).
- The decision, repository and collector before the setup flows.

### Parallel opportunities

- Phase 2: T003, T004, T006 and T009 together; then T005, T007 and T010 together.
- Phase 3 can run alongside Phase 2: T011, T012 and T013 together.
- Phase 4: T017, T018 and T019 together; T020 and T021 together.
- Phase 5: T025 and T026 together.
- Phase 6: T030 and T031 together.
- Phase 7: T033, T034 and T035 together.

---

## Parallel example: User Story 2

```text
# Tests, all in different files:
Task: "T017 Update backend/tests/component/display_labels/test_gather.py"
Task: "T018 Write backend/tests/component/display_labels/test_setup.py"
Task: "T019 Write backend/tests/component/hfid/test_setup.py"

# Stop creating the placeholder definitions:
Task: "T020 backend/infrahub/display_labels/models.py"
Task: "T021 backend/infrahub/hfid/models.py"
```

---

## Implementation strategy

### First deliverable

1. Phase 1 and Phase 3: the Jinja2 computed attribute placeholders disappear. This removes about one third of the placeholder automations with no new storage (spec, Assumptions).
2. Check the Phase 3 checkpoint.

### Incremental delivery

1. Phase 2: fingerprint store, collector and decision, tested on their own.
2. Phase 4: display labels and HFIDs read the records; User Stories 1 and 2 complete.
3. Phase 5: carry-over for upgrades. Do not release Phase 4 without it.
4. Phase 6: branch lifecycle.
5. Phase 7: documentation, changelog, regression runs, measurements.

---

## Notes

- `[P]` tasks touch different files and depend on no unfinished task.
- T022 and T029 edit the same function, as do T023 and T029; run them in order.
- T032 departs from `contracts/fingerprint-store.md` (the contract names `delete_branch` on the repository as the deleter's entry point); the task updates the contract in the same change.
