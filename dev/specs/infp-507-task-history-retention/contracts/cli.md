# Contract: CLI

## `infrahub tasks flush flow-runs` (changed)

```text
infrahub tasks flush flow-runs [CONFIG_FILE] [--rewrite]
```

- Deletes finished top-level runs (COMPLETED, FAILED, CANCELLED, CRASHED) whose end time is older than `task_manager.retention.task_history`, with their task runs, states, logs and artifacts.
- `--rewrite`: after the deletes, rewrites each task-history and activity log table (`flow_run`, `flow_run_state`, `task_run`, `task_run_state`, `log`, `artifact`, `events`, `event_resources`) whose live rows hold less than half of its disk space, to return that space (request `rewrite: if_freed`; without the option, `never`). The rule measures the free space whoever freed it, because the task manager's hourly cleanup has usually deleted the old records already (after the upgrade, or after lowering a retention). Off by default; tasks that write to a table wait while it is rewritten, and the instance does not need to be stopped. Nothing is rewritten on SQLite. A table whose rewrite waits more than 60 s for a lock is retried up to 3 times, then skipped and listed in the summary.
- Removed: `--days-to-keep` and `--batch-size`; the task manager deletes up to the retention that Prefect's own cleanup uses, set from `task_history` (breaking change, flagged in the changelog).
- Prints progress (current day, runs deleted) each time it changes while the job runs, then a summary: runs deleted and the cutoff, the size of the eight tables before and after (Postgres only), then, with `--rewrite`, one line per outcome that applies: `Rewrote <tables>`, `Left <tables> as they are, because their live rows hold at least half of their disk space`, and `Did not rewrite <tables>, which stayed locked by other sessions`; `No table rewritten` when none applies, as on SQLite. Without `--rewrite` the last line is `Tables not rewritten`.
- When the task manager answers that a cleanup runs on another replica, or no longer knows the job, or cannot be reached while the command follows the job (a restart), the command waits (2 s) and starts again; committed days are not redone. It gives up after the task manager has answered only that, or stayed unreachable, for 3 hours since it last showed a job. While it waits it prints one line when a wait starts, when its reason changes, and when a wait starts again after a job showed, not one per retry: `Waiting to start the cleanup, because the task manager answered that a cleanup runs elsewhere`, `Waiting to start the cleanup, because the task manager answered that it does not know the cleanup` or `Waiting to start the cleanup, because the task manager could not be reached`. The error it gives up with names the reason seen last: `Gave up after 180 minutes without a cleanup to follow, when <reason>`.
- When the task manager already runs a job (for example one an interrupted run of the command started), the command follows that job to its end, and the summary is that job's. The task manager raises the job's rewrite to `if_freed` when the command asks for it, so the job rewrites as the command asks; see [task-manager-api.md](task-manager-api.md).
- Exit codes: `0` on success, and also when the task manager does not provide the cleanup (prints `The task manager does not provide the task history cleanup yet; skipped.`); `1` when the job fails, the command gives up waiting, the task manager cannot be reached to start the cleanup, or it answers with an unexpected error, with the error printed on one line. When the job failed in the task manager, the next lines say what it had committed: `Deleted N runs before the failure`, followed by the rewrite lines above when its rewrite had finished. The job records no table of a rewrite cut short by the failure, so none is named then.
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

- Deletes no task history and keeps its six steps.
- In the "Task manager" step, after `Task manager configured`, prints `Task history takes <size>. To get the space back, run: infrahub tasks flush flow-runs --rewrite`, with the size from `GET /infrahub/task-history/size` (see [task-manager-api.md](task-manager-api.md)).
- The size is read with a 10 s bound. A task manager that does not answer in time, answers an error (`404` from a task manager without the route) or an answer without a size gets `To get the disk space of old task history back, run: infrahub tasks flush flow-runs --rewrite`, and the upgrade goes on. On SQLite (`size` is `null`) nothing is printed.
- Removed from the design of 4 Oct: the "Task history cleanup" step, the step numbering 1/7 to 7/7, `--no-task-history-cleanup` and the `--check` "Task history" section.
