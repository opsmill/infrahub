# Tasks: Task History and Activity Log Retention

**Input**: Design documents from `dev/specs/infp-507-task-history-retention/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md). The [Notion design doc](https://app.notion.com/p/opsmill/Task-history-and-Activity-log-retention-3dc228b830258012ba28dc3a23eece65) is the source of truth for technical decisions.

**Tests**: Requested. The spec requires three CI guards (FR-027 to FR-029) and the constitution requires tests at the right tier, plus an E2E test for user-facing behaviour.

**Organization**: One phase per user story, in the delivery order of the design doc: US1 (part 1, task history), US2 (part 2, Activities page, before US3), US3 (part 3, activity log retention), US4 (single configuration entry point). Documentation (part 4) is in the final phase and ships with US1 and US3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story from spec.md (US1 to US4)

---

## Phase 1: Setup

**Purpose**: Shared test helpers used by several stories.

- [X] T001 [P] Add a component-test helper that seeds Prefect flow runs with explicit state, `start_time`, `end_time`, parent task run, task runs, states, logs and artifacts directly through Prefect's database interface, in `backend/tests/helpers/task_manager_seed.py` (function names: `seed_flow_run`, `seed_log`, `seed_artifact`)
- [X] T002 [P] Add a component-test helper that stores events through Prefect's event storage (both Infrahub events built from `infrahub.events` classes and raw Prefect events with a given name and `occurred`) in `backend/tests/helpers/task_manager_seed.py` (functions `seed_infrahub_event`, `seed_prefect_event`)

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The retention settings and their translation into Prefect settings, used by US1, US3 and US4.

- [X] T003 Add `TaskManagerRetentionSettings` (fields `task_history` default 30 days, `activity_log` default 7 days, `prefect_own_events` default 7 days; values accept `30d` or ISO 8601 durations; validators: each ≥ 1 day, error message `Invalid task manager retention: <key> <reason>`; a `prefect_own_events` longer than `activity_log` is not an error) and a `TaskManagerSettings` holding it under `retention`, registered on `Settings` as `task_manager`, env prefix `INFRAHUB_TASK_MANAGER_RETENTION_`, in `backend/infrahub/config.py` (contract: [contracts/configuration.md](contracts/configuration.md))
- [X] T004 [P] Unit tests for T003: defaults, `30d` and `P30D` parsing, refusal below 1 day, own events longer than activity log accepted, env variable names, in `backend/tests/unit/config/test_task_manager_retention_settings.py`
- [X] T005 Create `backend/infrahub/prefect_server/retention.py` with `PREFECT_EVENT_TYPES: tuple[str, ...] = ()` (filled in US3) and `build_prefect_retention_env(settings: TaskManagerRetentionSettings, event_types: tuple[str, ...]) -> dict[str, str]` returning `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED=events,flow_runs`, `PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD`, `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` (ISO 8601 durations in days, such as `P30D`) and `PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES` (JSON, one entry per given type, using `min(prefect_own_events, activity_log)`), and `apply_prefect_retention_env(environ: MutableMapping[str, str], settings) -> list[str]` that builds them from `PREFECT_EVENT_TYPES`, sets only variables not already present and returns a warning when own events are capped plus a warning `PREFECT_<NAME> is set and overrides task_manager.retention.<key>` per variable left as is (data-model: Derived Prefect settings)
- [X] T006 [P] Unit tests for T005 (derived values, JSON shape, capping of own events with its warning, precedence and warnings) in `backend/tests/unit/prefect_server/test_retention.py`
- [X] T007 In `backend/infrahub/prefect_server/app.py::create_infrahub_prefect`, load the Infrahub configuration in every mode (today only in distributed mode), then call `apply_prefect_retention_env(os.environ, config.SETTINGS.task_manager.retention)`, log each warning and refresh Prefect's global settings (`prefect.context.refresh_global_settings_context`, since Prefect reads the environment once at import), before `create_app()`; an invalid retention stops the process with the validation error. The steps live in `apply_infrahub_settings_to_prefect()`; the stock Prefect container of `backend/tests/helpers/utils.py` (no `infrahub` package) starts `create_prefect_app_with_infrahub_routes` instead

**Checkpoint**: The task manager starts with the derived Prefect settings; the component harness still turns the vacuum off through `backend/tests/helpers/constants.py`, which now takes precedence by design.

---

## Phase 3: User Story 1 - Task history stops filling the disk (Priority: P1) 🎯 MVP

**Goal**: Old finished runs are deleted automatically and by the command for old runs; the Compose upgrade deletes the backlog and rewrites the tables.

**Independent Test**: Seed finished, stuck and recent runs older and newer than the retention; run the command and the upgrade step; only old finished runs and their logs and artifacts are gone, and the tables shrink (quickstart Part 1).

### Tests for User Story 1

- [X] T008 [P] [US1] Component test: cleanup equivalence. Seed runs (finished in each terminal state, RUNNING, PENDING, recent, subflows with and without parent, logs, artifacts), copy the state, run Prefect's `vacuum_old_flow_runs` on one copy and the new cleanup on the other, assert identical remaining run, task run, state, log and artifact IDs, in `backend/tests/component/task_manager/test_task_history_cleanup.py`
- [X] T009 [P] [US1] Component test: run Prefect's `vacuum_old_flow_runs` and the new cleanup concurrently on the same old runs; both finish without error and the end state equals T008's, in `backend/tests/component/task_manager/test_task_history_cleanup.py`
- [X] T010 [P] [US1] Component tests for the routes: `POST` returns the running job on a second call, raising its rewrite to a stronger one, which the job decides again with when it arrives after the decision and never rewrites twice, `409` when the lock is held elsewhere (simulate by holding the lock), `GET` unknown id → `404`, no rewrite on SQLite, in `backend/tests/component/task_manager/test_task_history_routes.py`
- [X] T011 [P] [US1] Unit tests for the CLI client loop: 404 on start → message and exit 0; 409 or 404 while polling → wait and post again; failed job → exit 1; progress lines printed; `--days-to-keep` and `--batch-size` no longer accepted, using a fake HTTP transport, in `backend/tests/unit/cli/test_tasks_flush_flow_runs.py` (the polling loop itself in `backend/tests/unit/task_manager/flow_run/test_cleanup.py`)
- [X] T012 [P] [US1] Unit test that `infrahub upgrade` runs the task history cleanup step after the task manager step with the rewrite `if_freed`, skips it with `--no-task-history-cleanup`, and numbers steps 1/7 to 7/7, in `backend/tests/unit/cli/test_upgrade_task_history.py`
- [X] T013 [US1] Integration-docker test on Postgres: seed old runs, run `infrahub tasks flush flow-runs --rewrite` against the stack, assert the same end state as T008 and smaller table sizes, in `backend/tests/integration_docker/test_task_history_cleanup.py`

### Implementation for User Story 1

- [X] T014 [US1] Implement the cleanup job in `backend/infrahub/prefect_server/task_history.py`: `CleanupJob` (fields from data-model.md: Cleanup job), a module-level registry of the job running in this process, the advisory lock (Postgres `pg_try_advisory_lock` on a dedicated session for the job's lifetime; a process lock on SQLite), the per-day loop from the oldest eligible `end_time` to the cutoff (delete the day's eligible top-level runs with the same conditions as `vacuum_old_flow_runs`, returning their IDs, then the logs and artifacts of those runs, commit; the design doc's D9 SQL), a second pass for subflows left without a parent, and progress logging per day
- [X] T015 [US1] Add the rewrite to `backend/infrahub/prefect_server/task_history.py`: only on Postgres, as the request's `rewrite` mode asks (`never`; `if_freed`, when more than half of the tables' disk space is free after the deletes, measured on `flow_run` as its size on disk against the size of its live rows, so that runs Prefect's own cleanup deleted before the job started count too; `always`), `VACUUM FULL` on `flow_run`, `flow_run_state`, `task_run`, `task_run_state`, `log`, `artifact` in autocommit with `lock_timeout = 60s` and up to 3 retries per table, recording `size_before`, `size_after` (`pg_total_relation_size`), `rewritten` and `not_rewritten`
- [X] T016 [US1] Add the routes `POST /infrahub/task-history/cleanup` and `GET /infrahub/task-history/cleanup/{id}` in `backend/infrahub/prefect_server/task_history.py`, with Pydantic request/response models (`rewrite` only; job shape from [contracts/task-manager-api.md](contracts/task-manager-api.md)) in `backend/infrahub/prefect_server/task_history_models.py`, which imports neither the task manager's database layer nor any `infrahub` module, so the client loads without them, and include the router in `backend/infrahub/prefect_server/app.py::router`
- [X] T017 [US1] Add a client used by the CLI and the upgrade, `run_task_history_cleanup(client, rewrite: CleanupRewrite, on_progress, on_wait) -> CleanupJob | None` (returns `None` when the route is missing; the mode and the job model are the route's own, imported from `task_history_models.py`), which starts the job, polls, re-posts after a wait on 409, on 404, or on a transport error once the task manager has answered, follows the job it gets to its end (the task manager raises a running job's mode to a stronger request's, so the client never posts again after a completed job), reports each wait when it starts, when its reason changes and when it starts again after a job showed, gives up after 3 hours without seeing a job naming the reason of the last wait, and raises on a failed job with the job as it ended, in `backend/infrahub/task_manager/flow_run/cleanup.py`
- [X] T018 [US1] Reimplement `infrahub.cli.tasks::flow_runs` on T017: option `--rewrite` (sends `always`, otherwise `never`); remove `--days-to-keep` and `--batch-size`; progress and summary output; exit codes from [contracts/cli.md](contracts/cli.md); keep `stale_runs` and `FlowRunRetention` unchanged, in `backend/infrahub/cli/tasks.py`
- [X] T019 [US1] Add the "Task history cleanup" step after the task manager step in `backend/infrahub/cli/upgrade.py::_upgrade_execute` (calls T017 with the rewrite `if_freed`, prints the summary or the "not provided yet" message, reports a failed cleanup with the command that finishes it and goes on with the upgrade), add `--no-task-history-cleanup` to `upgrade_cmd`, renumber steps to 1/7 to 7/7
- [X] T020 [P] [US1] Changelog fragment for the task history retention, the changed `flush flow-runs` command and the upgrade step (irreversible deletion, set a longer retention before upgrading) by extending `changelog/+task-manager-retention.added.md` (which already covers the settings, the hourly deletion and setting a longer retention before upgrading) with the upgrade step, and adding `changelog/+flush-flow-runs.changed.md` (breaking: `--days-to-keep` and `--batch-size` removed) (follow the `creating-changelog-entries` skill)

### Evidence for User Story 1 (opsmill/infrahub-private-tests)

Run through the `test-dataset` workflow (`test_filter=...`) on restored backups that include `prefect.dump`, on Postgres 14 (Helm) and 18 (Compose). Results go in the PR description and on INFP-507 as the release evidence. Run every evidence task in a separate session in a checkout of opsmill/infrahub-private-tests (see plan.md, Evidence: infrahub-private-tests).

- [ ] T021 [P] [US1] Task history retention test: with the retention setting applied, the hourly cleanup deletes finished runs older than the retention with their logs and artifacts, keeps newer and stuck runs, and the setting also reaches Prefect's background services when they run in their own container (`infrahub tasks background-services`), in `tests/performance/test_task_history_retention.py` of opsmill/infrahub-private-tests
- [ ] T022 [P] [US1] Upgrade step test on backups with about 25 GB and 100 GB of task history: runs older than the retention deleted, newer and stuck runs kept, task-history tables smaller afterwards; record the duration, the extra disk used by the rewrite and the size before and after (answers Q1 for the release notes), in `tests/performance/test_task_history_upgrade.py` of opsmill/infrahub-private-tests
- [ ] T023 [P] [US1] Cleanup under a live workload: run the hourly cleanup, the command for old runs and Prefect's own cleanup while tasks run and the Activities and Tasks pages are queried; record lock waits, deadlocks, errors and the effect on running tasks, in `tests/performance/test_task_history_cleanup_load.py` of opsmill/infrahub-private-tests
- [ ] T024 [P] [US1] Track task-manager database size and dead space per table on the performance dashboard, extending `tests/performance/test_database_size.py` of opsmill/infrahub-private-tests

**Checkpoint**: US1 is shippable on its own (part 1).

---

## Phase 4: User Story 2 - The Activities page stays fast with a year of activity log (Priority: P2)

**Goal**: Same events as today, through indexed IDs, newest first in time windows, count only on request, paging by time.

**Independent Test**: Filter equivalence on seeded events; timings with a year of activity log in the private performance tests (quickstart Part 2).

### Prerequisite

- [X] T025 [US2] Merge PR #10379 (count only when requested, plan per query) into `stable`, or carry its commits into this branch, before T030-T033; if carried, keep its tests

### Tests for User Story 2

- [X] T026 [P] [US2] Component test: filter equivalence. Seed Infrahub events covering accounts, branches (existing, deleted, deleted then recreated with the same name), nodes with `infrahub.node.<id>` and bare-ID artifact events, parent and child events, branch merged/rebased/migrated; for each filter compare the new ID-based filter's events with today's label filter, at offsets 0 and beyond one window, in `backend/tests/component/task_manager/test_event_filter_equivalence.py`
- [X] T027 [P] [US2] Component test: time windows. Newest-first results equal a single full-retention read for sparse and dense filters, with `until` anchoring and with `offset`; events older than 180 days are returned when the retention is longer; `include_total=False` returns `total=None`, in `backend/tests/component/task_manager/test_event_query_windows.py`
- [X] T028 [P] [US2] Unit tests for filter construction (account, branch ID, node with both ID forms, parent with ancestor role plus label check, branch-name resource IDs) in `backend/tests/unit/task_manager/event/test_models.py`
- [X] T029 [P] [US2] Vitest for paging by time: next page param is the last event's `occurred_at`, duplicates at the boundary dropped by id, no next page when a page is short, in `frontend/app/src/entities/events/ui/queries/get-events.query.test.ts`

### Implementation for User Story 2

- [X] T030 [US2] Change `InfrahubEventFilter.add_account_filter`, `add_branch_filter` (takes branch IDs), `add_primary_node_filter`, `add_parent_filter` and the branch-name handling in `add_event_type_filter` to match `prefect.resource.id` as in data-model.md (Activities filters), in `backend/infrahub/task_manager/event/models.py`
- [X] T031 [US2] Resolve branch names to IDs in `backend/infrahub/graphql/queries/event.py::Events.resolve`: current branches from the database in one query (`BranchGetIdsByNameQuery`, including a branch whose deletion has started); otherwise the newest `infrahub.branch.deleted` event with resource ID `infrahub.branch.<name>` (read through `PrefectEvent`); no match → return an empty page without querying further; pass `include_total="count" in fields` down through `Events.query`
- [X] T032 [US2] Add `include_total` and the retention window to `InfrahubEventfilterInput`, make `InfrahubEventPage.total` nullable, in `backend/infrahub/prefect_server/models.py`; pass them in `backend/infrahub/prefect_server/events.py::read_events`; send `include_total` and accept a null count in `backend/infrahub/task_manager/event/query.py::PrefectEvent.query_events`
- [X] T033 [US2] Implement newest-first time windows (1 h, 1 d, 7 d, 30 d, then the activity log retention, counted back from `occurred.until` or now; a window is full when it holds `offset + limit` matches) and the optional count in `backend/infrahub/prefect_server/database.py::query_events`, keeping PR #10379's per-query plan setting
- [X] T034 [US2] Page by time on the Activities page: `getNextPageParam` returns the last event's `occurred_at`, `queryFn` passes it as `until` (no offset), pages are merged without duplicate ids, in `frontend/app/src/entities/events/ui/queries/get-events.query.ts` and its caller in `frontend/app/src/entities/events/domain/use-cases/get-events.ts`; confirm the query in `frontend/app/src/entities/events/api/get-events-from-api.ts` still does not select `count`
- [X] T035 [US2] E2E test: on the global Activities page, load more while new events are created, assert no event appears twice, in `tests/e2e/activities/test_global_activities.py`
- [X] T036 [P] [US2] Changelog fragment for the faster Activities page and the server counting only on request in `changelog/+activities-retention-queries.fixed.md`

### Evidence for User Story 2 (opsmill/infrahub-private-tests)

- [ ] T037 [US2] Land opsmill/infrahub-private-tests PR #33 (`TestActivityLog` in `tests/performance/test_activity_log.py`) and switch its retention override in `tests/performance/conftest.py::write_prefect_retention_override` from `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` to `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG`, so the test exercises the Infrahub setting (a pre-set `PREFECT_*` variable takes precedence and would bypass it)
- [ ] T038 [US2] Extend `tests/performance/test_activity_log.py` of opsmill/infrahub-private-tests: the same query repeated more than 5 times on one connection (no plan flip), identical results through the new filters against the previous release, the time windows, combined filters that match few events (including the rarest level with an account and a branch) against the 10 s limit, and paging by time far down a combined filter on Postgres 14 and 18 (the open deep-scrolling measurement)
- [ ] T039 [P] [US2] Many users paging through the Activities page at the same time, recording latency percentiles and errors, in `tests/performance/test_activity_log_concurrency.py` of opsmill/infrahub-private-tests

**Checkpoint**: The Activities page is fast at a year of activity log; US3 may now raise the retention.

---

## Phase 5: User Story 3 - Operators keep the activity log for a configured period (Priority: P3)

**Goal**: Infrahub events kept for the activity log retention; Prefect's own events deleted after their own retention.

**Independent Test**: Raise the activity log retention; Infrahub events survive past 7 days, Prefect events do not, no related item left (quickstart Part 3).

### Tests for User Story 3

- [X] T040 [P] [US3] Integration-docker guard test on the full stack (real workers, Postgres): run a workload of Infrahub tasks that also reaches the failure paths it can (a failed flow, a cancelled flow, a worker restart), list stored event names not starting with `infrahub.`, assert none is missing from `PREFECT_EVENT_TYPES`, in `backend/tests/integration_docker/test_prefect_event_types.py`. As landed: the workload loads a schema, creates and updates nodes, creates, rebases and merges a branch, and creates a proposed change. The failed flow is the add flow of a read-only repository whose ref does not exist, because the connectivity check refuses a location that cannot be reached and does not resolve a read-only ref. The cancelled flow is a run scheduled a day ahead and cancelled through Prefect's API. The task workers restart while a flow run is running; in the local runs that was the proposed change pipeline, which ended `Crashed`. The test does not assert the crash, because whether a run is running at the restart depends on timing. The test also asserts that completed, failed and cancelled flow-run events are stored, so a quiet stack cannot pass. The stored Prefect event types were all in the list, so the list is unchanged
- [X] T041 [P] [US3] Unit test independent of any workload: for every built-in state name of the pinned Prefect (read from Prefect's state definitions), assert `prefect.flow-run.<State>` and `prefect.task-run.<State>` are in `PREFECT_EVENT_TYPES`, so a Prefect upgrade that adds a state fails CI, in `backend/tests/unit/prefect_server/test_prefect_event_types.py`
- [X] T042 [P] [US3] Component test: with activity log 365 days and own events 7 days applied, run Prefect's `vacuum_events_with_retention_overrides` and `vacuum_old_events`; Infrahub events older than 7 days are kept, listed Prefect events older than 7 days are deleted, an unlisted Prefect type is kept, no `event_resources` row is left without its event, in `backend/tests/component/task_manager/test_event_retention.py`

### Implementation for User Story 3

- [X] T043 [US3] Fill `PREFECT_EVENT_TYPES` from the pinned Prefect 3.8.6 (flow-run and task-run state events for every built-in state name, heartbeat, worker, automation, deployment, work pool, work queue and block events) and the benchmark datasets, with a one-line comment naming the Prefect version, in `backend/infrahub/prefect_server/retention.py`
- [X] T044 [US3] Use the activity log retention as the widest Activities time window by default. As landed, with no new code: the task manager sets Prefect's `server.events.retention_period` from `task_manager.retention.activity_log` at startup (T005, T007), and `InfrahubEventfilterInput.retention` in `backend/infrahub/prefect_server/models.py` falls back to that Prefect setting when the request sends no `retention_seconds`, which the Infrahub server never sends. Prefect's setting stays the only source, so a `PREFECT_SERVER_EVENTS_RETENTION_PERIOD` set by the operator bounds both the deletion and the widest window. Covered by `test_task_manager_retention_bounds_the_widest_window_by_default` and the `sparse_page_older_than_180_days` case in `backend/tests/component/task_manager/test_event_query_windows.py`
- [X] T060 [US3] Warn at task manager startup about stored `prefect.*` event types missing from `PREFECT_EVENT_TYPES`: `read_stored_event_types` in `backend/infrahub/prefect_server/database.py`, `unlisted_prefect_event_types` in `backend/infrahub/prefect_server/retention.py`, the check after Prefect's startup in `backend/infrahub/prefect_server/app.py::create_infrahub_prefect`; unit, component and integration-docker tests
- [X] T045 [P] [US3] Changelog for the configurable activity log retention: `changelog/+task-manager-retention.added.md` already covers the unchanged 7-day default and how to raise it. As landed: the fragment is unchanged, because the sizing guidance (5.7 to 8.1 GiB per million stored events) goes to the documentation in T053

### Evidence for User Story 3 (opsmill/infrahub-private-tests)

- [ ] T046 [US3] Activity log retention test on a restored backup with the activity log raised: no Infrahub event deleted, no orphaned related item, nothing newer than either retention deleted, and every stored Prefect event type present in `PREFECT_EVENT_TYPES`, in `tests/performance/test_activity_log_retention.py` of opsmill/infrahub-private-tests

**Checkpoint**: Activity log retention is configurable; IFC-1702 is solved for instances that raise it.

---

## Phase 6: User Story 4 - One place to configure retention (Priority: P4)

**Goal**: The settings apply wherever Prefect's background services run, and invalid values stop the start.

**Independent Test**: Start the task manager and the separate background services with valid and invalid values (quickstart Part 1 steps 1, 2, 8 and Part 3 step 2).

- [X] T047 [P] [US4] Unit test: `create_infrahub_prefect` refuses to start on a retention under 1 day, logs a warning when own events are capped, and logs a warning per pre-set `PREFECT_*` variable, in `backend/tests/unit/prefect_server/test_app_retention.py`
- [X] T048 [US4] Add `infrahub tasks background-services [CONFIG_FILE]`: load the configuration, apply `apply_prefect_retention_env`, then start Prefect's background services in the foreground as `prefect server services start` does, in `backend/infrahub/cli/tasks.py`
- [X] T049 [P] [US4] Switch `task-manager-background-svc` to `command: infrahub tasks background-services` in `python_testcontainers/infrahub_testcontainers/docker-compose.test.yml` and `python_testcontainers/infrahub_testcontainers/docker-compose-cluster.test.yml`
- [ ] T050 [US4] Open the opsmill/infrahub-helm PR for the same release: background-services deployment runs `infrahub tasks background-services`, the upgrade hook passes `--no-task-history-cleanup`, retention values exposed in values.yaml (outside this repository)

---

## Phase 7: Polish & cross-cutting (part 4 documentation)

- [ ] T051 [P] Add `("infrahub.cli.tasks", "infrahub tasks", "infrahub-tasks")` to `tasks/docs.py::CLI_COMMANDS`, then run `uv run invoke docs.generate` to regenerate `docs/docs/reference/configuration.mdx` and `docs/docs/reference/infrahub-cli/infrahub-tasks.mdx`
- [ ] T052 [P] Upgrade guides: the task history cleanup step, irreversible deletion and setting a longer retention before upgrading, free disk for the rewrite, expected duration (Q1), the Helm maintenance step after the rollout (stop server and task workers, run `infrahub tasks flush flow-runs --rewrite`, start them), and getting disk back after lowering a retention, in `docs/docs/deploy-manage/maintain-upgrade/upgrade/overview.mdx`, `community.mdx` and `enterprise.mdx`
- [ ] T053 [P] Document the activity log retention, the own-event retention and sizing guidance (5.7 to 8.1 GiB per million stored events) in `docs/docs/deploy-manage/run-observe/activity-log.mdx`, and the task history retention, the precedence of `PREFECT_*` variables, `flush flow-runs` and the stuck-runs command with its limit in `docs/docs/deploy-manage/run-observe/tasks.mdx` (follow the `opsmill-docs-writing-infrahub-docs` skill)
- [ ] T054 [P] Update `dev/knowledge/backend/events.md` (retention, Prefect event-type list, Activities queries) and `dev/knowledge/backend/async-tasks.md` (task history retention, cleanup job, stuck runs), each with a behaviour table
- [ ] T055 [P] Update `dev/adr/0002-events-system.md`, whose assumption that Prefect's retention covers the audit trail no longer holds
- [ ] T056 [P] Correct `dev/specs/telemetry-collection-infp-589/spec.md` from 90 days to the 30-day task history default
- [ ] T057 Run the opsmill/infrahub-private-tests suites from the evidence tasks T021-T024, T037-T039 and T046 against the release candidate on Postgres 14 and 18, and attach the report to the PR and to INFP-507 as the release evidence
- [ ] T058 Run `/pre-ci` (format, lint, unit tests, `docs.validate`) and fix what it reports
- [ ] T059 Run [quickstart.md](quickstart.md) on a local Compose stack and record the results in the PR description, including the constitution deviation (unauthenticated cleanup route) for maintainer approval

---

## Dependencies & execution order

- **Setup (T001-T002)**: none.
- **Foundational (T003-T007)**: after Setup; blocks US1, US3, US4.
- **US1 (T008-T024)**: after Foundational. T014 → T015 → T016 → T017 → T018, T019. Tests T008-T012 are written first and fail until T014-T019 land; T013 after T018. Evidence T021-T024 after T019 on a built image; the separate-container case in T021 also needs T048 (US4).
- **US2 (T025-T039)**: independent of Foundational except T044 (US3). T025 first; T030-T033 after T025; T034 after T033; T035 after T034. Evidence T037 any time (lands PR #33), T038-T039 after T033 and T034 on a built image.
- **US3 (T040-T046)**: after Foundational and after US2 has merged (a longer retention with today's queries makes the page slower). T043 (filling the list) before T040 and T041 pass. Evidence T046 after T044.
- **US4 (T047-T050)**: after Foundational; T048 before T049 and T050.
- **Polish (T051-T059)**: T051-T056 alongside US1 and US3; T057 (evidence run on the release candidate), then T058-T059 last.

## Parallel opportunities

- Setup: T001 and T002.
- Foundational: T004 and T006 alongside T005 and T007.
- US1 tests T008-T012 in parallel; T020 any time; evidence T021-T024 in parallel in the private-tests repository.
- US2 tests T026-T029 in parallel; US2 can be developed in parallel with US1 by another developer.
- US3 tests T040, T041 and T042 in parallel.
- Polish T051-T056 in parallel.
- Evidence T037-T039 and T046 in parallel with the backend work once a test image exists.

## Implementation strategy

Each slice ships only with its private-test evidence (the "Evidence" block of its phase) attached to the PR and to INFP-507.

1. **MVP**: Setup, Foundational, US1 with T021-T024. This alone stops the disk-filling incidents and can ship (part 1).
2. **Then US2**: the Activities page fix, independent of the retention values.
3. **Then US3 and US4**: configurable activity log retention and the separate background services, once US2 is merged.
4. **Documentation** ships with US1 and US3.
