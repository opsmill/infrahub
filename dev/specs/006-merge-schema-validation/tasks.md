# Tasks: Validate schema changes against both branches at merge and rebase

**Input**: Design documents from `specs/006-merge-schema-validation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/refusal-messages.md](contracts/refusal-messages.md), [quickstart.md](quickstart.md)

**Tests**: Required. The spec's acceptance scenarios and constitution principle IV call for tests at each tier. Write
each regression test before its fix and confirm it fails without the fix (`.agents/rules/testing-python.md`, "A
regression guard must be shown to bite").

**Reference implementation**: the stash `migration-validators-wip-2026-11-03` (`110e36f4`). Its own changes are
`git diff 110e36f4^1 110e36f4`; its new files are in `git show 110e36f4^3` (for example
`git show 110e36f4^3:backend/tests/component/core/constraint_validators/test_node_attribute_add.py`). Reuse its tests
and code where this plan keeps its design; the merged schema (research R5) and the gate (research R4) differ.

**Organization**: Tasks are grouped by user story. Paths are relative to the repository root. Run backend tests from
`backend/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story the task belongs to (US1–US6)

---

## Phase 1: Setup

- [X] T001 Prepare the worktree on branch `merge-schema-validation`: run `git submodule update --init python_sdk`, `uv sync --all-groups` and `uv pip install -e ./python_sdk` from the repository root, then run `uv run pytest tests/unit/core/schema/test_schema_branch.py -q` from `backend/` to confirm the environment
- [X] T002 Load the guidelines that apply before writing code: `dev/guidelines/backend/python.md`, `dev/guidelines/backend/testing.md`, `dev/guidelines/code-doc-style.md`, `dev/knowledge/backend/database-schema.md` and `dev/knowledge/backend/query-pattern.md`, plus the `neo4j-cypher-guide` skill before T017

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the view option, the merged schema and the analyzer, which user stories 1–4 all use.

### View option

- [X] T003 [P] Make `is_isolated` a required field on `SchemaValidateMigrationData` (description: whether to read the default branch as it was when the branch was created; False reads its current data, which a merge or a rebase produces) and add it to `serialize_model` in `backend/infrahub/core/validators/models/validate_migration.py`
- [X] T004 [P] Add `is_isolated: bool` with default `True` and the same description to `SchemaConstraintValidatorRequest`, including `serialize_model`, in `backend/infrahub/core/validators/model.py`
- [X] T005 Pass `message.is_isolated` from `schema_validate_migrations` to `schema_path_validate`, make it a required parameter there, and set it on the `SchemaConstraintValidatorRequest` it builds, in `backend/infrahub/core/validators/tasks.py` (depends on T003, T004)
- [X] T006 [P] Add `is_isolated: bool = True` to `SchemaValidatorQuery.__init__`, store it as `self.is_isolated`, and document it in the Args section, in `backend/infrahub/core/validators/shared.py`
- [X] T007 Pass `is_isolated=True` explicitly in `_validate_migrations` and `check_schema` in `backend/infrahub/api/schema.py`, and in `update_core_schema` in `backend/infrahub/cli/db.py` (depends on T003)
- [X] T008 [P] Update the message tests: the round trip in `backend/tests/component/core/constraint_validators/test_models.py` builds the message with `is_isolated=False`, and `backend/tests/component/core/constraint_validators/test_task_schema_validate_migrations.py` passes `is_isolated=True` (depends on T003)

### Merged schema (research R5, data-model "Merged schema rules")

- [X] T009 Write the unit tests for the merged schema in `backend/tests/unit/core/schema/test_schema_branch.py`, in a class that builds processed schema branches with the existing `_load_processed_branch` helper and the `car_person_schema_root` fixture: one test per row of the data-model results table (mandatory kept, kind and schema class kept, branch wins on a shared field, both additions kept, removed attribute absent, removed kind absent, rename followed, inherited attribute from a generic, profile kind updated), plus tests that a kind or attribute the default branch removed and the branch changed keeps the branch's copy, and that a generic's `used_by` lists the nodes both branches added and leaves out the nodes either branch removed. Start from the stash's `TestUpdateChanges` class and kind-class test. Confirm they fail before T010
- [X] T010 Add the `SchemaBranch` method that applies a branch's schema diff since a base schema to this schema, taking values from the branch's schema, following the data-model rules (added/removed kinds, changed node fields, attribute and relationship additions, removals and field changes matched by id then name, kind change rebuilt with its new schema class, profile and template kinds of changed nodes, clear error on an unmatched element), in `backend/infrahub/core/schema/schema_branch.py` (depends on T009)

### Analyzer

- [ ] T011 Write the component test in `backend/tests/component/core/test_branch_merge.py` that asserts the exact list of `(constraint_name, kind, field, property)` that `calculate_validations` returns when the branch makes an attribute unique and mandatory and adds a mandatory attribute, and the default branch adds its own mandatory attribute; the list includes the default branch's `node.attribute.add`. Start from the stash's `test_merge_validations_include_the_validators_of_the_schema_migrations_of_both_branches`. Add a test that the analyzer's schema-change gate returns true when only the default branch changed the schema and false when neither did
- [ ] T012 In `MergeSchemaAnalyzer` in `backend/infrahub/core/merge/schema_analyzer.py`: make `calculate_validations` call `add_validator_for_migration(validator_map=CONSTRAINT_VALIDATOR_MAP)` on the 3-way validation result; make `get_candidate_schema` async, returning a copy of the destination schema when the source and destination hashes are equal and otherwise applying the branch's diff since the common ancestor with the T010 method; add the schema-change gate method (the recomputed branch diff has schema changes, or the two in-memory schema hashes differ) (depends on T010, T011)

**Checkpoint**: T008, T009 and T011 tests pass; `uv run mypy` is clean on the changed modules.

---

## Phase 3: User Story 1 - Refuse a branch whose schema change is broken by the default branch's data (Priority: P1) 🎯 MVP

**Goal**: merge, proposed-change merge and rebase refuse a branch whose migration-required change is broken by data
created on the default branch after branching.

**Independent Test**: the integration tests in T018 each refuse the operation with the exact message and leave both
branches unchanged.

### Tests for User Story 1

- [X] T013 [P] [US1] Add a parametrized test (dataclass cases `branch-view` and `merge-view`) to `backend/tests/component/core/constraint_validators/test_attribute_optional.py`: a node created on the default branch before the branch and given a value after, and a node created on the default branch after the branch without a value; the branch view flags the first, the merge view flags the second. Start from the stash's `test_validator_on_branch_reads_the_requested_view_of_main`
- [X] T014 [P] [US1] Add the same two-view test to `backend/tests/component/core/constraint_validators/test_attribute_kind_update.py` with the values `not-a-network-at-branch` and `not-a-network-on-main-after-branch` against `IPNetwork`
- [X] T015 [P] [US1] Create `backend/tests/component/core/constraint_validators/test_node_attribute_add.py` with: every node found before the attribute exists; on a branch, nodes with a value and nodes deleted on the branch skipped while a default-branch node and a branch node with a null value are flagged; the two-view test (node deleted on the default branch after branching versus node created there after branching). Start from the stash's version of this file
- [ ] T016 [US1] Add integration tests to `backend/tests/integration/schema_lifecycle/test_schema_validator_stored_data.py`: `BranchMerge` refused for an attribute made unique, an attribute made mandatory, and a mandatory attribute added without a default value; `BranchRebase` refused for an attribute made unique; each asserting the exact messages from `contracts/refusal-messages.md`, the branch status `OPEN`, and both branches' schema and data unchanged. Start from the stash's tests

### Implementation for User Story 1

- [X] T017 [US1] In `backend/infrahub/core/validators/node/attribute.py`, add `NodeAttributeValueMissingValidatorQuery` (active nodes of the kind whose attribute is missing, inactive, null or `NULL_VALUE`, with the attribute matched in an optional subquery and the standard edge ordering, reading `self.is_isolated`), returning only `n.uuid` and the root edge's branch name, and make `NodeAttributeAddChecker` use it and pass `request.is_isolated`; keep `NodeNotPresentValidatorQuery` for the relationship check. Run `EXPLAIN` on the query and keep the plan for the pull request (depends on T006)
- [X] T018 [P] [US1] Make `AttributeOptionalUpdateValidatorQuery` and `AttributeKindUpdateValidatorQuery` pass `is_isolated=self.is_isolated` to `get_query_filter_path`, and their checkers pass `is_isolated=request.is_isolated`, in `backend/infrahub/core/validators/attribute/optional.py` and `backend/infrahub/core/validators/attribute/kind.py` (depends on T006)
- [ ] T019 [US1] In `MergeConstraintValidator.validate` in `backend/infrahub/core/merge/constraints.py`, send `SchemaValidateMigrationData` with `is_isolated=False` (depends on T003)
- [ ] T020 [US1] In `GraphMerger._validate_constraints` in `backend/infrahub/core/merge/graph_merger.py`, await the async merged schema and gate the schema-diff constraints on the analyzer's gate method; replace the comment with a one-sentence reason (depends on T012)
- [ ] T021 [US1] In the rebase flow in `backend/infrahub/core/branch/tasks.py`, await the merged schema, gate the schema-diff constraints on the analyzer's gate method instead of the branch's cached flag, and send the validation message with `is_isolated=False` (depends on T012)
- [ ] T022 [US1] Run T013–T016 and confirm each fails when its fix is reverted (T017, T018, T019–T021 respectively, and T012's `add_validator_for_migration`); record the result for the pull request

**Checkpoint**: user story 1 works on its own: branch changes broken by default-branch data are refused.

---

## Phase 4: User Story 2 - Refuse a branch whose data breaks a schema change made on the default branch (Priority: P1)

**Goal**: merge and rebase refuse a branch whose data breaks a change loaded on the default branch after branching,
including when the branch changed no schema.

**Independent Test**: T023 and T024 refuse each case at merge and at rebase.

### Tests for User Story 2

- [ ] T023 [US2] Add integration tests to `backend/tests/integration/schema_lifecycle/test_schema_validator_stored_data.py`: merge refused when the default branch adds a mandatory attribute and the branch holds a node; rebase refused for the same; merge refused when the default branch makes an attribute mandatory and the branch holds a null; rebase refused when the default branch changes an attribute from Text to Number and the branch holds `big`; each with exact messages and both branches unchanged (the branch's attribute keeps its old kind after the refused rebase). Start from the stash's Socket, Outlet, Lamp and Meter tests
- [ ] T024 [US2] Create `backend/tests/integration_docker/test_schema_merge_validation.py` following `backend/tests/integration_docker/test_schema_migration.py`: an attribute's kind changes from Text to Number on the branch with a non-number on the default branch, and on the default branch with a non-number on the branch; each refused at merge and at rebase with the exact messages; and a branch with compliant data that merges

### Implementation for User Story 2

- [ ] T025 [US2] Confirm that the merge and rebase flows load the latest schema of both branches into the worker's registry before the checks (read `backend/infrahub/core/merge/` and the rebase flow in `backend/infrahub/core/branch/tasks.py`, and the schema refresh on schema-update events); if not, refresh both branches' schemas in the analyzer before the gate, and add a component test for it
- [ ] T026 [US2] Run T023 and T024 and confirm they fail without the T012 gate and merged schema; if T024 shows a difference from the in-process tests, add the failing case to the T009 unit tests

**Checkpoint**: user stories 1 and 2 work together; changes on either side are checked against the other side's data.

---

## Phase 5: User Story 3 - Keep accepting valid merges and rebases (Priority: P1)

**Goal**: no new refusal for compliant data, and no schema check when neither side changed the schema.

**Independent Test**: T027 and T028 accept each case; T029 shows no schema check runs without schema changes.

- [ ] T027 [P] [US3] Add integration tests to `backend/tests/integration/schema_lifecycle/test_schema_validator_stored_data.py` for accepted merges: a mandatory attribute added on the branch with values set on the branch's nodes, and a null value created before branching that the branch sets before making the attribute mandatory; assert the merged data on the default branch
- [ ] T028 [P] [US3] Add a component test in `backend/tests/component/core/test_branch_merge.py` that a merge of a branch with data changes but no schema change on either side produces no schema-diff constraints
- [ ] T029 [US3] Run the local matrix in `quickstart.md` on fresh stacks (R1–R10 refused, A1–A5 and A8 accepted, each through merge, proposed-change merge and rebase) and record the table for the pull request; any unexpected result becomes a failing test before it is fixed (depends on T017–T021, T025)

**Checkpoint**: P1 stories complete; this is the MVP.

---

## Phase 6: User Story 4 - See the same violations on the proposed change (Priority: P2)

**Goal**: the proposed change's schema check reports the same violations as the merge.

**Independent Test**: T030 shows the proposed change's check failing with the merge's violations for a change made
only on the default branch.

- [ ] T030 [US4] Add a test to `backend/tests/component/message_bus/operations/requests/test_proposed_change.py`, next to `test_schema_integrity`, where the default branch makes an attribute mandatory after branching and the branch holds a node without a value: the schema integrity check records the violation, and a schema change made only on the default branch is not reported as one the branch made
- [ ] T031 [US4] In `run_proposed_change_schema_integrity_check` in `backend/infrahub/proposed_change/tasks.py`, build a `MergeSchemaAnalyzer` for the source and destination branches, use its merged schema and `calculate_validations` for the schema-diff constraints, keep the schema processing step and the data-diff constraints, and send the validation message with `is_isolated=False` (depends on T012, T030)

---

## Phase 7: User Story 6 - Confirm and fix the two suspected merge gaps (Priority: P3, first pull request)

**Goal**: each suspected gap is confirmed or ruled out with a test.

- [X] T032 [P] [US6] Add a component test in `backend/tests/component/core/constraint_validators/` for the new-relationship check at merge: a branch adds a mandatory relationship and creates nodes that set it; run the `node.relationship.add` check in the merge view and assert no violation. If it fails, add a relationship-presence query like T017's and make the check pass `request.is_isolated`, in `backend/infrahub/core/validators/node/relationship.py`
- [ ] T033 [P] [US6] Add an integration test in `backend/tests/integration/schema_lifecycle/test_schema_validator_stored_data.py`: a node created on a branch, then an attribute with a default value added on the default branch, then a merge; assert the merged node holds the default value. If it fails, mark it `xfail(strict=True)` with the mechanism as reason and open an issue with the reproduction, because the fix belongs in the merge migrations

---

## Phase 8: Polish and delivery of the first pull request

- [ ] T034 [P] Update `docs/docs/branches/merge.mdx` and `docs/docs/branches/rebase.mdx`: add to their troubleshooting tables the refusals for a schema change on either side that the other side's data breaks, with the recovery paths for a mandatory attribute added on the default branch without a default value (delete the nodes on the branch, or add a default value on the default branch); run `uv run invoke docs.lint`
- [ ] T035 [P] Create the changelog fragment with `uv run towncrier create -c "<text>" +merge-schema-validation.fixed.md`, starting from the stash's `changelog/+merge-migration-validators.fixed.md` and checking every claim against the code
- [ ] T036 Run `uv run invoke format`, `uv run invoke lint`, `uv run ruff check . --exclude python_sdk`, `uv run ruff format --check --exclude python_sdk .` and `uv run invoke docs.validate` from the repository root; delete `backend/repositories/` first if integration tests left it
- [ ] T037 Run the affected suites from `backend/`: `tests/unit/core`, `tests/component/core/constraint_validators`, `tests/component/core/test_branch_merge.py`, `tests/component/core/test_branch_rebase.py`, `tests/component/api/test_40_schema.py`, `tests/component/message_bus/operations/requests/test_proposed_change.py`, `tests/integration/schema_lifecycle`, `tests/integration/proposed_change`, and the new Docker test
- [ ] T038 Write the pull request description against `release-1.12`: the issues fixed, the behavior changes from the spec, the regression checks from T022 and T026, the matrix table from T029, the `EXPLAIN` plan from T017, and the follow-ups (user story 5, issue 10, any gap recorded in T033); remind the user to run `/pre-ci`, and drop the stash `migration-validators-wip-2026-11-03` only after the user confirms

---

## Phase 9: User Story 5 - Regex, enum, length and choices at merge (Priority: P3, second pull request)

**Goal**: the four remaining queries read the requested view.

- [ ] T039 [P] [US5] Add the two-view component test to `backend/tests/component/core/constraint_validators/test_attribute_regex_update.py`, `test_attribute_enum_update.py`, `test_attribute_length.py` and `test_attribute_choices_update.py`
- [ ] T040 [US5] Make the queries and checkers in `backend/infrahub/core/validators/attribute/regex.py`, `enum.py`, `length.py` and `choices.py` read `self.is_isolated` and pass `request.is_isolated` (depends on T039)
- [ ] T041 [US5] Add one integration refusal (a regex added on the branch, a non-matching value created on the default branch after branching) to `backend/tests/integration/schema_lifecycle/test_schema_validator_stored_data.py`, a changelog fragment, and open the second pull request

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (Phase 1) → Foundational (Phase 2) → user stories.
- User stories 1 and 2 both need T012; user story 2's tests also rely on the gate wiring from T020 and T021.
- User story 3's matrix (T029) runs after user stories 1 and 2 are implemented.
- User story 4 needs T012 only.
- User story 6 can start after Phase 2.
- Polish (Phase 8) closes the first pull request; Phase 9 starts after it merges.

### Within each story

Tests first and failing, then the implementation, then the regression-guard check.

### Parallel opportunities

- T003, T004, T006 (different files) in parallel; T008 after T003.
- T013, T014, T015 in parallel (different test files); T018 in parallel with T017.
- T027 and T028 in parallel; T032 and T033 in parallel; T034 and T035 in parallel.

## Parallel Example: User Story 1

```text
T013 test_attribute_optional.py two-view test
T014 test_attribute_kind_update.py two-view test
T015 test_node_attribute_add.py
then T017 (node/attribute.py) alongside T018 (attribute/optional.py, attribute/kind.py)
```

## Implementation Strategy

### MVP first

Phases 1–5 (user stories 1–3) are the MVP: the reported defect and its reverse are fixed, and valid merges keep
working, validated by the local matrix.

### Incremental delivery

1. Phases 1–2: the foundation, tested on its own.
2. Phase 3: user story 1, the reported defect.
3. Phases 4–5: user stories 2 and 3, then the matrix.
4. Phases 6–8: the proposed-change check, the suspected gaps, docs and delivery of the first pull request.
5. Phase 9: the second pull request.

## Notes

- Ask before any graph migration, GraphQL schema change, new dependency or CI change; none is planned.
- Comments and docstrings follow `.agents/rules/code-doc-style.md`: one-sentence reasons, no names of other
  functions or classes.
- Commit only when the user asks; never use a bare `git stash`.
