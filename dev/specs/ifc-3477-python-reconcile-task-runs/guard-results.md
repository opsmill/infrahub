# Guard results for the task-run count test

These counts come from `test_reconcile_task_runs.py::TestReconcileTaskRuns::test_task_run_count_does_not_depend_on_branch_count[branch_deleted]`. Each count is the number of task runs in one `computed-attribute-setup-python` run started by a branch deletion. The column headings give the number of open branches besides the default branch while the run executes. The tests ran against testcontainers (Neo4j 2026.05.0, Prefect 3.8.6, Redis 8.4.0) on 2026-11-04.

| Code | 2 branches | 10 branches | Test result |
|------|------------|-------------|-------------|
| Before the fix, with the `@task` decorator on `gather_python_transform_attributes` | 10 | 26 | Fails (`26 != 10`) |
| After the fix, without the decorator | 4 | 4 | Passes |

- Before the fix, each branch adds 2 task runs, including the default branch: 4 + 2 × 3 = 10 and 4 + 2 × 11 = 26. The reconcile runs the gather twice, and each gather run creates one task run per branch.
- After the fix, the run holds 2 gather task runs and 2 trigger-setup task runs, as research R2 predicts.
- The guard check put the decorator back temporarily, and the test failed with the counts 10 and 26. The decorator was then removed again.
