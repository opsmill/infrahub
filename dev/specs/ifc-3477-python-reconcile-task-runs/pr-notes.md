# Release-note details for the pull request description

The statements in the first two sections come from the spec's [Resolved Clarifications](spec.md#resolved-clarifications), and link to the source that section cites. The counts in the last section come from the test runs recorded in [guard-results.md](guard-results.md).

## Removing the task-manager records already written

- `infrahub tasks flush flow-runs` deletes every flow run, of any flow, that is in a completed, failed or cancelled state and that started more than `--days-to-keep` days ago. `--days-to-keep` is 30 by default ([cli/tasks.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/cli/tasks.py#L68-L87), [retention.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/task_manager/flow_run/retention.py)).
  - The command does not select the runs of `computed-attribute-setup-python` only.
  - With the default of 30 days, the records written in the last 30 days stay. To remove them, the operator passes a smaller `--days-to-keep`, which also deletes the history of every other flow for that period.
- Deleting a flow run also deletes the records attached to it, in Prefect 3.7.5 and in Prefect 3.8.6:
  - its task runs and the states of each task run, through `ON DELETE CASCADE` foreign keys ([orm_models.py at 3.7.5](https://github.com/PrefectHQ/prefect/blob/3.7.5/src/prefect/server/database/orm_models.py));
  - its logs, through a background job that the delete endpoint of the Prefect API schedules ([api/flow_runs.py at 3.7.5](https://github.com/PrefectHQ/prefect/blob/3.7.5/src/prefect/server/api/flow_runs.py)).

## Disk space after the deletion

- PostgreSQL reuses the space of the deleted rows for new rows in the same table, but does not return it to the operating system. Vacuuming, including autovacuum, returns space only when the pages at the end of a table are empty ([PostgreSQL documentation, Recovering Disk Space](https://www.postgresql.org/docs/current/routine-vacuuming.html#VACUUM-FOR-SPACE-RECOVERY)).
- `VACUUM FULL` returns the space to the operating system ([PostgreSQL documentation, VACUUM](https://www.postgresql.org/docs/current/sql-vacuum.html)):
  - it takes an `ACCESS EXCLUSIVE` lock on each table while it rewrites that table;
  - it needs free disk space about the size of that table, because it writes a new copy of the table and keeps the old copy until it finishes.

## Task runs recorded by one reconcile, before and after the fix

Each count is the number of task runs in one flow run on the default branch, with 2 or 10 open branches besides the default branch. The counts come from `test_task_run_count_does_not_depend_on_branch_count` in `backend/tests/component/computed_attribute/test_reconcile_task_runs.py`, run on 2026-11-04 against Neo4j 2026.05.0, Prefect 3.8.6 and Redis 8.4.0. The "before" counts were taken with the `@task` decorator put back on `gather_python_transform_attributes`. See [guard-results.md](guard-results.md).

| Event | Flow | Before, 2 branches | Before, 10 branches | After, 2 branches | After, 10 branches |
|-------|------|--------------------|---------------------|-------------------|--------------------|
| Branch deleted | `computed-attribute-setup-python` | 10 | 26 | 4 | 4 |
| Schema updated | `computed-attribute-setup-python` | 10 | 26 | 4 | 4 |
| Python transform created | `computed-attribute-process-transform-lifecycle` | 6 | 14 | 3 | 3 |
| Python transform updated | `computed-attribute-process-transform-lifecycle` | 6 | 14 | 3 | 3 |
| Python transform deleted | `computed-attribute-process-transform-lifecycle` | 6 | 14 | 3 | 3 |

- Before the fix, a branch deletion or a schema update added 2 task runs per branch, the default branch included, because the flow gathers the Python computed attributes twice. A Python transform change added 1 task run per branch, because that flow gathers once.
- After the fix, the count does not depend on the number of branches.
- In the test, the recomputes that a run submits go to a recorder, so they add no task runs. In production, each submitted recompute adds one task run. That number depends on the attributes selected, not on the number of branches. The count on a running instance is not known yet.
