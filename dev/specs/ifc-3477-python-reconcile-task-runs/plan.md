# Implementation Plan: One branch deletion records the same number of task runs whatever the number of open branches

**Branch**: `python-reconcile-task-runs-ifc-3477` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3477-python-reconcile-task-runs/spec.md`

## Summary

Each run of `computed-attribute-setup-python` records two task runs per open branch, because the Python computed-attribute gather calls a Prefect task once per branch. Branch deletions run this flow thousands of times a day on some instances, and in the dump described in [#11165](https://github.com/opsmill/infrahub/issues/11165) the flow holds 89% of all task runs.

The fix removes the `@task` decorator from the per-branch gather, so a whole gather records one task run whatever the number of branches. A warning about a missing transform names the branch, and a failure on one branch adds the branch to the exception with a PEP 678 note. The grouping logic, the flows and the automations they build stay as they are. Component tests count the task runs of a run with 2 branches and with 10, and check the automations after a deletion. The decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (backend)

**Primary Dependencies**: Prefect 3.8.6 (task manager client and server), Neo4j through Infrahub's database layer

**Storage**: The task manager's PostgreSQL database, written by the Prefect server. This change writes fewer rows to it and adds no table or column.

**Testing**: pytest 9.0 component tests in `backend/tests/component/computed_attribute/`, on `TestInfrahubAppWithoutLocalWorkflow`. That base class requests the module-scoped `prefect` fixture, so its flows run against the session-scoped Prefect server container, not the in-process test harness (`dev/knowledge/backend/testing.md` §"A Component Test Process Talks to Two Prefect Servers"). The existing integration Docker tests for computed attributes keep running.

**Target Platform**: Infrahub task workers (Linux containers)

**Project Type**: Web service backend (the `backend/` package)

**Performance Goals**: The number of task runs in one `computed-attribute-setup-python` run does not depend on the number of open branches (FR-001). 100 deletions with 75 open branches record at most 770 task runs, against about 15,400 today (SC-001).

**Constraints**:

- The automations built after a deletion are the same as today (FR-002).
- The flows' parameters and the reconcile's lock do not change.
- No new exception type is added.
- The fix targets `stable` for a 1.11 patch release.

**Scale/Scope**: Two production functions in one module (`backend/infrahub/computed_attribute/gather.py`), one new component test module, two new cases in an existing test module, and one changelog fragment.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|-----------|------------|--------|
| I. Schema-Driven Integrity | No schema, generated file or migration changes. | Pass |
| II. Branch-Safe by Default | The reconcile still gathers every branch that is not global and builds the same per-branch automations. FR-002 and SC-002 are covered by a test that deletes a branch owning automations. | Pass |
| III. Type Safety & Explicit Contracts | The signatures do not change. The plain function keeps its type hints. No API contract changes. | Pass |
| IV. Test Discipline | Component tests cover FR-001 to FR-005. The existing integration Docker tests for computed attributes keep passing, as the principle requires for computed attributes and triggered actions. No E2E test, because nothing changes in the web interface. | Pass |
| V. Query Performance & Efficiency | No query changes. The task manager writes about 3 state rows and 1 task-run row fewer per branch per gather. | Pass |
| VI. Security & Input Boundaries | No input boundary changes. The added note names a branch, which the operator already views in the task log. | Pass |
| VII. Simplicity & Maintainability | The change removes a decorator and adds a `try`/`except` that re-raises. It adds no abstraction or configuration. | Pass |
| Documentation requirements | A `fixed` changelog fragment (FR-006). `dev/knowledge/backend/computed-attributes.md` stays accurate, so it is not changed (research R8). | Pass |

Post-design re-check: the design artifacts below add no new entity, interface, dependency or migration. All gates still pass.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3477-python-reconcile-task-runs/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R10
├── data-model.md        # Phase 1: existing entities and the invariant on task runs
├── quickstart.md        # Phase 1: how to validate the change
├── contracts/
│   └── task-runs-and-messages.md   # What an operator observes in the task manager
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/computed_attribute/
└── gather.py                      # modified: per-branch gather becomes a plain function;
                                   #   warning names the branch; failure on one branch is re-raised
                                   #   with a note naming it

backend/tests/component/computed_attribute/
├── test_gather.py                 # modified: FR-004 warning text, FR-005 failure on one branch
└── test_reconcile_task_runs.py    # new: FR-001, FR-002, FR-003 (task-run counts, automations)

changelog/
└── 11165.fixed.md                 # new: FR-006, created with `towncrier create`
```

**Structure Decision**: The change stays inside the existing `computed_attribute` package and its component test directory. The new test module sits beside `test_scoped_recompute_python.py` and reuses `tests/component/computed_attribute/_base.py`. It reuses the `ScopedRecomputeTestBase` fixtures (app, workflow recorder, context) and `create_transform01`.

## Design

### Production change (`backend/infrahub/computed_attribute/gather.py`)

1. **`gather_python_transform_attributes`**: remove the `@task(...)` decorator. Remove the `task` and `NONE` imports only if no other decorator in the module still uses them. `gather_trigger_computed_attribute_jinja2` and `gather_trigger_computed_attribute_python` stay tasks, so the imports stay. Keep the signature, the body and `get_run_logger()`.
2. **Missing-transform warning**: replace the message with the wording in research R5: `No Python transform named '<transform>' was found on branch '<branch>', but a computed attribute is assigned to it.`
3. **`gather_trigger_computed_attribute_python`**: wrap only the per-branch call:

   ```python
   try:
       computed_attributes = await gather_python_transform_attributes(
           db=db, branch_name=branch.name, repositories=repositories
       )
   except Exception as exc:
       exc.add_note(f"Gathering the Python computed attributes failed on branch '{branch.name}'")
       raise
   ```

   The grouping loop after it does not change.
4. **No other production file changes.** `computed_attribute/tasks.py` and `trigger/tasks.py` keep calling `gather_trigger_computed_attribute_python` as they do today.

### Tests

The tests follow `.agents/rules/testing-python.md`: exact assertions, a positive count, no mocks except the allowed `get_run_logger` patch, and a guard shown to fail when the change is reverted.

- **`test_gather.py`, FR-004**: request `car_person_schema_computed_attr` and `register_core_models_schema`, and not `transform01` (research R6). Call `gather_trigger_computed_attribute_python.fn(db=db)` with `infrahub.computed_attribute.gather.get_run_logger` patched to a stdlib logger. Assert the exact warning text from `caplog`.
- **`test_gather.py`, FR-005**: with `transform01` loaded, create a branch. Load `query01` on that branch, delete it there with `Node.delete`, and call `gather_trigger_computed_attribute_python(db=db)` inside `pytest.raises(LookupError, match=...)`. pytest matches against the message followed by the notes, one per line, so anchor the whole text: `^Unable to find the peer\nGathering the Python computed attributes failed on branch '<name>'$`. Pin the exception type and message only after confirming them, as research R6 says.
- **Deleting a branch in a test**: `Branch.delete` raises `NotImplementedError`. Delete with `BranchDataDeleter(db=db, batch_size=...).delete(branch=branch, user_id=...)`, then call `registry.purge_inactive_branches(db=db)` before running the flow, because nothing in the test app purges the registry (research R6).
- **`test_reconcile_task_runs.py`** (new), a class on `ScopedRecomputeTestBase` with `transform01` loaded on `main` and `CAR_PERSON_PYTHON_SCHEMA` loaded once per class:
  - A class-scoped fixture installs `AssertingPassthroughEventsClient` with `EventsWorker.set_client_override(...)`. Its `finally` drains that worker and resets the override (research R3). A helper runs a flow with `return_state=True`, then calls `await asyncio.to_thread(worker.wait_until_empty)`. It returns the number of distinct `prefect.task-run.*` resources whose related resources include that flow run.
  - Cases are a dataclass list whose first field is `name`:
    - `branch_deleted`: `computed_attribute_setup_python(branch_name=<deleted>, event_name=BranchDeletedEvent.event_name)`, after deleting one branch;
    - `schema_updated`: `computed_attribute_setup_python(branch_name="main", event_name=SchemaUpdatedEvent.event_name)`;
    - `transform_created`, `transform_updated`, `transform_deleted`: `process_transform_lifecycle` with each action. Follow `test_transform_lifecycle_recompute.py`, which already runs this flow for each action.
  - Order of measurement: a class-scoped fixture `counts_with_2_branches` creates 2 branches that are not global and runs every case once. A second class-scoped fixture, `counts_with_10_branches`, depends on the first, creates enough branches to reach 10 and runs every case again. The `branch_deleted` case deletes a fresh branch each time, so each fixture creates one extra branch for it to delete.
  - **FR-001 and FR-003**: a test parametrized over the cases asserts that `counts_with_2_branches[case.name] == counts_with_10_branches[case.name]`, and that the count is greater than zero.
  - **FR-002**, in a method that runs after the count test:
    - Add the computed attribute only on one branch, as `test_gather_trigger_computed_attribute_python_only_on_branch` does, and run the reconcile.
    - Assert the literal names of the `COMPUTED_ATTR_PYTHON` automations, which are built as `<type>::<branch>::TestCar_<attribute>`, the way `test_transform_lifecycle_recompute.py::test_delete_drops_removed_transform_automation_but_keeps_others` does.
    - Delete that branch, purge the registry and run the setup flow for the deletion.
    - Assert the literal names again: the branch's automation is gone and the `main` automations remain. Assert also that no name of either type contains the deleted branch.
  - Teardown deletes the automations the class created, following `dev/knowledge/backend/testing.md` §"Prefect Server State Outlives the Test Class".
  - Show that the guard works: with the `@task` decorator restored, the FR-001 and FR-003 assertions fail. Record that in the pull request, together with the absolute count observed on a running instance (spec Assumptions).

### Changelog (FR-006)

Create `changelog/11165.fixed.md` with `towncrier create`, following the `creating-changelog-entries` skill: one sentence that states the fix and names `infrahub tasks flush flow-runs`. Put the details listed in research R7 in the pull request description.

## Delivery

- Open the pull request against `stable`. It references [#11165](https://github.com/opsmill/infrahub/issues/11165) and [IFC-3477](https://opsmill.atlassian.net/browse/IFC-3477).
- The interaction with the open pull requests #11093 and #11095, and with the merge into `develop`, is in research R9.

## Complexity Tracking

No constitution violations to justify.
