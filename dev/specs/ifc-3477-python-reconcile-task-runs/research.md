# Research: One branch deletion records the same number of task runs whatever the number of open branches

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Each entry records a decision, why it was taken, and the alternatives set aside. Code locations are cited as `module::symbol` on `stable` at `5ca7c05db8`.

## R1. How the per-branch gather stops recording task runs

**Decision**: Remove the `@task` decorator from `backend/infrahub/computed_attribute/gather.py::gather_python_transform_attributes`, so it becomes a plain `async` function that `gather_trigger_computed_attribute_python` calls once per branch. `gather_trigger_computed_attribute_python` keeps its `@task` decorator and its grouping logic.

**Rationale**:

- Each call of a Prefect task records one task run and about 3 task-run states in the task manager database. A plain function call records nothing.
- `get_run_logger()` inside the plain function returns the logger of the enclosing task run, `gather-trigger-computed-attribute-python`, so the warning still reaches the flow-run log.
- The only callers of `gather_python_transform_attributes` are inside `gather.py`. No caller uses a task-only attribute (`.fn`, `.with_options`, `.submit`).
- All three flows that gather Python computed attributes go through `gather_trigger_computed_attribute_python`:
  - `computed_attribute/tasks.py::computed_attribute_setup_python`, directly and through `_reconcile_python_computed_attribute_automations`;
  - `computed_attribute/tasks.py::process_transform_lifecycle`, through `_reconcile_python_computed_attribute_automations`;
  - `trigger/tasks.py::trigger_configure_all`, which `infrahub upgrade` runs.

  One change covers FR-001 and FR-003.

**Alternatives considered**:

- Gather every branch in one task call, as the HFID, display-label and profile gathers do. The result is the same: one task run per gather. It needs a larger rewrite of the gather, and the PRD keeps the grouping logic unchanged.
- Gather once per flow run and pass the result to the reconcile. This lowers the number of graph database reads, which the PRD puts out of scope. It also changes the reconcile's interface.
- Skip the task call on branches with no Python computed attribute. A branch that has one still records a task run, so the count still depends on the number of open branches.

## R2. Task runs per run after the change

**Decision**: Read the fixed count from the code. Tests compare counts across branch numbers rather than pinning an absolute number.

| Run | Task runs after the change | Today |
|-----|----------------------------|-------|
| `computed-attribute-setup-python` | 2 × `gather-trigger-computed-attribute-python` + 2 × `trigger-setup` = 4 | 4 + 2 per branch that is not global |
| `computed-attribute-process-transform-lifecycle` (any action) | 1 × gather + 2 × `trigger-setup` = 3, plus any task the recompute submission records on create or update | 3 + 1 per branch, plus the same recompute tasks |
| `trigger-configure-all` | 1 × gather + the other gathers + 1 × `trigger-setup` | the same + 1 per branch |

**Rationale**: `add_tags`, `wait_for_schema_to_converge` and `get_repositories_commit_per_branch` are plain functions, and `trigger/setup.py::setup_triggers` is the only task the reconcile calls besides the gather. The testing principle in the PRD says not to assert on which functions are Prefect tasks. A comparison between 2 and 10 branches holds without pinning the number.

**Alternatives considered**: Assert `== 4`. This ties the test to the current number of tasks in the flow, so any unrelated task added to the flow would break it.

## R3. How a component test counts the task runs of one flow run

**Decision**: Capture the Prefect events that the flow run emits, in-process, and count the distinct task-run resources related to that flow run. Install Prefect's `prefect.events.clients.AssertingPassthroughEventsClient` as the events worker for the test, through `monkeypatch.setattr(EventsWorker, "instance", ...)`, the way `prefect/testing/fixtures.py::asserting_and_emitting_events_worker` does. Then call `worker.wait_until_empty()` before counting. Get the flow-run id from the state that `return_state=True` returns.

**Rationale**:

- In Prefect 3.8.6, the client does not write task runs through the API. It emits task-run state events, and the server service `prefect/server/services/task_run_recorder.py` writes the rows later. A `read_task_runs()` call right after the flow returns can miss rows, so a server-side count would be flaky.
- The passthrough client records every event and still forwards it to the server, so the rest of the test stack behaves as it does today.
- `monkeypatch` restores `EventsWorker.instance` after the test. This follows the testing rule against leaking process-global state.
- The count is the number of task-run rows that the task manager writes for that run, the measure that the spec's success criteria use.

**Alternatives considered**:

- Count with `read_task_runs()` on the server and poll until the count stops changing. This still depends on timing, and the testing guideline forbids assertions that depend on elapsed time.
- `AssertingEventsClient`, which does not forward. It would stop the server from receiving task-run events that other parts of the stack may read during the test.
- Count calls to the gather function. This asserts on which functions are tasks, which the PRD's testing principle rules out.

## R4. How a failure on one branch names the branch (FR-005)

**Decision**: In `gather_trigger_computed_attribute_python`, wrap only the call to `gather_python_transform_attributes` for one branch in `try`/`except Exception as exc`. Add a note that names the branch with `exc.add_note(...)`, then re-raise with a bare `raise`. The note reads: `Gathering the Python computed attributes failed on branch '<branch>'`.

**Rationale**:

- The PRD asks for no new error type: "the existing failure names the branch". `add_note` (PEP 678) keeps the type, the message and the traceback of the original exception, and attaches the branch to it.
- `dev/guidelines/backend/exceptions.md` allows a broad catch only to add context and re-raise. A bare `raise` keeps the traceback. Ruff's `BLE001` does not flag a handler that re-raises.
- Prefect logs the failure with its traceback, and since Python 3.11 a formatted traceback includes the notes. The flow-run log therefore names the branch.
- Since pytest 8.0, the `match` of `pytest.raises` also matches the notes, so the test asserts on the branch without patching anything.
- Today's failures do not name the branch. For example, `core/relationship/model.py::RelationshipManager.get_peer` raises `LookupError("Unable to find the peer")` when a transform's query or repository is missing on the branch. Before this change, only the name of the per-branch task run told the operator which branch had failed.

**Alternatives considered**:

- `log.error(...)` naming the branch, then `raise`. The branch then appears in a separate log line but does not travel with the exception. The test would need to patch `get_run_logger`.
- `raise SomeError(f"... {branch}") from exc`. This changes the type of the error, against the PRD.
- Continue with the other branches and report the failed one. The PRD puts this out of scope.

## R5. Wording of the missing-transform warning (FR-004)

**Decision**: Change the message to: `The transform <transform> is assigned to a computed attribute on branch '<branch>' but the transform could not be found on that branch.`

**Rationale**: The message names the branch and the transform, as FR-004 requires. It states what the code observed, which is that the query on that branch returned no transform with that name, following `exceptions.md` §"Error messages state what was observed, not a guessed cause". The previous message said "in the database", which is not what the code checks: the query is scoped to one branch.

## R6. Test fixtures for the warning and the failure

**Decision**:

- FR-004: reuse `car_person_schema_computed_attr` without `transform01`. The computed attribute names `transform01`, which does not exist, so the gather on `main` logs the warning. Capture it with `caplog` by patching `infrahub.computed_attribute.gather.get_run_logger`, the one exception to the mocking rule that `.agents/rules/testing-python.md` allows. Call `gather_trigger_computed_attribute_python.fn(db=db)`.
- FR-005: create a branch, then delete on that branch only the GraphQL query that `transform01` reads, with `Node.delete`, which does not run the mutation-level delete checks. The gather of that branch then raises `LookupError` from `get_peer(raise_on_error=True)`. Assert `pytest.raises(LookupError, match=...)` on the branch name in the note. During implementation, confirm the exact exception type before pinning it.

**Rationale**: Both fixtures build the condition from real data and need no mock. The existing gather tests in `backend/tests/component/computed_attribute/test_gather.py` already use these schema and transform fixtures.

**Alternatives considered**: A test double for the gather. The project bans mocking, and a double would not prove that the real failure carries the branch.

## R7. What the changelog entry can state (FR-006)

**Decision**: Write a `fixed` fragment named `11165.fixed.md`, created with `towncrier create`. It states:

- A branch deletion, a schema update and a Python transform change no longer record task runs in proportion to the number of open branches.
- `infrahub tasks flush flow-runs` deletes completed, failed and cancelled flow runs older than `--days-to-keep` days (30 by default), together with their task runs, task-run states and logs.
- PostgreSQL reuses the freed space for new rows but does not return it to the operating system. `VACUUM FULL` returns it and locks each table while it runs.

**Rationale**: Each statement is confirmed by the sources listed in the spec's [Resolved Clarifications](spec.md#resolved-clarifications):

- the Prefect 3.7.5 and 3.8.6 cascade rules and the background deletion of logs;
- `task_manager/flow_run/retention.py::FlowRunRetention.purge`;
- the PostgreSQL documentation.

Before writing the fragment, read the `creating-changelog-entries` skill, which sets the wording conventions.

## R8. Documentation updates

**Decision**: Do not change `dev/knowledge/backend/computed-attributes.md`. Its description of the reconcile, "one gather builds both trigger lists and they are applied under a single trigger-registry lock", stays true.

**Note for the extraction phase**: `dev/guides/backend/creating-async-tasks.md` recommends tasks "for granular tracking" and does not warn that a task called in a loop records one task run, with its states, per item on every run. That would be a candidate rule for `speckit-opsmill-extract`. It is not part of this change, because the PRD limits documentation to the changelog and the computed-attributes knowledge page.

## R9. Delivery and merge conflicts

**Decision**: Branch from `stable` (`5ca7c05db8`) and open the pull request against `stable`.

- #11095, open, edits the body of `gather_python_transform_attributes`. If it merges first, rebase and keep its skip for a branch with no repository commit. Only the decorator goes.
- #11093, open, edits the first lines of `computed_attribute_setup_python`. The two changes touch different lines.
- `develop` keeps the per-branch task in a loop whose grouping logic differs. During the merge from `stable` into `develop`, remove the decorator there too and keep `develop`'s grouping.

## R10. Spec-kit agent context file

**Decision**: Do not run the `speckit-agent-context-update` step. The step would append a managed block to the committed `CLAUDE.md`, which has no `<!-- SPECKIT START -->` marker, and no earlier spec on `stable` added one.
