# Contract: CLI

## `infrahub tasks flush flow-runs` (changed)

```text
infrahub tasks flush flow-runs [CONFIG_FILE] [--rewrite]
```

- Deletes finished top-level runs (COMPLETED, FAILED, CANCELLED, CRASHED) whose end time is older than `task_manager.retention.task_history`, with their task runs, states, logs and artifacts.
- `--rewrite`: after the deletes, rewrites each task-history and activity log table (`flow_run`, `flow_run_state`, `task_run`, `task_run_state`, `log`, `artifact`, `events`, `event_resources`) whose live rows hold less than half of its disk space, to return that space (request `rewrite: if_freed`; without the option, `never`). The rule measures the free space whoever freed it, because the task manager's hourly cleanup has usually deleted the old records already (after the upgrade, or after lowering a retention). Off by default; tasks that read or write a table wait while it is rewritten, and the instance does not need to be stopped. Nothing is rewritten on SQLite. A table whose rewrite waits more than 3 s for a lock is retried up to 4 times 20 s apart, then skipped and listed in the summary; a rewrite that takes longer than 60 s is stopped, which leaves the table as it was, and listed in the summary; a table whose rewrite fails with a database error, such as no free disk for the copy, is left as it was and listed in the summary. After each of these tables the command goes on with the next table; a lost database connection still fails the job.
- Removed: `--days-to-keep` and `--batch-size`; the command reads the retention setting (breaking change, flagged in the changelog).
- Prints progress (current day, runs deleted) each time it changes while the job runs, then a summary: runs deleted and the cutoff, the size of the eight tables before and after (Postgres only), then, with `--rewrite`, one line per outcome that applies: `Rewrote <tables>`, `Left <tables> as they are, because their live rows hold at least half of their disk space`, `Did not rewrite <tables>, which stayed locked by other sessions`, `Did not rewrite <tables>, whose rewrite took longer than its time limit and was stopped`, and `Did not rewrite <tables>, whose rewrite failed with a database error; the task manager log has the details`; `No table rewritten` when none applies, as on SQLite. Without `--rewrite` the last line is `Tables not rewritten`.
- When the task manager answers that a cleanup runs on another replica, or no longer knows the job, or cannot be reached while the command follows the job (a restart), the command waits (2 s) and starts again; committed days are not redone. It gives up after the task manager has answered only that, or stayed unreachable, for 3 hours since it last showed a job. While it waits it prints one line when a wait starts, when its reason changes, and when a wait starts again after a job showed, not one per retry: `Waiting to start the cleanup, because the task manager answered that a cleanup runs elsewhere`, `Waiting to start the cleanup, because the task manager answered that it does not know the cleanup` or `Waiting to start the cleanup, because the task manager could not be reached`. The error it gives up with names the reason seen last: `Gave up after 180 minutes without a cleanup to follow, when <reason>`.
- When the task manager already runs a job (for example one an interrupted run of the command started), the command follows that job to its end, and the summary is that job's. The task manager raises the job's rewrite to `if_freed` when the command asks for it, so the job rewrites as the command asks; see [task-manager-api.md](task-manager-api.md).
- Exit codes: `0` on success, also when a table stayed locked, its rewrite took too long or its rewrite failed with a database error, and also when the task manager does not provide the cleanup (prints `The task manager does not provide the task history cleanup yet; skipped.`); `1` when the job fails (for example when the database connection is lost during the rewrite), the command gives up waiting, the task manager cannot be reached to start the cleanup, or it answers with an unexpected error, with the error printed on one line. When the job failed in the task manager, the next lines say what it had committed: `Deleted N runs before the failure`, followed by the rewrite lines above for each table whose rewrite ended before the failure; the table the failure stopped and the tables after it are not named.
- Safe to re-run: a re-run continues from the oldest remaining day.

## `infrahub tasks flush stale-runs` (unchanged, now documented)

- Marks runs RUNNING or PENDING since more than `--days-to-keep` days (default 2) as CRASHED, which gives them an end time so that the cleanup deletes them later.
- A PENDING run that never started has no start time; Prefect then filters on its expected start time, so the command marks it once that time is older than `--days-to-keep` days.

## `infrahub tasks background-services` (new)

```text
infrahub tasks background-services [CONFIG_FILE]
```

- Validates the retention settings, applies the derived Prefect settings, then runs Prefect's background services in the foreground, as `prefect server services start` does today.
- Used by the separate background-services deployment (Helm option, test compose files).

## `infrahub upgrade` (changed)

- Deletes no task history and keeps its six steps.
- In the "Task manager" step, after `Task manager configured`, prints `Task history takes <size>, with <count> runs older than the retention. To get the space back, run: infrahub tasks flush flow-runs --rewrite` (`1 run`, `no runs`, or `more than 100,000 runs` past the count limit), with the size and the count from `GET /infrahub/task-history/size` (see [task-manager-api.md](task-manager-api.md)).
- The size is read with a 10 s bound. A task manager that does not answer in time, answers an error (`404` from a task manager without the route) or answers without a size gets `Could not read the task history size from the task manager (<error type>). To get the disk space of old task history back, run: infrahub tasks flush flow-runs --rewrite`, and the upgrade goes on. On SQLite (`size` is `null`) nothing is printed.
- Removed from the design of 4 Oct: the "Task history cleanup" step, the step numbering 1/7 to 7/7, `--no-task-history-cleanup` and the `--check` "Task history" section.
