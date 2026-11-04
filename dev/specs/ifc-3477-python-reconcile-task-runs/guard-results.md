# Guard results for the task-run count test

These counts come from `test_reconcile_task_runs.py::TestReconcileTaskRuns::test_task_run_count_does_not_depend_on_branch_count[branch_deleted]`. Each count is the number of task runs in one `computed-attribute-setup-python` run started by a branch deletion. The column headings give the number of open branches besides the default branch while the run executes. The tests ran against testcontainers (Neo4j 2026.05.0, Prefect 3.8.6, Redis 8.4.0) on 2026-11-04.

| Code | 2 branches | 10 branches | Test result |
|------|------------|-------------|-------------|
| Before the fix, with the `@task` decorator on `gather_python_transform_attributes` | 10 | 26 | Fails (`26 != 10`) |
| After the fix, without the decorator | 4 | 4 | Passes |

- Before the fix, each branch adds 2 task runs, including the default branch: 4 + 2 × 3 = 10 and 4 + 2 × 11 = 26. The reconcile runs the gather twice, and each gather run creates one task run per branch.
- After the fix, the run holds 2 gather task runs and 2 trigger-setup task runs, as research R2 predicts.
- The guard check put the decorator back temporarily, and the test failed with the counts 10 and 26. The decorator was then removed again.

## Task-run counts for every event that runs the reconcile

These counts come from the other parametrized cases of `test_task_run_count_does_not_depend_on_branch_count`. Each case runs one flow on the default branch. The `schema_updated` case runs `computed-attribute-setup-python` with the schema update event. The `transform_*` cases run `computed-attribute-process-transform-lifecycle` for `transform01` with the matching action. The tests ran against the same testcontainers stack on 2026-11-04.

| Case | Before the fix, 2 branches | Before the fix, 10 branches | After the fix, 2 branches | After the fix, 10 branches |
|------|----------------------------|-----------------------------|---------------------------|----------------------------|
| `schema_updated` | 10 | 26 | 4 | 4 |
| `transform_created` | 6 | 14 | 3 | 3 |
| `transform_updated` | 6 | 14 | 3 | 3 |
| `transform_deleted` | 6 | 14 | 3 | 3 |

- Before the fix, `schema_updated` adds 2 task runs per branch, like `branch_deleted`, because it also runs the gather twice. The `transform_*` cases add 1 task run per branch, including the default branch: 3 + 3 = 6 and 3 + 11 = 14. They run the gather once.
- After the fix, `schema_updated` holds 2 gather task runs and 2 trigger-setup task runs. The `transform_*` cases hold 1 gather task run and 2 trigger-setup task runs. Both match research R2. The recompute submissions go to the `WorkflowRecorder`, so they add no task runs.
- The guard check put the decorator back temporarily, and all 5 cases failed: `branch_deleted` and `schema_updated` with 10 and 26, and the 3 `transform_*` cases with 6 and 14. The decorator was then removed again.
