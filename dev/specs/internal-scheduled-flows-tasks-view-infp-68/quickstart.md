# Quickstart: validating internal & scheduled background flows in the Tasks view

**Feature**: `internal-scheduled-flows-tasks-view-infp-68`

**Date**: 2026-09-24

How to prove the feature works. Scenario numbers map to the spec's acceptance
scenarios and success criteria; contract details live in
[`contracts/graphql.md`](./contracts/graphql.md) and entity shapes in
[`data-model.md`](./data-model.md) — neither is repeated here.

---

## Prerequisites

```bash
uv sync --all-groups
cd frontend/app && pnpm install
```

A Docker daemon is required for component, integration and e2e runs (the
testcontainers stack boots Prefect, Neo4j and the workers). Set
`INFRAHUB_USE_TEST_CONTAINERS=false` to reuse an already-running database.

---

## Fast loop (no Docker)

Run while iterating. Both should finish in seconds.

```bash
uv run pytest backend/tests/unit/task_manager/ backend/tests/unit/graphql/queries/test_task.py -q
cd frontend/app && pnpm test
```

These cover the tag-filter composition (R1), the health-verdict precedence (R6),
the cron-interval derivation (R5), the schedule-sentence helper (R8) and the
filter-form/type-facet components. None of them needs Prefect.

---

## Scenario 1 — the default Tasks list did not move (SC-005, FR-003, FR-021)

The single most important regression check in the feature. It must assert
**observed membership**, never "no internal runs are returned" — writing it the
second way encodes the regression it exists to catch (FR-003).

```bash
uv run pytest backend/tests/component/graphql/queries/test_task.py -q
```

Expected: with `workflow_type` omitted, the runs returned and the `count` are
identical to the pre-change baseline — including runs of the eight internal
workflows that tag themselves via `add_tags()`.

Manual confirmation:

```graphql
query { InfrahubTask(limit: 50) { count edges { node { id workflow workflow_type } } } }
```

Runs with `workflow_type: INTERNAL` **should** be present. Their absence is the
regression.

---

## Scenario 2 — the Type facet reaches wholly-hidden internal runs (US3, FR-002)

```graphql
query { InfrahubTask(workflow_type: [INTERNAL], limit: 50) { count edges { node { title workflow workflow_type } } } }
```

Expected: runs of workflows that never call `add_tags()` —
`clean-up-deadlocks`, `git_repositories_sync`, `merge-watcher` — appear. These
are invisible without the argument.

Then confirm FR-004, the distinction the UI must not blur:

```graphql
query { all: InfrahubTask(workflow_type: [CORE, USER, INTERNAL]) { count }
        dflt: InfrahubTask { count } }
```

Expected: `all.count > dflt.count`. Equality means the type tags are not being
used and the two selections have been collapsed.

Compose with another facet (FR-005):

```graphql
query { InfrahubTask(workflow_type: [INTERNAL], state: [FAILED, CRASHED]) { count } }
```

Empty-list rejection (`data-model.md` §1):

```graphql
query { InfrahubTask(workflow_type: []) { count } }
```

Expected: an `errors[]` entry, **not** an unfiltered result.

---

## Scenario 3 — the scheduled-flows view (US1, SC-002, FR-009…FR-011)

```bash
uv run pytest backend/tests/component/task_manager/ -q
```

Then against a running stack:

```graphql
query {
  InfrahubScheduledFlows {
    count
    catalogue_only
    edges { node {
      name workflow_type cron interval_seconds next_run_at active
      collision_strategy health
      latest_run { state state_name expected_start_time start_time }
      recent_outcomes { window_hours total counts { state count } }
    } }
  }
}
```

Expected: all five catalogue schedules present — `git_repositories_sync`,
`clean-up-deadlocks`, `merge-watcher` (`* * * * *`),
`anonymous_telemetry_send` (`~ 2 * * *`), `webhook-configure` (`~ 3 * * *`).
`catalogue_only` is empty on a fully-registered instance. Unhealthy entries sort
first.

Scenario 1.4 (never run) — on a freshly-booted instance the daily flows have no
history and must read `NEVER_RUN`, never an error, empty cell, or success.

---

## Scenario 4 — the motivating incident (SC-003, FR-011)

The one that justifies the feature. Stop the worker so the every-minute flows
stop producing runs, wait past three intervals, and confirm the verdict flips.

```bash
PROJECT=$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep infrahub | head -1)
docker compose -p "$PROJECT" stop task-worker
sleep 200
```

Expected: `clean-up-deadlocks`, `git_repositories_sync` and `merge-watcher`
report `health: OVERDUE`. Restart the worker and confirm they return to
`HEALTHY` once a run lands.

```bash
docker compose -p "$PROJECT" start task-worker
```

---

## Scenario 5 — a collision cancellation is not a crash (Assumption 8)

The three every-minute flows use `CANCEL_NEW`, so collisions occur in normal
operation. Find one:

```graphql
query { InfrahubTask(workflow_type: [INTERNAL], state: [CANCELLED], limit: 5) {
  edges { node { title state workflow } } } }
```

Expected in the scheduled-flows view: the flow reports `health: CANCELLED`, and
its `latest_run` has `expected_start_time` set with `start_time: null` — the
signature of a run cancelled before it began. It must not be rendered
identically to a crash, and must not be counted as success.

---

## Scenario 6 — errors are loud (FR-013, FR-019)

```bash
docker compose -p "$PROJECT" stop prefect-server
```

Expected: `InfrahubScheduledFlows` returns `errors[]` with `data: null`, and the
UI renders its error state. An empty list reading as "all healthy" is the
failure this scenario exists to catch.

---

## Scenario 7 — frontend end to end (US1, US2, SC-001, SC-008, SC-011)

```bash
uv run pytest -c tests/e2e/pytest.ini tests/e2e/tasks -s --pdb
```

`--pdb` is not optional advice here — per `AGENTS.md`, a failure without it
costs a full stack boot to re-attach.

Walks: Tasks view → scheduled-flows view (≤2 clicks, SC-001) → every scheduled
flow listed with schedule, last-run outcome and elapsed time → drill into one →
task list scoped to that workflow, unfiltered by state → open a run → logs
render (SC-008). Then the Type facet: apply Type = System, confirm the list and
count both narrow, the URL carries the filter across a reload (FR-023), and
branch/related-node cells render empty rather than erroring (FR-024).

SC-011 (never colour alone) is asserted by locating each health verdict by its
accessible text, not by a class or colour.

---

## Before pushing

```bash
uv run invoke format && uv run invoke lint
uv run invoke backend.generate
uv run invoke schema.generate-graphqlschema
uv run invoke docs.generate && uv run invoke docs.validate
cd frontend/app && pnpm codegen
cd frontend && pnpm exec biome ci .
cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test
```

Or run `/pre-ci`, which wraps these plus the whole-repo
`ruff check . --exclude python_sdk` that `invoke lint` alone does not cover.

CI fails if any generated file is stale, so the `codegen` /
`generate-graphqlschema` output must be committed alongside the change.
