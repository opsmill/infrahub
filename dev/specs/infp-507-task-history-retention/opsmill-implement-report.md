# Implementation report: task history and activity log retention (INFP-507)

## 1. Header

- **Feature**: task history and activity log retention, INFP-507, target release 1.13. Source of truth: the [Notion design doc](https://app.notion.com/p/opsmill/Task-history-and-Activity-log-retention-3dc228b830258012ba28dc3a23eece65).
- **Spec directory**: `dev/specs/infp-507-task-history-retention/`
- **Base commit**: `origin/develop` at `1920cd11d`. The spec commits were cut from `stable` and rebased onto `develop` before implementation, because `dev/guidelines/git-workflow.md` sends features to `develop`.
- **Head commit**: `f59317d0a`, the tip of `retention-docs-infp-507`, the top of the stack, before the commit that adds this report.
- **Wall-clock time**: about 9.5 hours on 2026-10-04, from about 11:55 UTC (first chunk) to about 21:30 UTC (this report).
- **Status**: DONE. Every chunk completed, and every test added or changed has local-pass evidence (§4). The quickstart run (T059) found a defect in the upgrade's rewrite, which is fixed on PR 2 and passed a second Compose run. The tasks still open run in other repositories or on a release candidate (§3).
- **Delivery**: six draft pull requests in GitHub stack #10873, based on `develop`. Merge them bottom-up:

  | PR | Branch | Contents |
  |---|---|---|
  | [opsmill/infrahub#10862](https://github.com/opsmill/infrahub/pull/10862) | `task-history-retention-infp-507` | Spec set; retention settings applied to Prefect; Prefect event-type list |
  | [opsmill/infrahub#10869](https://github.com/opsmill/infrahub/pull/10869) | `task-history-cleanup-infp-507` | Cleanup job and routes; `flush flow-runs [--rewrite]`; upgrade step |
  | [opsmill/infrahub#10876](https://github.com/opsmill/infrahub/pull/10876) | `activities-queries-infp-507` | Activities queries by ID, newest-first windows, paging by time; carries opsmill/infrahub#10379 |
  | [opsmill/infrahub#10877](https://github.com/opsmill/infrahub/pull/10877) | `activity-log-retention-infp-507` | Full-stack guard for the Prefect event-type list |
  | [opsmill/infrahub#10878](https://github.com/opsmill/infrahub/pull/10878) | `background-services-infp-507` | `infrahub tasks background-services` |
  | [opsmill/infrahub#10879](https://github.com/opsmill/infrahub/pull/10879) | `retention-docs-infp-507` | Customer docs, knowledge docs, ADR-0002 amendment, CLI reference |

## 2. Chunk-by-chunk ledger

The review fixes rebased the stack after the chunks ran, and the quickstart fix rebased PRs 3 to 6 again. The commits below are the ones now on each branch, so they differ from the hashes the chunk subagents reported.

| # | Chunk | Tasks | Outcome | Commits now on the branch | Flagged upward |
|---|---|---|---|---|---|
| 1 | Foundational (PR 1) | T003-T007, T047 (pulled forward from US4 as the test for T007) | 6 ✅ | `62db5e844`, `d4bbf506f`, `289e10d6a` | Prefect reads its settings once at import, so the task manager refreshes Prefect's settings context after applying the values. The stock Prefect test container now uses a factory without the configuration step. |
| 1b | Event types and review fixes (PR 1) | T002, T041, T042, T043 (pulled forward from US2 and US3); legacy aliases, startup log, 36,500-day maximum, changelog | 4 ✅ | `56439d938`, `14c619dac`, `4242f7fe5`, `8e65b4170` | 103 Prefect event types, read from the Prefect 3.8.6 source. 5 state names set by Prefect's engine are not covered by the state unit test. |
| 2 | Cleanup job and routes (PR 2) | T001, T008, T009, T010, T014, T015, T016 | 7 ✅ | `52a5065da`, `8d8f80a6e` | Postgres 14 and 18 probe (not committed): lock `409`, concurrency with Prefect's vacuum, and a skipped table on lock timeout. |
| 3 | Client, CLI, upgrade (PR 2) | T011, T012, T013, T017, T018, T019, T020; rewrite modes | 7 ✅ | `18ab30664`, `9b25fab11` | Rewrite modes `never` / `if_freed` / `always` (see §6). |
| 3b-3d | Review rounds on PR 2 | review fixes | ✅ | `0494764e1` … `dbd1841a0` | A running job's rewrite mode is raised in the task manager; the job lifecycle lives in one place. |
| 4 | Activities backend (PR 3) | T025 (cherry-pick of #10379), T026-T028, T030-T033 | 8 ✅ | `97d6187c3`, `f482680f3` (#10379), `cf14102a8`, `8fb83cdf3` | The "Primary Node" filter keeps label matching unless the request lists event types (see §6). `include_total` keeps #10379's name. |
| 5 | Activities frontend and E2E (PR 3) | T029, T034, T035, T036 | 4 ✅ | `2af3c61e8`, `9a89e8b17` | No tie offset, because Prefect orders events by time only. The proposed-change timeline pages with `since`. |
| 6 | Event-type guard (PR 4) | T040, T044, T045 | 3 ✅ | `fa28b0295`, `968a80cd5` | T044 needed no production code. T045's sizing guidance went to the docs (T053). |
| 7 | Background services (PR 5) | T048, T049 | 2 ✅ | `aa603a7d7`, `927c9fa89`, `2905c9bc1` | The background services now log at `INFRAHUB_LOG_LEVEL` (INFO), not Prefect's WARNING. |
| 8 | Documentation (PR 6) | T051-T056 | 6 ✅ | `aa9c3d9c4`, `908b52f34`, `5e2c251e8`, `ac047ecf6` | Findings are listed in §7. |
| R | Stack-wide review fixes | see §5 | ✅ | PR 1 `6d0fa03e0`, `35b8e561c`; PR 2 `96fdf9c22`-`4f05013fd`; PR 3 `2c564cd0c`-`cd1c43fa4`; PR 6 `3a75e347e` | One partial item (§5). |
| Q | Quickstart run and the fix it needed (PR 2, PR 6) | T059 | ✅ after a fix | PR 2 `389fb275b`, `4779e7130`; PR 6 `bc47d990b`, `f59317d0a` | The documented Compose upgrade never rewrote the tables. The `if_freed` rule now measures free space (§6 item 11). |

Orchestrator commits outside the chunks:

- `cd22dd835`: retention variables on the Compose `task-manager` service.
- Spec, docs and changelog corrections: `84b1848f0`, `48fcc60a7`, `dd707e1b4`, `d9758ab3c`, `ff6a8ce62`, `c2237d75d`, `f595626cf`, `1512d84bc`, `bc47d990b`, `f59317d0a`.

## 3. Tasks not completed

| Task | Reason |
|---|---|
| T021, T022, T023, T024 | Release evidence in opsmill/infrahub-private-tests. Per `plan.md`, these run in a separate session in that repository. |
| T037, T038, T039 | Same: private performance tests. T037 includes switching PR #33's override to `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG`. |
| T046 | Same: activity log retention test on a restored backup. |
| T050 | The opsmill/infrahub-helm PR is in another repository. It must ship in the same release; see §7. |
| T057 | The private-tests run against the release candidate. It depends on the tasks above and on a release candidate. |

T058 (`/pre-ci`) ran before each push: PR 1, PR 2, PR 3, PRs 4 and 5 together, and PR 6, then once more on the top of the stack after the quickstart fix. Every failure it reported came from the environment (see §4).

T059 (quickstart on a local Compose stack, image built from the top of the stack):

- Part 1: steps 1 to 6 and 9 passed. Step 9 deleted the old runs with `flush flow-runs` instead of waiting for the hourly cleanup, then `--rewrite` printed `Deleted 0 runs`, `172.5 MB before, 2.0 MB after`.
  - Step 5 failed on the first run, then passed after the fix (§5, §6 item 11).
  - Step 7 was not run, because no task manager from the previous release was at hand; the unit tests cover the `404` path.
  - Step 8 is covered by the scale-out stack check in §4.
- Part 2: steps 1 and 2 are covered by the equivalence component test and the Activities E2E test in §4. Step 3 passed: the Postgres statement log shows the count query only for a GraphQL query that selects `count`.
- Part 3: step 1 ran with own events of 30 days, so it showed `P365D` and `P30D for 103 event types` rather than the 7-day default the step expects; the overrides follow `prefect_own_events`, and the unit tests cover the default. Step 2 passed: the warning and `P7D`. The event-type tests of step 3 are in §4.
- Part 4: `docs.validate` passed in `/pre-ci`.
- The results are in PR 6's description. The constitution deviation is in PR 2's description.

## 4. Local-pass evidence

The rows group tests by file and run. Each run's pass line covers every test in that file; the chunk reports list the test IDs. Environment for component and integration runs: macOS, Python 3.14, `DOCKER_HOST=unix:///Users/Dimitris/.docker/run/docker.sock`, `PYTHONPATH=backend`. Component tests run on Prefect's SQLite test server. Integration tests run on the Postgres test stack with an image built from the branch.

| Test id | Type | Run command | Passed at (UTC) | Environment context | Verbatim pass line |
|---|---|---|---|---|---|
| `backend/tests/unit/config/test_task_manager_retention_settings.py` (all cases, including bare `P`/`PT`) | unit | `uv run --no-sync pytest backend/tests/unit/config/test_task_manager_retention_settings.py -q -n 0` | 2026-10-04T19:24:43Z | n/a | `89 passed, 16 warnings in 0.14s` |
| `backend/tests/unit/prefect_server/test_retention.py`, `test_app_retention.py`, `test_prefect_event_types.py` | unit | `uv run --no-sync pytest backend/tests/unit/prefect_server/ backend/tests/unit/config/test_task_manager_retention_settings.py -q -n 0` | 2026-10-04T13:01:31Z | n/a | `101 passed, 16 warnings in 1.26s` |
| `backend/tests/component/task_manager/test_event_retention.py::test_prefect_own_events_expire_before_the_activity_log` | component | `uv run --no-sync pytest backend/tests/component/task_manager/test_event_retention.py backend/tests/component/task_manager/test_event.py -q -n 0 -v` | 2026-10-04T12:57:44Z | SQLite Prefect test server | `4 passed, 16 warnings in 11.99s` |
| `backend/tests/unit/task_manager/flow_run/test_cleanup.py`, `backend/tests/unit/cli/test_tasks_flush_flow_runs.py`, `backend/tests/unit/cli/test_upgrade_task_history.py`, `backend/tests/component/task_manager/test_task_history_cleanup.py`, `backend/tests/component/task_manager/test_task_history_routes.py` | unit + component | `cd backend && uv run --no-sync pytest tests/unit/task_manager/flow_run/test_cleanup.py tests/unit/cli/test_tasks_flush_flow_runs.py tests/unit/cli/test_upgrade_task_history.py tests/component/task_manager/test_task_history_cleanup.py tests/component/task_manager/test_task_history_routes.py -p no:cacheprovider --no-cov -q -rA` | 2026-10-04T19:50:22Z | SQLite Prefect test server | `56 passed, 16 warnings in 15.14s` |
| `backend/tests/integration_docker/test_task_history_cleanup.py::TestTaskHistoryCleanup` (flush with rewrite; lock timeout; advisory lock) | integration-docker | `cd backend && uv run --no-sync pytest tests/integration_docker/test_task_history_cleanup.py -p no:cacheprovider --no-cov -rA` | 2026-10-04T19:50:13Z | `INFRAHUB_TESTING_IMAGE_VER=local-infp507`, `INFRAHUB_TESTING_DOCKER_PULL=false`, image built from PR 2 | `3 passed, 16 warnings in 61.55s` |
| `backend/tests/unit/task_manager/event/test_models.py` | unit | `uv run --no-sync pytest backend/tests/unit/task_manager/event/test_models.py -q -n 0` | 2026-10-04T16:52:59Z | n/a | `17 passed, 16 warnings in 0.11s` |
| `backend/tests/component/task_manager/test_event_filter_equivalence.py` (24 cases) | component | `uv run --no-sync pytest backend/tests/component/task_manager/test_event_filter_equivalence.py -q -n 0` | 2026-10-04T16:45:20Z, 16:45:46Z, 16:46:10Z | SQLite Prefect test server | `24 passed` (three runs) |
| `backend/tests/component/task_manager/test_event_query_windows.py`, `backend/tests/component/task_manager/test_event.py` (includes the `since` case and count-only-when-selected) | component | `uv run --no-sync pytest backend/tests/component/task_manager/test_event_query_windows.py backend/tests/component/task_manager/test_event.py backend/tests/unit/task_manager/event/test_models.py -p no:cacheprovider` | 2026-10-04T19:58:04Z | SQLite Prefect test server | `33 passed` |
| `backend/tests/component/graphql/queries/test_event.py` | component | `uv run --no-sync pytest backend/tests/component/graphql/queries/test_event.py -q -n 0` | 2026-10-04T16:53:21Z | Neo4j testcontainer, SQLite Prefect test server | `7 passed, 16 warnings in 56.48s` |
| `frontend/app/src/entities/events/ui/queries/get-events.query.test.ts` (6 tests) | unit (Vitest) | `vitest run src/entities/events/ui/queries/get-events.query.test.ts --reporter=verbose` | 2026-10-04T17:18:47Z | chromium browser mode | `Tests  6 passed (6)` |
| `tests/e2e/activities/test_global_activities.py::TestGlobalActivities::test_load_more_while_new_activities_arrive_shows_each_activity_once[chromium]` | e2e | `INFRAHUB_TESTING_IMAGE_VER=local-infp507-fe INFRAHUB_TESTING_DOCKER_PULL=false uv run --no-sync pytest -c tests/e2e/pytest.ini tests/e2e/activities/test_global_activities.py -v -s --pdb` | 2026-10-04T17:15:35Z | image `local-infp507-fe`, chromium | `…shows_each_activity_once[chromium] PASSED`, `4 passed in 155.35s` |
| `backend/tests/integration_docker/test_prefect_event_types.py` (2 tests) | integration-docker | `uv run --no-sync pytest backend/tests/integration_docker/test_prefect_event_types.py -v -p no:cacheprovider` | 2026-10-04T17:48:47Z and 17:50:41Z | `local-infp507` built from PR 4 | `2 passed, 16 warnings in 108.21s` / `in 106.83s` |
| `backend/tests/unit/cli/test_tasks_background_services.py` (3), `backend/tests/unit/prefect_server/test_app_retention.py` (6) | unit | `uv run --no-sync pytest backend/tests/unit/cli/test_tasks_background_services.py backend/tests/unit/prefect_server/test_app_retention.py -v --timeout 120` | 2026-10-04T18:20:55Z | n/a | `9 passed, 16 warnings in 1.25s` |
| Scale-out stack check of `infrahub tasks background-services` | integration-docker | `INFRAHUB_TESTING_TASKMGR_SCALEOUT=1 … uv run --no-sync pytest backend/tests/integration_docker/test_prefect_event_types.py` | 2026-10-04T18:16:36Z-18:18:21Z | `local-infp507` built from PR 5, `INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY=12d` | `2 passed … in 99.69s`; container log `Task manager retention: PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD=P12D` |
| Final run on the top of the stack: `backend/tests/unit/cli`, `config`, `prefect_server`, `task_manager` | unit | `uv run --no-sync pytest backend/tests/unit/cli backend/tests/unit/config backend/tests/unit/prefect_server backend/tests/unit/task_manager -q -n 4` | 2026-10-04T20:03:29Z | n/a | `498 passed, 80 warnings in 7.84s` |
| Final run on the top of the stack: `backend/tests/component/task_manager` | component | `uv run --no-sync pytest backend/tests/component/task_manager -q -n 4` | 2026-10-04T20:04:24Z | SQLite Prefect test server | `65 passed, 80 warnings in 18.16s` |
| After the free-space fix: `backend/tests/unit/task_manager/flow_run/test_cleanup.py`, `backend/tests/unit/cli/test_upgrade_task_history.py`, `backend/tests/unit/cli/test_tasks_flush_flow_runs.py`, `backend/tests/component/task_manager/test_task_history_cleanup.py`, `backend/tests/component/task_manager/test_task_history_routes.py` | unit + component | `uv run --no-sync pytest <the five files> -p no:randomly -v` | 2026-10-04T20:57:58Z | PR 2 at `4779e7130`, SQLite Prefect test server | `59 passed, 16 warnings in 11.93s` |
| `backend/tests/integration_docker/test_task_history_cleanup.py` (5 tests, including `test_a_cleanup_rewrites_the_tables_freed_by_runs_deleted_before_it_started` and `test_a_cleanup_leaves_tables_of_mostly_live_runs_as_they_are`) | integration-docker | `INFRAHUB_TESTING_IMAGE_VER=local-infp507-fix INFRAHUB_TESTING_DOCKER_PULL=false uv run --no-sync pytest backend/tests/integration_docker/test_task_history_cleanup.py -n 0 -p no:randomly -v` | 2026-10-04T20:51:36Z, and in a different order at 20:53:26Z | image `local-infp507-fix` built from PR 2 | `5 passed, 16 warnings in 67.49s` / `in 67.58s` |
| The same file on the top of the stack | integration-docker | the same, with `INFRAHUB_TESTING_IMAGE_VER=local-infp507-validate2` | 2026-10-04T21:14:56Z | image `local-infp507-validate2` (`sha256:40f5bbbdfcba…`) built from `bc47d990b` | `5 passed, 16 warnings in 81.55s (0:01:21)` |
| Quickstart Part 1 step 5: `docker compose down`, then `docker compose run --rm server infrahub upgrade`, with 120,305 old runs | Compose (T059) | dev stack, project `infp507grillingspec087164` | 2026-10-04T21:08:57Z (failed before the fix at 20:25:16Z) | image `local-infp507-validate2` | `Task history tables: 175.0 MB before, 1.6 MB after` / `Task history tables rewritten` (before the fix: `166.5 MB before, 166.5 MB after` / `not rewritten`) |
| Final run on the top of the stack: backend unit suite | unit | `uv run --no-sync invoke backend.test-unit` | 2026-10-04T21:05:55Z | n/a | `3092 passed, 18 warnings, 6 errors in 89.21s`; the 6 errors are environment failures, see below |
| Final run on the top of the stack: `frontend/app/src/entities/events/ui/queries/get-events.query.test.ts` | unit (Vitest) | `vitest run src/entities/events/ui/queries/get-events.query.test.ts` | 2026-10-04T21:04:43Z | chromium browser mode | `Tests  6 passed (6)` |

Bite checks (each new guard was seen to fail against the code it protects):

- **Cutoff cap**: with the cap removed, the 18:00 run was deleted.
- **Batching**: with one batch only, the logs and artifacts differ.
- **Model import**: before the move, `asyncpg` and `prefect.server.database` were loaded.
- **`since` break**: without the break, only the new case failed, with one extra event.
- **Count**: with the count forced on, the count test fails with `assert 2 is None`.
- **Lock release**: without the release, `409` instead of `202`.
- **Event-type guard**: with one type removed from the list, the test fails and names that type.
- **Activities E2E**: on the previous frontend, 5 activities are shown twice.
- **Free-space rewrite**: against an image of the earlier run-count rule, the new regression test fails with `('completed', 0, False, [])`.

`/pre-ci` failures that come from this machine, not from the branch:

- `ty check .` reports about 119 `unresolved-import` errors on `tests.*`. `ty check backend/infrahub` is clean.
- The `python_testcontainers` tests stop at session start, on psutil `cpu_freq`.
- `markdownlint-cli2` is not installed; the replacement `npx markdownlint-cli2` and vale runs were clean.
- `backend/tests/unit/helpers/test_prefect_diagnostics.py` (not changed by the stack) errors 6 times in the full unit run: its stand-in server subprocess imports `tests` from the editable `python_sdk`. With `PYTHONPATH=backend` it passes: `11 passed, 16 warnings in 2.69s`.
- `yamllint -s .` reads YAML files in the untracked `python_testcontainers/.venv`. On the tracked YAML files it is clean.

## 5. Review findings

Reviews ran in three places:

- cubic, before PR 1 (two passes) and PR 2 (three passes). Later, the user asked to stop running cubic.
- `/pre-ci`, before each push.
- One `speckit-review-run` over the whole stack, with six agents in parallel.

Quickstart run (T059), on a local Compose stack:

| Severity | File | Summary | PR | Outcome |
|---|---|---|---|---|
| High | `prefect_server/task_history.py` | The documented Compose upgrade never rewrote the tables. `docker compose run` starts the task manager, Prefect's own cleanup deletes the old runs within seconds, and the job then counted only the runs left | 2 | Fixed: `if_freed` measures free space in `flow_run`; a regression test fails on the earlier code and passes on the fix; a second Compose run rewrote 175.0 MB down to 1.6 MB |
| Suggestion | upgrade overview, retention knowledge page, spec set | They said that only the first upgrade or a lower retention rewrites the tables, but small tables are rewritten on most upgrades, in milliseconds, because the upgrade replaces Prefect's scheduled runs | 6 | Fixed |

Stack-wide review (no critical findings):

| Severity | File | Summary | PR | Outcome |
|---|---|---|---|---|
| Important | `prefect_server/task_history.py`, `task_manager/flow_run/cleanup.py` | The CLI client imported the server module, which loads `asyncpg` and Prefect's database layer | 2 | Fixed: models moved to `task_history_models.py`, with an import test |
| Important | `task_manager/flow_run/cleanup.py` | The client stayed silent for up to 3 hours while it waited; the give-up message merged three conditions | 2 | Fixed: wait lines; the give-up message names the last reason |
| Important | `prefect_server/task_history.py` | No test of the cutoff cap on the last day (irreversible deletes) | 2 | Fixed, bite-checked |
| Important | `prefect_server/task_history.py` | Batched log and artifact deletes never ran more than one batch | 2 | Fixed, bite-checked |
| Important | `prefect_server/task_history.py` | Postgres advisory lock untested | 2 | Fixed: integration test |
| Important | `prefect_server/task_history.py` | Comment gave the wrong reason for the own connection pool | 2 | Fixed |
| Important | `prefect_server/task_history_models.py` | The job model allows states that should not exist (failed without an error, sizes half set) | 2 | Deferred: needs a model per state and an API contract change |
| Important | `prefect_server/database.py` | No test of the `since` bound in newest-first windows | 3 | Fixed, bite-checked |
| Important | `task_manager/event/query.py` | Count-only-when-selected untested (code from #10379) | 3 | Fixed, bite-checked |
| Important | `prefect_server/app.py`, docs | Claim that the INFO `Task manager retention:` lines never print | 1 | Not acted on: chunks 1b and 7 saw them in the task manager and background-services logs |
| Important | `prefect_server/events.py` | Comment of three sentences | 3 | Left for opsmill/infrahub#10379, where the code comes from |
| Suggestion | `config.py` | Bare `P`/`PT` reported as too long instead of unreadable | 1 | Fixed |
| Suggestion | `changelog/+task-manager-retention.added.md` | "Never deleted" was false | 1 | Fixed |
| Suggestion | `cli/upgrade.py` | `--check` said nothing about the cleanup step | 2 | Fixed |
| Suggestion | `cleanup.py` | A failed job's committed work was not printed | 2 | Partial: deleted runs and a completed rewrite are printed; tables rewritten before a mid-rewrite failure are not recorded |
| Suggestion | `task_history.py`, `cleanup.py` | Two simplifications | 2 | Fixed |
| Suggestion | `prefect_server/models.py`, e2e test | Misleading `retention_seconds` description; a comment that restates the code | 3 | Fixed |
| Suggestion | `dev/knowledge/backend/task-manager-retention.md` | Three statements did not match the code | 6 | Fixed |
| Suggestion | several | Rewriter `None` on SQLite; `since` read from `model_fields_set`; 36,500-day maximum defined twice; a repeated `VACUUM FULL` when a load balancer spreads requests across replicas; retry warning on the last attempt (#10379) | 2, 3 | Deferred; the last one goes to #10379 |

cubic findings on PR 1 and PR 2 (16 in total) were all fixed or recorded as known limitations in the PR bodies.

## 6. Autonomous decisions

1. **Base branch**: the stack targets `develop`, not `stable`, per the git workflow. `develop` is still the 1.12 line, so the base may need to change if 1.12 is cut before this merges.
2. **Tasks moved between PRs**:
   - T047 moved to PR 1, as the test of T007.
   - T002, T041, T042 and T043 moved to PR 1, so `prefect_own_events` works from the first PR (a cubic finding).
   - T001 moved to PR 2.
3. **Retention maximum**: 36,500 days, a technical safety bound. The design doc said "no upper limit"; the spec set is updated.
4. **Rewrite modes (deviation from the design doc, D9)**:
   - `flush flow-runs --rewrite` always rewrites.
   - Only the upgrade step keeps the "deletes freed most of the tables" condition, measured as free space in `flow_run` (item 11).

   Applied to the explicit command, that condition would leave Helm users and anyone who lowers a retention without disk back, because Prefect's hourly cleanup deletes the runs first. The Notion page still has the old wording.
5. **A failed cleanup no longer stops the upgrade**: the error and the command to finish it are printed, and the upgrade goes on to the branch rebase. Before, it stopped while exiting 0.
6. **"Primary Node" Activities filter**: it keeps today's label matching unless the request lists event types. ID matching would drop branch merged/deleted and group auto-created events from the timelines.
   [CLAUDE RECOMMENDED – based on the task manager owning its event query] Match the indexed resource ID, OR the label limited to those three event types. This needs the tech owner's decision, and is in PR 3's body.
7. **Carrying opsmill/infrahub#10379**: PR 3 carries the two commits with `cherry-pick -x`. Nothing was posted on that PR.
8. **Reviews**: cubic ran on PR 1 and PR 2 only, because the user asked to stop after PR 2. `/pre-ci` ran before every push. One stack-wide `speckit-review-run` ran at the end, and its fixes were applied on the branch that introduced each issue, then the stack was rebased and force-pushed with lease.
9. **GitHub stacked PRs**: the `github/gh-stack` extension was installed. PRs were created with `gh pr create --draft` and linked with `gh stack link`, never `gh stack submit`, which may rewrite the PR bodies.
10. **No change to the public GraphQL schema**: the `since` description still says 180 days.
11. **`if_freed` measures free space, not runs (FR-011 changed)**: the upgrade rewrites the tables when the live rows of `flow_run` take less than half of its size on disk, whoever deleted the runs and when. The earlier rule compared the runs left with the runs counted when the job started, so it missed the runs that Prefect's cleanup deletes when the task manager starts. The design doc's "freed most of the tables" describes space, so this follows the doc more closely than the run count did.
    - Side effects: an upgrade that applies a lower retention now rewrites the tables, and small tables are rewritten on most upgrades, in milliseconds.
    - Rejected: rewriting on every upgrade. With a long retention and a lot of retained task history, each upgrade would need free disk for a full copy of the tables.

## 7. Suggested next steps

1. **Maintainer approval of the constitution deviation**: the cleanup route deletes data without authentication (Principle VI). It is recorded in PR 2's body.
2. **Tech owner decision on the "Primary Node" filter** (§6 item 6).
3. **Helm chart PR (T050), in the same release**:
   - the background-services deployment runs `infrahub tasks background-services`;
   - the upgrade hook passes `--no-task-history-cleanup`;
   - the retention values go in `values.yaml`.

   The Enterprise sizing presets run the background services in their own pod, so the hourly deletion does not run there until this chart PR ships.
4. **Private-tests evidence** (T021-T024, T037-T039, T046, then T057 on the release candidate): run it in a separate session in opsmill/infrahub-private-tests, and attach the results to the PRs and to INFP-507.
5. **Update the Notion design doc for the decisions made here**:
   - the rewrite modes, and the free-space measure of `if_freed`;
   - the upgrade continuing after a failed cleanup;
   - the 36,500-day maximum;
   - the "Primary Node" filter;
   - the GraphQL `since` description (180 days), which needs a schema change.
6. **Telemetry spec**: it assumes task history reaches back well beyond 24 hours, but the retention can now be 1 day.
7. **When opsmill/infrahub#10379 merges**: rebase the stack to drop its two carried commits, and send it the review findings on its code.
8. **Deferred review items** (§5): if wanted, give the job model one model per state.
