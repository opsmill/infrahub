# Contract: CLI

## `infrahub tasks flush flow-runs` (changed)

```text
infrahub tasks flush flow-runs [CONFIG_FILE] [--rewrite]
```

- Deletes finished top-level runs (COMPLETED, FAILED, CANCELLED, CRASHED) whose end time is older than `task_manager.retention.task_history`, with their task runs, states, logs and artifacts.
- `--rewrite`: after the deletes, rewrites the six task-history tables to return their disk space (request `rewrite: always`; without the option, `never`). Off by default, because each table is locked during its rewrite. Rewrites whatever the deletes freed, because the task manager's hourly cleanup has usually deleted the old runs already (after a Helm rollout, or after lowering the retention). Nothing is rewritten on SQLite. A table whose rewrite waits more than 60 s for a lock is retried up to 3 times, then skipped and listed in the summary.
- Removed: `--days-to-keep` and `--batch-size`; the command reads the retention setting (breaking change, flagged in the changelog).
- Prints progress (current day, runs deleted) each time it changes while the job runs, then a summary: runs deleted and the cutoff, table size before and after (Postgres only), whether the tables were rewritten, and the tables a rewrite skipped.
- When the task manager answers that a cleanup runs on another replica, or no longer knows the job, the command waits (2 s) and starts again; committed days are not redone. It gives up after the task manager has answered only that for 3 hours since it last showed a job.
- Exit codes: `0` on success, and also when the task manager does not provide the cleanup (prints `The task manager does not provide the task history cleanup yet; skipped.`); `1` when the job fails or the command gives up waiting, with the error printed.
- Safe to re-run: a re-run continues from the oldest remaining day.

## `infrahub tasks flush stale-runs` (unchanged, now documented)

- Marks runs RUNNING or PENDING since more than `--days-to-keep` days (default 2) as CRASHED, which gives them an end time so that the cleanup deletes them later.
- Does not catch PENDING runs that never started (no start time).

## `infrahub tasks background-services` (new)

```text
infrahub tasks background-services [CONFIG_FILE]
```

- Validates the retention settings, applies the derived Prefect settings, then runs Prefect's background services in the foreground, as `prefect server services start` does today.
- Used by the separate background-services deployment (Helm option, test compose files).

## `infrahub upgrade` (changed)

- New step after "Task manager": "Task history cleanup", the cleanup of `infrahub tasks flush flow-runs` with the rewrite `if_freed`: the tables are rewritten only when the deletes, Prefect's own hourly deletes during the step included, freed more than half of the runs the tables held (in practice the first upgrade). Same progress and summary output. A failed cleanup is reported with the command that finishes it, and the upgrade goes on to the next step: the days already deleted stay deleted, and a failed rewrite leaves its table intact.
- New flag `--no-task-history-cleanup`, documented for the Helm chart's upgrade hook only, which runs while the instance is still serving.
- Step numbering in the output becomes 1/7 to 7/7.
