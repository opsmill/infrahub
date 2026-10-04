# Contract: CLI

## `infrahub tasks flush flow-runs` (changed)

```text
infrahub tasks flush flow-runs [CONFIG_FILE] [--rewrite]
```

- Deletes finished top-level runs (COMPLETED, FAILED, CANCELLED, CRASHED) whose end time is older than `task_manager.retention.task_history`, with their task runs, states, logs and artifacts.
- `--rewrite`: after the deletes, rewrites the six task-history tables to return their disk space (request `rewrite: always`; without the option, `never`). Off by default, because each table is locked during its rewrite. Rewrites whatever the deletes freed, because the task manager's hourly cleanup has usually deleted the old runs already (after a Helm rollout, or after lowering the retention). Nothing is rewritten on SQLite. A table whose rewrite waits more than 60 s for a lock is retried up to 3 times, then skipped and listed in the summary.
- Removed: `--days-to-keep` and `--batch-size`; the command reads the retention setting (breaking change, flagged in the changelog).
- Prints progress (current day, runs deleted) each time it changes while the job runs, then a summary: runs deleted and the cutoff, table size before and after (Postgres only), whether the tables were rewritten, and the tables a rewrite skipped.
- When the task manager answers that a cleanup runs on another replica, or no longer knows the job, or cannot be reached while the command follows the job (a restart), the command waits (2 s) and starts again; committed days are not redone. It gives up after the task manager has answered only that, or stayed unreachable, for 3 hours since it last showed a job. While it waits it prints one line when a wait starts, when its reason changes, and when a wait starts again after a job showed, not one per retry: `Waiting to start the cleanup, because the task manager answered that a cleanup runs elsewhere`, `Waiting to start the cleanup, because the task manager answered that it does not know the cleanup` or `Waiting to start the cleanup, because the task manager could not be reached`. The error it gives up with names the reason seen last: `Gave up after 180 minutes without a cleanup to follow, when <reason>`.
- When the task manager already runs a job (for example one an interrupted upgrade started), the command follows that job to its end, and the summary is that job's. The task manager raises the job's rewrite to the one the command asks for when that is stronger (`never` < `if_freed` < `always`), so the job rewrites as the command asks; see [task-manager-api.md](task-manager-api.md).
- Exit codes: `0` on success, and also when the task manager does not provide the cleanup (prints `The task manager does not provide the task history cleanup yet; skipped.`); `1` when the job fails, the command gives up waiting, the task manager cannot be reached to start the cleanup, or it answers with an unexpected error, with the error printed on one line. When the job failed in the task manager, a second line says what it had committed: `Deleted N runs before the failure`, followed by `; task history tables rewritten` (and the tables that stayed locked) when its rewrite had finished. The job records no table of a rewrite cut short by the failure, so none is named then.
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

- New step after "Task manager": "Task history cleanup", the cleanup of `infrahub tasks flush flow-runs` with the rewrite `if_freed`: the tables are rewritten only when more than half of their disk space is free after the deletes, whoever deleted the runs: Prefect's own cleanup, which runs when the task manager starts and then every hour, often deletes them before the step starts (in practice the first upgrade). Same progress, wait and summary output. A failed cleanup is reported with what it had committed and the command that finishes it, and the upgrade goes on to the next step: the days already deleted stay deleted, and a failed rewrite leaves its table intact.
- New flag `--no-task-history-cleanup`, documented for the Helm chart's upgrade hook only, which runs while the instance is still serving.
- Step numbering in the output becomes 1/7 to 7/7.
- `--check` prints a "Task history" section before "Branches": the upgrade deletes the finished task runs older than the task manager's task history retention, rewrites the task history tables if more than half of their disk space is free after the deletes, and `--no-task-history-cleanup` leaves this out. It does not query the task manager.
