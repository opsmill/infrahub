# Contract: CLI

## `infrahub tasks flush flow-runs` (changed)

```text
infrahub tasks flush flow-runs [CONFIG_FILE] [--rewrite] [--days-to-keep N]
```

- Deletes finished top-level runs (COMPLETED, FAILED, CANCELLED, CRASHED) whose end time is older than `task_manager.retention.task_history`, with their task runs, states, logs and artifacts.
- `--rewrite`: after the deletes, rewrites the six task-history tables to return their disk space. Off by default, because each table is locked during its rewrite. Skipped when nothing was deleted. A table whose rewrite waits more than 60 s for a lock is skipped and listed in the summary.
- `--days-to-keep N` (N ≥ 1): overrides the retention setting for this run, so existing scripts keep working. Its default becomes the retention setting instead of 30.
- `--batch-size`: accepted and ignored, with a deprecation warning; removed in a later release.
- Prints progress (current day, runs deleted) while the job runs, then a summary: runs deleted, table size before and after, tables not rewritten.
- When the task manager answers that a cleanup runs on another replica, or no longer knows the job, the command waits and starts again; committed days are not redone.
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
