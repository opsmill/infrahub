# Contract: CLI

## `infrahub tasks flush flow-runs` (changed)

```text
infrahub tasks flush flow-runs [CONFIG_FILE] [--rewrite]
```

- Deletes finished top-level runs (COMPLETED, FAILED, CANCELLED, CRASHED) whose end time is older than `task_manager.retention.task_history`, with their task runs, states, logs and artifacts.
- `--rewrite`: after the deletes, rewrites the six task-history tables to return their disk space. Off by default, because each table is locked during its rewrite. Skipped when nothing was deleted.
- Removed: `--days-to-keep`, `--batch-size` (the retention setting and the per-day steps replace them).
- Prints progress (current day, runs deleted) while the job runs, then a summary: runs deleted, table size before and after.
- Exit codes: `0` on success, and also when the task manager does not provide the cleanup (prints `The task manager does not provide the task history cleanup yet; skipped.`); `1` when the job fails.
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

- New step after "Task manager": "Task history cleanup", the same as `infrahub tasks flush flow-runs --rewrite`.
- New flag `--no-task-history-cleanup`, documented for the Helm chart's upgrade hook only, which runs while the instance is still serving.
- Step numbering in the output becomes 1/7 to 7/7.
