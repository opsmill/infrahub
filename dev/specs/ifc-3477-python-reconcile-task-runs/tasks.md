---

description: "Task list for a fixed number of task runs per Python computed-attribute reconcile"
---

# Tasks: One branch deletion records the same number of task runs whatever the number of open branches

**Input**: Design documents from `dev/specs/ifc-3477-python-reconcile-task-runs/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/task-runs-and-messages.md](contracts/task-runs-and-messages.md), [quickstart.md](quickstart.md)

**Tests**: The spec gives each functional requirement a test, so test tasks are included. Write each test first and run it to confirm it fails, or for FR-002 that it passes on today's code, before changing production code.

**Organization**: Tasks are grouped by user story so that each story can be implemented and tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: The user story the task belongs to (US1 to US4 in spec.md)

## Path Conventions

- Production code: `backend/infrahub/computed_attribute/gather.py`
- Tests: `backend/tests/component/computed_attribute/`
- Changelog: `changelog/` at the repository root

---

## Phase 1: Setup

**Purpose**: Start from the right base and record the behavior before the change.

- [ ] T001 Confirm the branch `python-reconcile-task-runs-ifc-3477` is based on `origin/stable`. Check whether the pull requests #11093 and #11095 have merged into `stable` (`gh pr view 11093 --repo opsmill/infrahub --json state`, the same for 11095). If either has merged, rebase onto `origin/stable` first. If #11095 has merged, keep its skip for a branch with no repository commit in `backend/infrahub/computed_attribute/gather.py::gather_python_transform_attributes` in every later task (research R9).
- [ ] T002 Run the existing computed-attribute suites to record a passing baseline: `uv run pytest backend/tests/component/computed_attribute/ -v` and `uv run pytest backend/tests/functional/computed_attributes/ -v`. Note any test that already fails so it is not attributed to this change.

---

## Phase 2: Foundational (test infrastructure shared by US1 and US2)

**Purpose**: The test module, fixtures and helpers that the task-run count tests of US1 and US2 need.

**⚠️ CRITICAL**: US1 and US2 test tasks depend on this phase.

- [ ] T003 Create `backend/tests/component/computed_attribute/test_reconcile_task_runs.py` with a class `TestReconcileTaskRuns(ScopedRecomputeTestBase)` from `tests/component/computed_attribute/_base.py`, with `WORKFLOW = TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES`. Add a class-scoped `transform_dataset` fixture modeled on `test_scoped_recompute_python.py::TestScopedRecomputePython.transform_dataset`. It creates `transform01` with `create_transform01`, creates `transform_opaque`, and loads `CAR_PERSON_PYTHON_SCHEMA` with `load_schema(..., update_db=True)`. The fixture returns the ids of both transforms, which the lifecycle cases need. Follow `.agents/rules/testing-python.md`: no mocks, exact assertions, and no issue or ticket numbers in names, docstrings or comments.
- [ ] T004 In the same module, add a class-scoped fixture that captures Prefect events in-process (research R3):
  - It calls `EventsWorker.set_client_override(AssertingPassthroughEventsClient)` (`prefect.events.worker.EventsWorker`, `prefect.events.clients.AssertingPassthroughEventsClient`) and yields `EventsWorker.instance()`.
  - In `finally`, it drains that worker and calls `EventsWorker.set_client_override(None)`, so no process-global state leaks to later tests.
- [ ] T005 In the same module, add an `async` helper that counts the task runs of one flow run. It runs a flow coroutine with `return_state=True` and reads the flow-run id from `state.state_details.flow_run_id`. Then it calls `await asyncio.to_thread(worker.wait_until_empty)`. It returns the number of distinct event resource ids that start with `prefect.task-run.` among the captured events whose `related` resources include `prefect.flow-run.<flow_run_id>`. It must not assert on task names or on which functions are tasks.
- [ ] T006 In the same module, add a branch helper (research R6):
  - Creating a branch uses `infrahub.core.initialization.create_branch`.
  - Deleting a branch uses `BranchDataDeleter(db=db, batch_size=...).delete(branch=branch, user_id=TEST_ACTOR_ID)`, with `TEST_ACTOR_ID` from `tests/helpers/agnostic_edges.py`, followed by `registry.purge_inactive_branches(db=db)`. Do not call `Branch.delete`, which raises `NotImplementedError`.
- [ ] T007 In the same module, add a class-scoped teardown that deletes the automations whose names start with `TriggerType.COMPUTED_ATTR_PYTHON.value` or `TriggerType.COMPUTED_ATTR_PYTHON_QUERY.value` followed by `NAME_SEPARATOR`. Read them with `infrahub.trigger.setup.gather_all_automations` and delete them with `delete_automation`, following `dev/knowledge/backend/testing.md` §"Prefect Server State Outlives the Test Class".

**Checkpoint**: The module imports and collects. `uv run pytest backend/tests/component/computed_attribute/test_reconcile_task_runs.py --collect-only` succeeds.

---

## Phase 3: User Story 1 - A branch deletion records a fixed number of task runs (Priority: P1) 🎯 MVP

**Goal**: The `computed-attribute-setup-python` run that a branch deletion starts holds the same number of task runs whatever the number of open branches, and the node-input automations after the deletion are correct (FR-001, FR-002, SC-001, SC-002).

**Independent Test**: In `test_reconcile_task_runs.py`, the `branch_deleted` count is equal with 2 and with 10 branches and greater than zero, and the automation names after a deletion match the literal expected set.

### Tests for User Story 1 (write first)

- [ ] T008 [US1] In `backend/tests/component/computed_attribute/test_reconcile_task_runs.py`, add a dataclass `ReconcileCountCase` whose first field is `name`, and a module-level list `RECONCILE_COUNT_CASES` with one case, `branch_deleted`. The case deletes a freshly created branch with the T006 helper. It then runs `computed_attribute_setup_python(context=..., branch_name=<deleted branch name>, event_name=BranchDeletedEvent.event_name)` through the T005 helper.
- [ ] T009 [US1] In the same module, add two class-scoped fixtures:
  - `counts_with_2_branches` makes sure exactly 2 branches besides the default branch exist while each case runs. It creates one extra branch for the `branch_deleted` case to delete, then returns `{case.name: count}` for every case in `RECONCILE_COUNT_CASES`.
  - `counts_with_10_branches` depends on `counts_with_2_branches`, creates enough branches to reach 10 besides the default branch while each case runs (again plus one for `branch_deleted` to delete), and returns the same mapping.
- [ ] T010 [US1] In the same module, add `test_task_run_count_does_not_depend_on_branch_count`, parametrized over `RECONCILE_COUNT_CASES` with `ids=[c.name for c in RECONCILE_COUNT_CASES]`. It asserts `counts_with_10_branches[case.name] == counts_with_2_branches[case.name]` and `counts_with_2_branches[case.name] > 0`. Run it: it MUST fail on today's code, because each extra branch adds 2 task runs.
- [ ] T011 [US1] In the same module, add `test_branch_deletion_keeps_the_automations_a_full_reconcile_builds` (FR-002). Define it after T010's test, so it runs after the count fixtures. Steps:
  - Create a branch that owns an automation. Prefer setting `repo01`'s `commit` to a different value on that branch, which gives the branch its own automation and adds it to the default-branch automation's exclusions (`computed_attribute/models.py`, `gather.py::gather_trigger_computed_attribute_python`). The other option is to add the computed attribute only on that branch, as `test_gather.py::test_gather_trigger_computed_attribute_python_only_on_branch` does.
  - Run the reconcile through `process_transform_lifecycle(..., action=MutationAction.UPDATED.value)` on `main`. Then assert the literal set of `COMPUTED_ATTR_PYTHON` automation names, built as `<type>::<branch>::TestCar_<attribute>` like `test_transform_lifecycle_recompute.py::test_delete_drops_removed_transform_automation_but_keeps_others` does. Pin the literal set only after confirming it on today's code.
  - Delete the branch with the T006 helper, then run `computed_attribute_setup_python(branch_name=<deleted>, event_name=BranchDeletedEvent.event_name)`.
  - Assert the literal set again: the branch's automation is gone and the `main` automations remain. If the branch was excluded through its commit, the default-branch automation no longer excludes it. No automation name of either Python type contains the deleted branch's name.
  - This test passes on today's code. It guards FR-002 through the change.

### Implementation for User Story 1

- [ ] T012 [US1] In `backend/infrahub/computed_attribute/gather.py`, remove the `@task(name="gather-python-transform-attributes", task_run_name=..., cache_policy=NONE)` decorator from `gather_python_transform_attributes`. Keep its signature, its body and its `get_run_logger()` call. Keep the `task` and `NONE` imports, because `gather_trigger_computed_attribute_jinja2` and `gather_trigger_computed_attribute_python` still use them. Do not change `gather_trigger_computed_attribute_python`'s grouping logic. Do not add a comment that narrates the change (`.agents/rules/code-doc-style.md`).
- [ ] T013 [US1] Run `uv run pytest backend/tests/component/computed_attribute/test_reconcile_task_runs.py -v`. T010 and T011 MUST pass.
- [ ] T014 [US1] Show that the guard works (`.agents/rules/testing-python.md` §"A regression guard must be shown to bite"). Put the decorator removed in T012 back temporarily and run T010's test: it MUST fail. Note the two counts it reports for the pull request, then remove the decorator again.

**Checkpoint**: A branch deletion records a fixed number of task runs, and the automations are unchanged. This is the MVP.

---

## Phase 4: User Story 2 - Schema updates and Python transform changes record a fixed number of task runs (Priority: P2)

**Goal**: FR-003. The same count holds for a schema update and for a Python transform create, update and delete.

**Independent Test**: The new cases of `test_task_run_count_does_not_depend_on_branch_count` pass, and fail when the decorator is put back.

### Tests for User Story 2

- [ ] T015 [US2] In `backend/tests/component/computed_attribute/test_reconcile_task_runs.py`, add these cases to `RECONCILE_COUNT_CASES`:
  - `schema_updated` runs `computed_attribute_setup_python(context=..., branch_name=<default branch>, event_name=SchemaUpdatedEvent.event_name)`.
  - `transform_created`, `transform_updated` and `transform_deleted` run `process_transform_lifecycle(branch_name=<default branch>, transform_id=<transform01 id from transform_dataset>, action=MutationAction.<CREATED|UPDATED|DELETED>.value, context=...)`. Follow `test_transform_lifecycle_recompute.py`.
  - The `transform_deleted` case only reconciles. It does not need the transform to be deleted first.
  - The recompute submissions go to the class's `WorkflowRecorder`, so they add no task runs (research R2).

### Verification for User Story 2

- [ ] T016 [US2] Run `uv run pytest backend/tests/component/computed_attribute/test_reconcile_task_runs.py -v`. All cases MUST pass with T012 in place.
- [ ] T017 [US2] Repeat the T014 check for the new cases: with the decorator put back, `schema_updated`, `transform_created`, `transform_updated` and `transform_deleted` MUST fail. Then remove the decorator again.

**Checkpoint**: Every event that runs the reconcile records a fixed number of task runs.

---

## Phase 5: User Story 3 - Warnings and errors name the branch they come from (Priority: P3)

**Goal**: FR-004 and FR-005. The missing-transform warning names the branch and the transform. A failure on one branch carries a note that names the branch, and the exception type is unchanged.

**Independent Test**: The two new tests in `test_gather.py` pass, and fail before the production changes.

### Tests for User Story 3 (write first)

- [ ] T018 [P] [US3] In `backend/tests/component/computed_attribute/test_gather.py`, add `test_gather_warns_with_branch_when_transform_is_missing` (FR-004).
  - It requests `db`, `default_branch`, `register_core_models_schema` and `car_person_schema_computed_attr`, and not `transform01`. The core models are needed because the gather reads the repositories first (research R6).
  - Patch `infrahub.computed_attribute.gather.get_run_logger` to return `logging.getLogger(<module logger name>)`, as `dev/knowledge/backend/testing.md` §"Logging: Use `caplog` Instead of Mocking `get_run_logger`" shows. This is the one exception to the mocking rule.
  - Call `await gather_trigger_computed_attribute_python.fn(db=db)` under `caplog.at_level(logging.WARNING, ...)`.
  - Assert that the captured warning messages equal exactly `["No Python transform named 'transform01' was found on branch 'main', but a computed attribute is assigned to it."]`. Use the default branch's actual name.
  - Run it: it MUST fail on today's message.
- [ ] T019 [US3] In `backend/tests/component/computed_attribute/test_gather.py`, add `test_gather_failure_names_the_branch` (FR-005), with `transform01` loaded.
  - Create a branch. Load `query01`, the `CoreGraphQLQuery` that `transform01` reads, on that branch with `NodeManager.get_one(..., branch=<branch>)`, and delete it with `await node.delete(db=db)`. Load it on the branch first, or the delete lands on `main`.
  - Call `await gather_trigger_computed_attribute_python(db=db)` inside `pytest.raises(LookupError, match=r"^Unable to find the peer\nGathering the Python computed attributes failed on branch '<branch>'$")`. Confirm the exception type and message on today's code first (research R6).
  - Run it: it MUST fail on today's code, because the note is missing.

### Implementation for User Story 3

- [ ] T020 [US3] In `backend/infrahub/computed_attribute/gather.py::gather_python_transform_attributes`, replace the missing-transform warning with `f"No Python transform named '{transform_name}' was found on branch '{branch_name}', but a computed attribute is assigned to it."` (research R5, contract).
- [ ] T021 [US3] In `backend/infrahub/computed_attribute/gather.py::gather_trigger_computed_attribute_python`, wrap only the `await gather_python_transform_attributes(...)` call for one branch in `try` / `except Exception as exc:`. Call `exc.add_note(f"Gathering the Python computed attributes failed on branch '{branch.name}'")`, then use a bare `raise` (research R4, `dev/guidelines/backend/exceptions.md` §"Re-raise what you can't handle"). Keep the `try` body to that one call.
- [ ] T022 [US3] Run `uv run pytest backend/tests/component/computed_attribute/test_gather.py -v`. T018, T019 and the existing gather tests MUST pass.

**Checkpoint**: Operators can find the branch behind a warning or a failure without the per-branch task runs.

---

## Phase 6: User Story 4 - An operator finds how to remove the rows already written (Priority: P3)

**Goal**: FR-006. The changelog names `infrahub tasks flush flow-runs`, and the details go where release notes can use them.

**Independent Test**: The fragment and the pull request notes match the spec's Resolved Clarifications.

- [ ] T023 [P] [US4] Read the `creating-changelog-entries` skill. Then create `changelog/11165.fixed.md` with `uv run towncrier create 11165.fixed.md --content "..."`. Do not write the file by hand. The content is one past-tense sentence from the operator's perspective, with no jargon. It says that a branch deletion, a schema update or a Python transform change no longer adds task-manager records for every open branch, and it names `infrahub tasks flush flow-runs` as the way to remove the records already written (research R7). Check it with `uv run towncrier build --draft --version 0.0.0`.
- [ ] T024 [P] [US4] Write `dev/specs/ifc-3477-python-reconcile-task-runs/pr-notes.md`, the release-note details for the pull request description. List each item with its source from the spec's Resolved Clarifications:
  - `infrahub tasks flush flow-runs` deletes every flow run of any flow that is completed, failed or cancelled and older than `--days-to-keep` days (30 by default), with its task runs, task-run states and logs;
  - PostgreSQL reuses the freed space but does not return it to the operating system;
  - `VACUUM FULL` returns the space, locks each table while it rewrites it, and needs free disk space about the size of that table.

  Add the counts from T014 and T017.

**Checkpoint**: Operators who upgrade know how to reclaim the space that the old behavior used.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T025 Confirm that `dev/knowledge/backend/computed-attributes.md` §"Node-Input Automations" still describes the reconcile correctly, and leave it unchanged if so (research R8). Do not edit `dev/guides/backend/creating-async-tasks.md`. The rule about tasks called in a loop is left for `speckit-opsmill-extract`.
- [ ] T026 Run the full computed-attribute suites again, as in T002, and compare with the baseline: `uv run pytest backend/tests/component/computed_attribute/ -v` and `uv run pytest backend/tests/functional/computed_attributes/ -v`.
- [ ] T027 Run the formatters and linters: `uv run invoke format`, `uv run invoke lint`, `uv run ruff check . --exclude python_sdk`, `uv run ruff format --check --exclude python_sdk .` and `uv run invoke docs.validate`. Fix every finding in the changed files without adding a suppression (`.agents/rules/python-typing.md`).
- [ ] T028 Optionally, run quickstart.md step 4 on a development instance to record the absolute task-run count of one deletion run (spec Assumptions). Add it to `pr-notes.md`.
- [ ] T029 Remind the user to run `/pre-ci` before pushing. The pull request targets `stable` and references #11165 and IFC-3477. Its description includes `pr-notes.md` and the guard results from T014 and T017.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Phase 1, and blocks US1 and US2.
- **US1 (Phase 3)**: depends on Phase 2.
- **US2 (Phase 4)**: depends on US1. It adds cases to US1's list and relies on T012.
- **US3 (Phase 5)**: depends on Phase 1 only. Its tests are in a different file from US1's. Its production tasks (T020, T021) edit `gather.py`, so do not run them at the same time as T012.
- **US4 (Phase 6)**: depends on Phase 1 only. T024 adds the counts once T014 and T017 are done.
- **Polish (Phase 7)**: depends on all stories.

### Within Each User Story

- Write the tests and see them fail first. T011 is the exception: it passes on today's code because it guards behavior that must not change.
- Production change next, then the run, then the guard check.

### Parallel Opportunities

- T018 and T019 edit the same file, so only T018 is marked [P]: it can run beside US1's tasks. Write T019 after T018.
- T023 and T024 can run in parallel with each other and with US1's tasks.
- US3's tests (T018, T019) can be written while US1's tests (T008 to T011) are written, since they are in different files.

---

## Parallel Example: User Story 3 with User Story 1

```bash
# While T008–T011 are written in test_reconcile_task_runs.py:
Task: "T018 Add the FR-004 warning test in backend/tests/component/computed_attribute/test_gather.py"
Task: "T023 Create changelog/11165.fixed.md with towncrier create"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 and Phase 2.
2. Phase 3: the `branch_deleted` count test, the automation test and the decorator removal.
3. Stop and validate: the count is equal with 2 and with 10 branches, and the guard fails when the decorator is put back. This alone stops the database growth that the issue reports.

### Incremental Delivery

1. US1, the MVP: branch deletions.
2. US2: the schema-update and transform cases, which are tests only.
3. US3: the warning and the failure name the branch.
4. US4: the changelog and the release-note details.
5. Polish, then one pull request against `stable`.

---

## Notes

- Cite code by `module::symbol`, never by line number.
- No issue numbers, ticket numbers or spec vocabulary in test names, docstrings or comments.
- Commit after each phase. Use the conventional commit format from `dev/guidelines/git-workflow.md`.
