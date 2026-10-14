# Quickstart: validating retention

Validation scenarios for each part. Settings and commands are defined in [contracts/](contracts/); record shapes in [data-model.md](data-model.md).

## Prerequisites

- A local stack: `uv run invoke dev.build` then `uv run invoke dev.start` (Compose, task manager on Postgres).
- For unit and component tests: `uv run invoke backend.test-unit`, and the component suite with a running Docker daemon.

## Part 1: task history retention

1. Set `INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY=1d` on the task manager and restart it. Expect it to start and log the derived Prefect settings.
2. Set `INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY=0d` and restart. Expect the task manager to refuse to start, naming `task_history`.
3. Seed finished runs with end times older than 1 day, recent runs, and one RUNNING run (component test fixtures do this). Run `infrahub tasks flush flow-runs`. Expect only the old finished runs, their logs and artifacts gone, and the RUNNING run kept.
4. Run `infrahub tasks flush flow-runs --rewrite` on a database with old runs. Expect the reported size after to be smaller than before, and every one of the eight tables named once in the rewrite lines.
5. Run `infrahub upgrade` on a Compose stack with old runs. Expect no cleanup step and, in the task manager step, the line `Task history takes <size>, with <count> runs older than the retention. To get the space back, run: infrahub tasks flush flow-runs --rewrite`. The count can be lower than the runs seeded, because the task manager's own cleanup starts deleting them when it starts.
6. Run `infrahub tasks flush flow-runs --rewrite` after that upgrade, with the instance running. Expect the old runs deleted (few or none when the task manager's own cleanup ran first), then one line naming the tables rewritten and one naming the tables left as they are because their live rows hold at least half of their disk space.
7. Point `infrahub tasks flush flow-runs` at a task manager from the previous release. Expect the "does not provide the task history cleanup yet" message and exit code 0.
8. Start the background services through `infrahub tasks background-services` with the test compose file and confirm the derived settings in its log.
9. Lower `INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY`, restart the task manager and let its hourly cleanup delete the older runs, then run `infrahub tasks flush flow-runs --rewrite`. Expect few or no runs deleted, the freed task history tables rewritten, and the reported size after smaller than before.

Automated: the cleanup equivalence component test (new cleanup and Prefect's `vacuum_old_flow_runs` leave the same runs, logs and artifacts).

## Part 2: Activities page

1. Run the filter equivalence component test: every new filter returns the same events as today's label filter on seeded events (account, branch, deleted branch, recreated branch name, node with both ID forms, parent, merged, rebased and migrated by name).
2. In the UI, open Activities, scroll with "load more" while creating new changes in another tab. Expect no repeated events.
3. Query `InfrahubEvent` without `count`; check in the task-manager logs or with a breakpoint that no count query runs.

Speed with a year of activity log is validated by the private performance tests (opsmill/infrahub-private-tests, `TestActivityLog` and the concurrency test), dispatched through the `test-dataset` workflow with `test_filter=TestActivityLog`.

## Part 3: activity log retention

1. Set `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG=365d` and restart. Expect `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` of 365 days and the per-type overrides at 7 days in the startup log.
2. Set `INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS=30d` with the activity log at 7 days. Expect a warning and the per-type overrides at 7 days.
3. Run the event-type list tests: the unit test (every built-in Prefect state listed) and the integration-docker guard (a workload on the full stack stores no Prefect event type missing from the list).
4. Store an event whose type starts with `prefect.` and is missing from the list, then restart the task manager. Expect a warning in its log naming that type and the activity log retention that keeps it.

## Part 4: documentation

1. `uv run invoke docs.generate` then `uv run invoke docs.validate`: the configuration reference lists the three settings, and the CLI reference includes `infrahub tasks`.
2. Read the upgrade guides for the cleanup step after the upgrade, the same on Compose and Helm, the retention to set before upgrading and the free disk needed.
