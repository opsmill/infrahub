# Implementation Plan: Task History and Activity Log Retention

**Branch**: `task-history-retention-infp-507` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-507-task-history-retention/spec.md`, with the [Notion design doc](https://app.notion.com/p/opsmill/Task-history-and-Activity-log-retention-3dc228b830258012ba28dc3a23eece65) as the source of truth for technical decisions (D1-D10).

## Summary

Bound the task manager's storage and make the activity log retention configurable, without adding tables or indexes to Prefect's database:

- **Task history (part 1)**: turn on Prefect's built-in cleanup of old runs, driven by a new Infrahub retention setting; reimplement `infrahub tasks flush flow-runs` as a task-manager job that deletes with set-based SQL and optionally rewrites the tables; run it in the Compose upgrade, which rewrites the tables when more than half of their disk space is free after the deletes, whoever deleted the runs.
- **Activities page (part 2)**: filter on Prefect's indexed resource IDs instead of labels, read newest first in widening time windows, count only on request, plan each query for its values (PR #10379), and page by time on the frontend.
- **Activity log (part 3)**: keep Infrahub events for the activity log retention and delete Prefect's own events after their own retention, through a list of Prefect event types guarded by a test.
- **Documentation (part 4)**: configuration reference, CLI reference, upgrade guides, sizing, knowledge docs.

Research and code locations: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 / React 19 (frontend)

**Primary Dependencies**: FastAPI, Pydantic settings, Prefect 3.8.6 (embedded task manager), SQLAlchemy (through Prefect's database interface), TanStack Query

**Storage**: Prefect's task-manager database (Postgres 14 in the Helm chart, 18 in Compose; SQLite in the component test harness). No schema change.

**Testing**: pytest (unit, component with the Prefect test harness, integration-docker), Vitest, Playwright E2E. **Release evidence**: performance and behaviour tests in opsmill/infrahub-private-tests on restored backups with real task history and activity log, on Postgres 14 and 18; each part ships only with its results attached to the PR and to INFP-507

**Target Platform**: Linux containers (Compose, Helm)

**Project Type**: Web service (backend + frontend) with an operator CLI

**Performance Goals**: Indicative, from the design doc: Activities default view and single filters about 1 s repeat / 3 s first load with a year of activity log; combined filters 3 to 6 s, at most 10 s; Compose upgrade about 8.5 min longer per 25 GB of task history

**Constraints**: No new tables, indexes or extensions in Prefect's database; queries must work on Postgres 14 and later; Infrahub sets Prefect settings, it does not patch Prefect

**Scale/Scope**: Up to 15M+ events for a year of activity log; 25 to 100+ GB of task history at upgrade

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | Pass | No Infrahub schema or graph change. Generated docs regenerated, not edited. |
| II. Branch-Safe by Default | Pass | No graph query changes. Branch filters resolve names to IDs from the database; deleted branches through their deletion event. Branch-deletion purge of runs unchanged. |
| III. Type Safety & Explicit Contracts | Pass | Pydantic settings section and request/response models for the new routes; contracts written before implementation (contracts/). |
| IV. Test Discipline | Pass (with private-test evidence) | Unit tests for settings and filter construction; component tests for the cleanup and filter equivalence on the Prefect harness; integration-docker guard and a unit test for the event-type list; Vitest for paging; an E2E test for Activities "load more" while new events arrive; the private performance tests provide the evidence at production scale that CI cannot (backups with 25 to 100 GB of task history and a year of activity log). |
| V. Query Performance | Pass | SQL built with SQLAlchemy Core, parameterized. Plans validated with EXPLAIN in the design-doc benchmark; regression covered by private performance tests. |
| VI. Security & Input Boundaries | **Deviation (needs maintainer approval)** | The new cleanup route mutates without authentication. Decided by the tech owner on 2026-10-04; the constitution allows a deviation only with maintainer approval, so the PR description asks for it explicitly. The route takes only `rewrite`. See Complexity Tracking. Settings input is validated at start. |
| VII. Simplicity | Pass, with one justified addition | The background job with status polling exists so that a dropped session or HTTP timeout during a long upgrade does not stop the cleanup. See Complexity Tracking. |

**Post-design re-check**: unchanged. No new dependency, no new abstraction with fewer than two callers (the settings translation serves the task manager and the background-services command; the cleanup job serves the CLI and the upgrade).

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-507-task-history-retention/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── configuration.md
│   ├── cli.md
│   └── task-manager-api.md
├── checklists/requirements.md
└── tasks.md            # next phase
```

### Source Code (repository root)

```text
backend/infrahub/
├── config.py                          # new retention settings section (validation)
├── prefect_server/
│   ├── app.py                         # load config in all modes, apply derived Prefect settings, mount cleanup router
│   ├── retention.py                   # new: settings translation + PREFECT_EVENT_TYPES list
│   ├── task_history.py                # new: cleanup job (SQL deletes per day, rewrite on Postgres) + routes
│   ├── task_history_models.py         # new: request and job models the routes and the client share
│   ├── database.py                    # newest-first time windows, optional count, plan per query
│   ├── events.py, models.py           # include_total, retention window, nullable total
├── task_manager/
│   ├── event/models.py                # account/branch/node/parent/branch-name filters on resource IDs
│   ├── event/query.py                 # pass include_total, nullable count
│   └── flow_run/retention.py          # FlowRunRetention kept for stale-runs
├── graphql/queries/event.py           # include_total from selected fields, branch name → ID resolution
└── cli/
    ├── tasks.py                       # flush flow-runs via the job, background-services command
    └── upgrade.py                     # task history cleanup step, --no-task-history-cleanup

backend/tests/
├── unit/task_manager/event/           # filter construction
├── unit/prefect_server/               # settings translation and validation
├── component/task_manager/            # cleanup equivalence, filter equivalence, cleanup routes, count
├── unit/prefect_server/test_prefect_event_types.py  # every built-in Prefect state in the list
└── integration_docker/                # Prefect event-type list guard on the full stack

frontend/app/src/entities/events/      # page by `until` (`since` in ascending order), dedupe by id
tests/e2e/                             # Activities load more while new events arrive, no event twice

python_testcontainers/infrahub_testcontainers/docker-compose*.test.yml  # background-services command
tasks/docs.py                          # add `infrahub tasks` to the CLI reference
docs/docs/deploy-manage/maintain-upgrade/upgrade/*.mdx, docs/docs/reference/*  # docs (reference regenerated)
dev/knowledge/backend/{events,async-tasks}.md, dev/adr/0002-events-system.md   # knowledge and ADR updates

# opsmill/infrahub-private-tests (separate repository): release evidence
tests/performance/test_activity_log.py (PR #33), test_activity_log_concurrency.py, test_activity_log_retention.py,
tests/performance/test_task_history_retention.py, test_task_history_upgrade.py, test_task_history_cleanup_load.py, test_database_size.py
changelog/                             # fragments per part
```

**Structure Decision**: Existing backend/frontend layout. New task-manager code lives in `backend/infrahub/prefect_server/` next to Infrahub's existing routes, because only the task manager connects to Prefect's database. The Helm chart change (background-services command, `--no-task-history-cleanup` in the upgrade hook arguments) is a separate PR in opsmill/infrahub-helm.

## Evidence: infrahub-private-tests

CI proves the logic on small seeded data; only the private tests prove the outcomes at the scale that caused the incidents. They run through the `test-dataset` workflow of opsmill/infrahub-private-tests on restored backups that include `prefect.dump`, on Postgres 14 (Helm) and 18 (Compose), and their report is attached to each PR and to INFP-507.

| Part | Private tests | Proves |
|---|---|---|
| 1. Task history | `test_task_history_retention.py`, `test_task_history_upgrade.py`, `test_task_history_cleanup_load.py`, `test_database_size.py` (extended) | Old runs deleted, newer and stuck runs kept, settings reach a separate background-services container; upgrade duration, extra disk and size before/after on 25 and 100 GB (Q1); no lock waits, deadlocks or task errors under load; size and dead space per table over time |
| 2. Activities page | PR #33 `test_activity_log.py` (landed, retention override switched to the Infrahub setting, extended), `test_activity_log_concurrency.py` | Identical results to the previous release; no plan flip on repeated queries; time windows; combined filters within 10 s; deep paging by time on Postgres 14 and 18 (open measurement); many users paging at once |
| 3. Activity log | `test_activity_log_retention.py` | No Infrahub event deleted, no orphaned related item, nothing newer than the retentions deleted, every stored Prefect event type in the list |

**Recommendation: run the private tests in a new session.** The evidence tasks (T021-T024, T037-T039, T046, T057) live in another repository, so `/speckit.opsmill.implement` in this repository cannot do them. Start a separate Claude Code session in a checkout of opsmill/infrahub-private-tests, once a test image of this branch exists, with a prompt such as:

```text
INFP-507 release evidence. Spec: dev/specs/infp-507-task-history-retention in opsmill/infrahub
(branch task-history-retention-infp-507), tasks T021-T024, T037-T039, T046, T057 in tasks.md and
the "Evidence: infrahub-private-tests" section of plan.md. Start from PR #33 (TestActivityLog) and
switch its retention override to INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG. Image: <tag of the
branch build>. Run through the test-dataset workflow on backups that include prefect.dump, on
Postgres 14 and 18, and report the results for the PR and INFP-507.
```

Keeping it separate keeps this repository's implementation context free of the private-tests code, and lets the evidence work start as soon as part 1 has an image, in parallel with parts 2 and 3.

## Delivery Order

1. **Part 1, task history** (independent): settings section and translation, flow-run vacuum on, cleanup job and routes (advisory lock, Prefect's delete order of runs then children, rewrite modes `never`, `if_freed` for the upgrade and `always` for the command's rewrite option, rewrite lock timeout with retries), `flush flow-runs` reimplementation without `--days-to-keep` and `--batch-size`, upgrade step and `--no-task-history-cleanup`, background-services command, stale-runs documentation, cleanup equivalence and concurrency tests, Postgres run of the cleanup test in the integration-docker tier. The infrahub-helm PR (background-services command, `--no-task-history-cleanup` in the upgrade hook arguments) ships in the same release.
2. **Part 2, Activities page** (before part 3): PR #10379 merged first or carried in; ID filters and branch resolution; time windows; optional count; frontend paging by time (the page already omits `count`); filter equivalence test.
3. **Part 3, activity log retention**: Prefect event-type list and its guard test; activity log and own-event retentions applied; defaults.
4. **Part 4, documentation**: ships with parts 1 and 3.

Each of parts 1 to 3 merges only with its private-test evidence. The final run on the release candidate (T057) covers all three together. The release notes explain how to raise the activity log retention and its cost, and the Helm upgrade notes lead with the maintenance step and its expected duration.

## Risks

| Risk | Mitigation |
|---|---|
| Upgrade step takes hours on large instances (Q1) | Per-day commits, progress output, re-runnable; operators can set a longer retention before upgrading. Release notes wait for the 100 GB figure. |
| API clients that select `count` | They still get it, and still wait for it (about 10 minutes for level 0 events on a year of activity log), as the design doc states. |
| SQL cleanup drifts from Prefect's rules on a Prefect upgrade | Cleanup equivalence component test in CI. |
| New Prefect event type not in the list | Integration-docker guard on the full stack (real workers, failure paths) plus a unit test over every built-in Prefect state; a missed type only costs disk. |
| Filter results change on a Prefect upgrade | Filter equivalence component test in CI. |
| Behaviour proven only on small CI data | Private tests on restored production-scale backups for each part, on both Postgres versions, attached as evidence. |
| PR #33's retention override bypasses the new Infrahub setting | Switch it to `INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG` (T037). |
| The Helm upgrade hook runs while the instance is serving | The chart passes `--no-task-history-cleanup`, and Helm users run the cleanup in a maintenance step after the rollout. Without the flag, the upgrade rewrites the tables whenever more than half of their disk space is free, including the space that Prefect's hourly cleanup freed before the upgrade. The 404 path covers a chart without the flag on the first release. |
| Operators already set PREFECT_* variables by hand | Explicit values win, with a warning naming the hidden Infrahub setting. |
| Several task-manager replicas run two cleanups | Postgres advisory lock; the CLI retries on "running elsewhere" or an unknown job. |
| The cleanup and Prefect's now-enabled vacuum run at the same time | Same order as Prefect (runs, then their children); Prefect skips locked runs and each side deletes children only for its own runs, so they cannot deadlock; the concurrency test (T009) guards it. |
| A table rewrite waits forever on a lock, or makes queries queue behind it | 60 s lock timeout per table, up to 3 retries; skipped tables are reported. |
| Existing cleanup scripts pass `--days-to-keep` or `--batch-size` | Removed per the design doc; the changelog marks the change as breaking and the CLI reference documents the retention setting. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Unauthenticated mutating route on the task manager (Principle VI) — needs maintainer approval at PR review | The cleanup must run inside the task manager, the only process connected to Prefect's database; Infrahub's existing task-manager route has no authentication either. | Adding authentication to the task manager is out of scope (decided by the tech owner, 2026-10-04): the route is reachable only on the internal network, like Prefect's own API, which already allows deleting runs. |
| Background job with status polling instead of a single request (Principle VII) | The cleanup can run for over an hour; a request-bound cleanup stops when the session or a proxy drops the connection. | A single blocking request fails on any HTTP timeout during the upgrade. |
