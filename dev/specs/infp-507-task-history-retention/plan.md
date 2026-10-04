# Implementation Plan: Task History and Activity Log Retention

**Branch**: `task-history-retention-infp-507` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-507-task-history-retention/spec.md`, with the [Notion design doc](https://app.notion.com/p/opsmill/Task-history-and-Activity-log-retention-3dc228b830258012ba28dc3a23eece65) as the source of truth for technical decisions (D1-D10).

## Summary

Bound the task manager's storage and make the activity log retention configurable, without adding tables or indexes to Prefect's database:

- **Task history (part 1)**: turn on Prefect's built-in cleanup of old runs, driven by a new Infrahub retention setting; reimplement `infrahub tasks flush flow-runs` as a task-manager job that deletes with set-based SQL and optionally rewrites the tables; run it with the rewrite in the Compose upgrade.
- **Activities page (part 2)**: filter on Prefect's indexed resource IDs instead of labels, read newest first in widening time windows, count only on request, plan each query for its values (PR #10379), and page by time on the frontend.
- **Activity log (part 3)**: keep Infrahub events for the activity log retention and delete Prefect's own events after their own retention, through a list of Prefect event types guarded by a test.
- **Documentation (part 4)**: configuration reference, CLI reference, upgrade guides, sizing, knowledge docs.

Research and code locations: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 / React 19 (frontend)

**Primary Dependencies**: FastAPI, Pydantic settings, Prefect 3.8.6 (embedded task manager), SQLAlchemy (through Prefect's database interface), TanStack Query

**Storage**: Prefect's task-manager database (Postgres 14 in the Helm chart, 18 in Compose; SQLite in the component test harness). No schema change.

**Testing**: pytest (unit, component with the Prefect test harness, functional), Vitest, Playwright E2E; private performance tests in infrahub-private-tests

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
| II. Branch-Safe by Default | Pass | No graph query changes. Branch filters resolve names through the branch registry; deleted branches through their deletion event. Branch-deletion purge of runs unchanged. |
| III. Type Safety & Explicit Contracts | Pass | Pydantic settings section and request/response models for the new routes; contracts written before implementation (contracts/). |
| IV. Test Discipline | Pass | Unit tests for settings and filter construction; component tests for the cleanup and filter equivalence on the Prefect harness; functional test for the event-type list; Vitest for paging; an E2E test for Activities "load more" without the count. |
| V. Query Performance | Pass | SQL built with SQLAlchemy Core, parameterized. Plans validated with EXPLAIN in the design-doc benchmark; regression covered by private performance tests. |
| VI. Security & Input Boundaries | **Deviation (justified)** | The new cleanup route mutates without authentication. See Complexity Tracking. Settings input is validated at start. |
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
│   ├── database.py                    # newest-first time windows, optional count, plan per query
│   ├── events.py, models.py           # include_count, retention window, nullable total
├── task_manager/
│   ├── event/models.py                # account/branch/node/parent/branch-name filters on resource IDs
│   ├── event/query.py                 # pass include_count, nullable count
│   └── flow_run/retention.py          # FlowRunRetention kept for stale-runs
├── graphql/queries/event.py           # include_count from selected fields, branch name → ID resolution
└── cli/
    ├── tasks.py                       # flush flow-runs via the job, background-services command
    └── upgrade.py                     # task history cleanup step, --no-task-history-cleanup

backend/tests/
├── unit/task_manager/event/           # filter construction
├── unit/prefect_server/               # settings translation and validation
├── component/task_manager/            # cleanup equivalence, filter equivalence, cleanup routes, count
└── functional/                        # Prefect event-type list guard

frontend/app/src/entities/events/      # page by `until`, drop `count`, dedupe by id
tests/e2e/                             # Activities load more without count

python_testcontainers/infrahub_testcontainers/docker-compose*.test.yml  # background-services command
tasks/docs.py                          # add `infrahub tasks` to the CLI reference
docs/docs/deploy-manage/maintain-upgrade/upgrade/*.mdx, docs/docs/reference/*  # docs (reference regenerated)
dev/knowledge/backend/{events,async-tasks}.md, dev/adr/0002-events-system.md   # knowledge and ADR updates
changelog/                             # fragments per part
```

**Structure Decision**: Existing backend/frontend layout. New task-manager code lives in `backend/infrahub/prefect_server/` next to Infrahub's existing routes, because only the task manager connects to Prefect's database. The Helm chart change (background-services command, `--no-task-history-cleanup` in the upgrade hook arguments) is a separate PR in opsmill/infrahub-helm.

## Delivery Order

1. **Part 1, task history** (independent): settings section and translation, flow-run vacuum on, cleanup job and routes, `flush flow-runs` rewrite, upgrade step and flag, background-services command, stale-runs documentation, cleanup equivalence test.
2. **Part 2, Activities page** (before part 3): PR #10379 merged first or carried in; ID filters and branch resolution; time windows; optional count; frontend paging by time and no count (frontend change waits for Q2); filter equivalence test.
3. **Part 3, activity log retention**: Prefect event-type list and its guard test; activity log and own-event retentions applied; defaults.
4. **Part 4, documentation**: ships with parts 1 and 3.

## Risks

| Risk | Mitigation |
|---|---|
| Upgrade step takes hours on large instances (Q1) | Per-day commits, progress output, re-runnable; operators can set a longer retention before upgrading. Release notes wait for the 100 GB figure. |
| Product refuses removing the total count (Q2) | Backend changes ship regardless; only the frontend change waits. |
| SQL cleanup drifts from Prefect's rules on a Prefect upgrade | Cleanup equivalence component test in CI. |
| New Prefect event type not in the list | Functional guard test in CI; a missed type only costs disk. |
| Filter results change on a Prefect upgrade | Filter equivalence component test in CI. |
| Helm hook rewrites tables on a live instance | Chart passes `--no-task-history-cleanup`; 404 path covers older charts against the first release. |
| Operators already set PREFECT_* variables by hand | Explicit values win, with a warning. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Unauthenticated mutating route on the task manager (Principle VI) | The cleanup must run inside the task manager, the only process connected to Prefect's database; Infrahub's existing task-manager route has no authentication either. | Adding authentication to the task manager is out of scope (decided 2026-10-04): the route is reachable only on the internal network, like Prefect's own API, which already allows deleting runs. |
| Background job with status polling instead of a single request (Principle VII) | The cleanup can run for over an hour; a request-bound cleanup stops when the session or a proxy drops the connection. | A single blocking request fails on any HTTP timeout during the upgrade. |
