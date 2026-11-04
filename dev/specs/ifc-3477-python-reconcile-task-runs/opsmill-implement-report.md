# Implementation report: fixed number of task runs per Python computed-attribute reconcile

- Feature: one branch deletion, schema update or Python transform change records the same number of task runs whatever the number of open branches
- Spec directory: `dev/specs/ifc-3477-python-reconcile-task-runs`
- Base commit: `dadd46e4f9`
- Head commit: the commit that adds this report, on top of `6191d727a`
- Status: DONE. 28 of 29 tasks are complete. T028 is optional and was skipped (see "Tasks not completed").
- Wall-clock time: about 50 minutes for the 7 chunks and the review.

## Chunk ledger

| Chunk | Tasks | Done / partial / blocked | Commits |
|-------|-------|--------------------------|---------|
| Phase 1: Setup | T001–T002 | 2 / 0 / 0 | `52786a5e3` |
| Phase 2: Test infrastructure | T003–T007 | 5 / 0 / 0 | `dc8621c7a` |
| Phase 3: User story 1 | T008–T014 | 7 / 0 / 0 | `8aa99a355`, `fa27d8bfe` |
| Phase 4: User story 2 | T015–T017 | 3 / 0 / 0 | `9f6057531` |
| Phase 5: User story 3 | T018–T022 | 5 / 0 / 0 | `5df08f85e`, `5da10321c` |
| Phase 6: User story 4 | T023–T024 | 2 / 0 / 0 | `d3185bb0b` |
| Phase 7: Polish | T025–T029 | 4 / 0 / 0, T028 skipped | `7829810bb`, plus the report commit |
| Review fixes | n/a | n/a | `6191d727a` |

Decisions and surprises that the chunk subagents reported:

- Phase 1: neither #11093 nor #11095 has merged into `stable`, so the branch was not rebased. `origin/stable` has one newer commit (#11431), which changes only `test_permissions_on_branch.py`.
- Phase 2:
  - The counting helper reads the captured events from Prefect's private `EventsWorker._client` attribute. Prefect's own test fixtures read it the same way.
  - The branch delete uses `config.SETTINGS.database.query_size_limit` as its batch size.
- Phase 3:
  - The automation test (FR-002) gives a branch named `repo-commit-changed` its own automation by setting `repo01`'s commit to `commit02` on that branch. It asserts each automation's branch filter as well as its name.
  - The only caller of `gather_python_transform_attributes` is the `gather_trigger_computed_attribute_python` task, so `get_run_logger()` still runs inside a task run.
- Phase 5: today's code raises `LookupError("Unable to find the peer")`, as research R6 expected. pytest 9.0.3 includes `__notes__` in `pytest.raises(match=...)`.
- Phase 7: the untracked `repositories/` directory that the tests leave at the repository root makes `invoke lint` and the whole-repository `ruff check` fail locally. Every finding is in that directory. CI does not see it. It is still untracked.

## Tasks not completed

- T028 (optional): measure the absolute task-run count of one deletion run on a development instance. It was skipped because it needs `uv run invoke dev.start` with a full Docker build. `pr-notes.md` says that this count is not known yet.

## Local-pass evidence

The environment for every row was the backend component test stack started by testcontainers on local Docker: Neo4j 2026.05.0, Prefect 3.8.6, Redis 8.4.0, Python 3.14.

| Test id | Type | Run command | Passed at (ISO 8601) | Verbatim pass line |
|---------|------|-------------|----------------------|--------------------|
| `backend/tests/component/computed_attribute/test_reconcile_task_runs.py::TestReconcileTaskRuns::test_task_run_count_does_not_depend_on_branch_count[branch_deleted]` | component | `uv run pytest backend/tests/component/computed_attribute/test_reconcile_task_runs.py -v -s -p no:cacheprovider` | 2026-11-04T21:29:08+00:00 | `...::test_task_run_count_does_not_depend_on_branch_count[branch_deleted] PASSED` |
| `...::test_task_run_count_does_not_depend_on_branch_count[schema_updated]` | component | same | 2026-11-04T21:29:08+00:00 | `...::test_task_run_count_does_not_depend_on_branch_count[schema_updated] PASSED` |
| `...::test_task_run_count_does_not_depend_on_branch_count[transform_created]` | component | same | 2026-11-04T21:29:08+00:00 | `...::test_task_run_count_does_not_depend_on_branch_count[transform_created] PASSED` |
| `...::test_task_run_count_does_not_depend_on_branch_count[transform_updated]` | component | same | 2026-11-04T21:29:08+00:00 | `...::test_task_run_count_does_not_depend_on_branch_count[transform_updated] PASSED` |
| `...::test_task_run_count_does_not_depend_on_branch_count[transform_deleted]` | component | same | 2026-11-04T21:29:08+00:00 | `...::test_task_run_count_does_not_depend_on_branch_count[transform_deleted] PASSED` |
| `...::TestReconcileTaskRuns::test_branch_deletion_keeps_the_automations_a_full_reconcile_builds` | component | same | 2026-11-04T21:29:08+00:00 | `...::test_branch_deletion_keeps_the_automations_a_full_reconcile_builds PASSED` |
| `backend/tests/component/computed_attribute/test_gather.py::test_gather_warns_with_branch_when_transform_is_missing` | component | `uv run pytest backend/tests/component/computed_attribute/test_gather.py -v -p no:randomly` | 2026-11-04T21:37:02+00:00 | `backend/tests/component/computed_attribute/test_gather.py::test_gather_warns_with_branch_when_transform_is_missing PASSED [ 60%]` |
| `backend/tests/component/computed_attribute/test_gather.py::test_gather_failure_names_the_branch` | component | same | 2026-11-04T21:37:02+00:00 | `backend/tests/component/computed_attribute/test_gather.py::test_gather_failure_names_the_branch PASSED [ 70%]` |

Each new test was shown to fail first:

- Before the fix, the `branch_deleted` count test failed with 26 task runs at 10 branches against 10 at 2 branches.
- With the decorator put back after the fix, all 5 count cases failed (`5 failed, 1 passed`).
- Both `test_gather.py` tests failed on the old warning text and on the missing note.

The full suites passed after all changes:

- `uv run pytest backend/tests/component/computed_attribute/ -v`: `40 passed, 18 warnings in 520.88s`, finished at 2026-11-04T21:48:26Z. The baseline was 32 passed.
- `uv run pytest backend/tests/functional/computed_attributes/ -v`: `13 passed, 17 warnings in 327.62s`, finished at 2026-11-04T21:45:13Z. The baseline was 13 passed.

The review fixes in `6191d727a` change only the changelog fragment and `pr-notes.md`, so no test was run again after them.

## Review findings

Three review agents read the diff: code and error handling, tests, and comments and simplification. None found a critical or high-severity defect.

| Severity | File | Finding | Outcome |
|----------|------|---------|---------|
| Medium | `changelog/11165.fixed.md` | With its default, the flush command keeps the last 30 days. The entry did not say that the command deletes the finished runs of every flow. | Fixed in `6191d727a` |
| Medium | `pr-notes.md` | The notes did not say that the records of the last 30 days stay with the default. | Fixed in `6191d727a` |
| Medium | `test_gather.py`, FR-005 test | The run's state message is built from `str(exc)`, so it does not include the note that names the branch. Only the logged traceback does. | Deferred. Research R4 and the contract record this as accepted, and User Story 3 states the limit. |
| Low to medium | `test_reconcile_task_runs.py` | `> 0` does not assert the exact count (4 or 3). | Deferred |
| Low | `test_reconcile_task_runs.py`, FR-002 test | It compares against a literal set and checks only the `computed_attr_python` automations, not the `computed_attr_python_query` ones. | Deferred |
| Low | `test_reconcile_task_runs.py`, event fixture | It does not call `AssertingPassthroughEventsClient.reset()`, and it sets the override to `None` instead of restoring the earlier value. | Deferred |
| Low | `test_reconcile_task_runs.py` | It reads Prefect's private `EventsWorker._client` attribute, so a Prefect upgrade can break it. | Deferred |
| Low | `test_reconcile_task_runs.py` | The case field `count_task_runs` has the same name as the module-level helper. | Deferred |
| Low | `test_reconcile_task_runs.py` | `create_open_branch` only forwards to `create_branch`, and the automation-prefix logic is repeated. | Deferred |
| Low | `pr-notes.md` | The intro claimed that every statement comes from the spec. | Fixed in `6191d727a` |
| Low | `pr-notes.md` | It names Prefect 3.8.6 but links only to the 3.7.5 sources. | Deferred |
| Low | `guard-results.md` | It cites "research R2" without a link. | Deferred |

## Decisions made without asking

- One chunk per phase heading in `tasks.md`. No phase needed splitting.
- T001 was resolved by the orchestrator before Phase 1 was dispatched, because it is a read-only check.
- T028 was skipped because it is optional and needs a full development instance.
- The FR-005 state-message finding was not fixed, because the spec accepts that limit. Changing it would need a new error message or type, which the PRD rules out.
- The orchestrator fixed the medium documentation findings itself. It left the low test findings for the author to decide.

## Next steps

1. Run `/pre-ci` before pushing.
2. Open the pull request against `stable`, referencing #11165 and IFC-3477. Include `pr-notes.md` and the guard results from `guard-results.md` in the description.
3. Decide whether to apply the deferred low findings, mainly asserting the exact counts and resetting the Prefect event client in the teardown.
4. Optionally, run quickstart.md step 4 (T028) to record the absolute task-run count on a running instance.
