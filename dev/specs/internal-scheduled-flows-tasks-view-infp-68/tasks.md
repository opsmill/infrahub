---
description: "Task list for internal & scheduled background flows in the Tasks view"
---

# Tasks: Internal & Scheduled Background Flows in the Tasks View

**Input**: Design documents from `specs/internal-scheduled-flows-tasks-view-infp-68/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md),
[research.md](./research.md), [data-model.md](./data-model.md),
[contracts/graphql.md](./contracts/graphql.md), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution IV (Test Discipline) requires them, and
SC-005 names an automated regression test as the acceptance mechanism.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable — different file, no dependency on an incomplete task
- **[Story]**: US1 / US2 / US3 from spec.md

## Path Conventions

Web app: `backend/infrahub/…`, `backend/tests/…`, `frontend/app/src/…`,
`tests/e2e/…`. Paths below are repo-relative and exact.

---

## Planning note — a correction to the spec's slice boundary

The spec's *Delivery Independence* section assigns the conditional-namespace
filter change (FR-002) and the `workflow_type` argument (FR-007) to **Slice B**.
That is one requirement too narrow.

US2's drill-down navigates to the Tasks list scoped to one internal workflow
(`/tasks?workflow=clean-up-deadlocks`). Without the type-aware filter, that list
still demands `TAG_NAMESPACE` and returns nothing for the eleven wholly-hidden
workflows — the drill-down would dead-end on exactly the flows it exists to
investigate.

So the whole selection-layer change is **foundational for all three stories**,
not Slice-B-only. Phase 2 below reflects that. Slice A and Slice B remain
independently shippable *above* Phase 2, which is what the spec's delivery
argument actually depends on.

---

## Phase 1: Setup

**Purpose**: nothing to scaffold — the repo, dependencies and tooling already
exist, and the plan adds no dependency (research R5, R8).

- [ ] T001 Confirm the working tree is on branch `OPS-21-show-internal-and-scheduled-background-flows-in-the-tasks-view-infp-68` and that `uv sync --all-groups` and `cd frontend/app && pnpm install` complete cleanly
- [ ] T002 [P] Create the backend package directory `backend/infrahub/task_manager/scheduled_flow/` with an `__init__.py`, following the sibling layout of `backend/infrahub/task_manager/flow_run/`
- [ ] T003 [P] Create the test package `backend/tests/unit/task_manager/scheduled_flow/` with an `__init__.py`, mirroring `backend/tests/unit/task_manager/flow_run/`

---

## Phase 2: Foundational (blocks every user story)

**Purpose**: teach the flow-run selection layer about workflow type. Every story
depends on this; nothing user-visible ships from it alone.

**Requirements covered**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006,
FR-007, FR-008, FR-025

### Tests first

- [ ] T004 [P] Extend `backend/tests/unit/task_manager/flow_run/test_filters.py::TestBuildFlowRunFilter` with the FR-002/FR-004/FR-005 matrix: no type requested ⇒ `tags.all_ == [TAG_NAMESPACE]` and `tags.any_ is None`; `workflow_types=[INTERNAL]` ⇒ `TAG_NAMESPACE` absent from `all_` and `any_ == ["infrahub.app/workflow-type/internal"]`; all three types ⇒ three entries in `any_`; branch + type together ⇒ branch tag in `all_`, type tags in `any_`; related-node + type compose the same way
- [ ] T005 [P] Extend `backend/tests/unit/task_manager/flow_run/test_tags.py` with cases for `WorkflowTagDecoder.workflow_type`: a run tagged `infrahub.app/workflow-type/internal` decodes to `WorkflowType.INTERNAL`; a run with no type tag returns `None`; an unrecognised type value returns `None` rather than raising
- [ ] T006 [P] Add a test to `backend/tests/unit/graphql/queries/test_task.py` asserting that `InfrahubTask(workflow_type: [])` raises a `ValidationError` and is **not** coerced to unset (data-model.md §1, FR-004)

### Implementation

- [ ] T007 Add `workflow_type(self, flow: FlowRun) -> WorkflowType | None` to `WorkflowTagDecoder` in `backend/infrahub/task_manager/flow_run/tags.py`, mirroring the prefix-strip approach of the existing `branch_name`, returning `None` for an absent or unrecognised value
- [ ] T008 Add `workflow_types: list[WorkflowType] | None = None` to `FlowRunQueryCriteria` and `workflow_type: WorkflowType | None = None` to `EnrichedFlowRun`, both in `backend/infrahub/task_manager/flow_run/models.py`
- [ ] T009 Rewrite the tag construction in `FlowRunFilterBuilder.build_flow_run_filter` (`backend/infrahub/task_manager/flow_run/filters.py`): build `all_` from branch, related-node and caller tags, appending `TAG_NAMESPACE` **only when `criteria.workflow_types` is falsy**; set `any_` to the rendered `WorkflowTag.WORKFLOWTYPE` tags when types were requested; pass `all_=None` when the AND list is empty so the cache key stays clean. Verified semantics in research R1 — do not add a second `FlowRunFilterTags`
- [ ] T010 In `PrefectTaskService.query` (`backend/infrahub/task_manager/flow_run/service.py`), populate `EnrichedFlowRun.workflow_type` from `self.tag_decoder.workflow_type(flow)` alongside the existing `branch` decode
- [ ] T011 Add `WorkflowTypeEnum = Enum.from_enum(WorkflowType)` and the `workflow_type` field to `TaskNodeInterface` in `backend/infrahub/graphql/types/task.py`, following the existing `TaskState = Enum.from_enum(StateType)` pattern (contracts/graphql.md §1, §4)
- [ ] T012 In `backend/infrahub/graphql/queries/task.py`: add `workflow_type=List(WorkflowTypeEnum)` to the `Task` field; thread it through `Tasks.resolve` and `Tasks.query` into `FlowRunQueryCriteria.workflow_types`; raise `ValidationError` on an explicitly-empty list; emit `workflow_type` from `FlowRunConnectionSerializer._serialize_node`. Leave `TaskBranchStatus` untouched
- [ ] T013 Run `uv run invoke schema.generate-graphqlschema` and commit the regenerated `schema/schema.graphql`
- [ ] T014 Run `cd frontend/app && pnpm codegen` and commit the regenerated types under `frontend/app/src/shared/api/graphql/generated/`

### The SC-005 regression gate

- [ ] T015 Add the default-list regression test to `backend/tests/component/graphql/queries/test_task.py`: register **both** a namespace-tagged internal run (as `add_tags()` produces) and a wholly-untagged internal run, then assert the no-argument `InfrahubTask` query returns the first and omits the second, and that `count` matches the list. **Assert observed membership — the same runs in, the same runs out. FR-003 explicitly forbids writing this as "no internal runs are returned"**, which would encode the regression the test exists to catch. Omitting the untagged run is also SC-009: the ~4,320 daily scheduled runs never enter the default list unless asked for
- [ ] T016 Add component tests to the same file for: `workflow_type: [INTERNAL]` returning the wholly-untagged internal run; the all-three-types selection returning a strict superset of the default (FR-004); `count` honouring `workflow_type` identically to the list (FR-006); `workflow_type` composing with `state` and `branch` under AND (FR-005)
- [ ] T017 Add a component test to the same file proving FR-008: `InfrahubTask(ids: [<internal run id>], workflow_type: [INTERNAL])` resolves the run with its state, timestamps, parameters and logs. No production change is expected — the test exists because US2's drill-down depends on this behaviour

**Checkpoint**: the backend can select by workflow type, the default list is
proven unchanged, and both slices are unblocked.

---

## Phase 3: User Story 1 — Find out whether a background job is alive (P1)

**Goal**: an operator opens a scheduled-flows view and immediately sees every
scheduled background flow with its schedule, last-run outcome, and whether it is
behind schedule.

**Independent test**: load the view on an instance with the five scheduled
deployments registered; each is listed with schedule and last-run outcome. Stop
the worker, wait past the overdue threshold, confirm the affected flows are
flagged (quickstart Scenarios 3 and 4).

**Requirements covered**: FR-009, FR-009a, FR-010, FR-011, FR-012, FR-012a,
FR-013, FR-014, FR-015, FR-016, FR-016a, FR-019, FR-019a

### Backend models and pure logic

- [ ] T018 [P] [US1] Define `ScheduledFlowHealth`, `LatestRunInfo`, `RecentOutcomeCounts`, `ScheduledFlowSummary` and `ScheduledFlowQueryResult` in `backend/infrahub/task_manager/scheduled_flow/models.py` exactly as specified in data-model.md §2–§3. `ScheduledFlowHealth` subclasses `InfrahubStringEnum`, matching `WorkflowType`
- [ ] T019 [P] [US1] Write `backend/tests/unit/task_manager/scheduled_flow/test_schedule_window.py` covering all five catalogue crons (`* * * * *`, `<n> 2 * * *`, `<n> 3 * * *`): correct `interval_seconds` and a `next_run_at` in the future; plus an uninterpretable cron returning `None` rather than raising
- [ ] T020 [US1] Implement `backend/infrahub/task_manager/scheduled_flow/schedule_window.py` with `next_fire_times()` and `interval_seconds()` on top of `prefect.server.schemas.schedules.CronSchedule.get_dates` (research R5). Keep this the **only** module in the feature importing `prefect.server.schemas.schedules`, and add a module docstring saying so
- [ ] T021 [P] [US1] Write `backend/tests/unit/task_manager/scheduled_flow/test_health.py` covering every verdict and, explicitly, the precedence pairs from research R6: overdue-and-failed ⇒ `OVERDUE`; paused-and-late ⇒ `PAUSED`; no runs inside the retention window ⇒ `NEVER_RUN`; no runs outside it ⇒ `NO_RECENT_RUNS`; a run cancelled before start (`expected_start_time` set, `start_time` None) ⇒ `CANCELLED`, never `FAILED`
- [ ] T022 [US1] Implement the pure verdict function in `backend/infrahub/task_manager/scheduled_flow/health.py` over `(latest_run, interval_seconds, active, deployment_created_at, now, retention_days)`, with the precedence order fixed in research R6 and the overdue window at 3 × interval (spec Assumption 6). Read `retention_days` from configuration, never hard-coded (plan Assumption A10)

### Backend Prefect access

- [ ] T023 [US1] Add a `DeploymentReading` Protocol (`read_deployments`) and a `FlowRunHistoryReading` Protocol (`flow_run_history`) to `backend/infrahub/task_manager/flow_run/prefect_client.py`, and implement both on `PrefectClientAdapter`. `flow_run_history` posts to `/flow_runs/history` via `self.client._client`, the same escape hatch `count_flow_runs` already uses for `/flow_runs/count` (research R3, plan Assumption A8)
- [ ] T024 [US1] Implement `backend/infrahub/task_manager/scheduled_flow/reader.py`: one `read_deployments()` call; then per scheduled deployment, concurrently via `asyncio.gather`, a latest-run read (`FlowRunFilterDeploymentId(any_=[id])`, `limit=1`, **`FlowRunSort.EXPECTED_START_TIME_DESC`**) and a 24-hour history call with `history_interval_seconds` set to the whole window so exactly one bucket returns. `START_TIME_DESC` is wrong here and would hide collision-cancelled runs — see research R4
- [ ] T025 [P] [US1] Write `backend/tests/unit/task_manager/scheduled_flow/test_service.py`: unhealthy-first ordering per data-model.md §4; `catalogue_only` populated when a catalogue cron has no registered deployment; a deployment with no catalogue type tag yielding `workflow_type=None` rather than an error; a *newly added* scheduled workflow appearing in the result with no code change, driven only by the catalogue and the deployment list (SC-010); and — against a fake reader that raises if its run-listing method is called for the breakdown — that the outcome counts never read individual runs (FR-012a as an executable constraint)
- [ ] T026 [US1] Implement `backend/infrahub/task_manager/scheduled_flow/service.py`: assemble summaries, apply the ordering, diff the catalogue crons against registered deployments into `catalogue_only`, cache the assembled result under one key with `KVTTL.ONE_MINUTE` (research R7), and expose a `build_scheduled_flow_service(...)` factory mirroring `build_prefect_task_service`. Let Prefect errors propagate — no partial-success shape (FR-013)

### Backend GraphQL

- [ ] T027 [US1] Add the `ScheduledFlow`, `ScheduledFlowLatestRun`, `ScheduledFlowOutcomes`, `ScheduledFlowOutcomeCount`, `ScheduledFlowNode`, `ScheduledFlows` object types and the `ScheduledFlowHealthEnum` to `backend/infrahub/graphql/types/scheduled_flow.py`, exactly as in contracts/graphql.md §3. Model `counts` as a typed list, never `GenericScalar`
- [ ] T028 [US1] Add the `InfrahubScheduledFlows` resolver in `backend/infrahub/graphql/queries/scheduled_flow.py` (no arguments — FR-012 and FR-009a), with a serializer class mirroring `FlowRunConnectionSerializer`
- [ ] T029 [US1] Register `InfrahubScheduledFlows` on the query root in `backend/infrahub/graphql/schema.py`, next to the existing `InfrahubTask` registration
- [ ] T030 [US1] Add `backend/tests/component/task_manager/test_scheduled_flow.py` against real registered deployments: **every catalogue workflow carrying a cron is present and none is missing (SC-002)** — assert by diffing the result against the catalogue rather than against a hard-coded list of five, so the test does not rot when a schedule is added; correct crons; a never-run daily flow reporting `NEVER_RUN` and not an error or a success; ordering putting unhealthy first
- [ ] T031 [US1] Re-run `uv run invoke schema.generate-graphqlschema` and `cd frontend/app && pnpm codegen`; commit both regenerated outputs

### Frontend

- [ ] T032 [P] [US1] Create `frontend/app/src/entities/scheduled-flows/api/get-scheduled-flows-from-api.ts` with the `InfrahubScheduledFlows` document, following the shape of `entities/tasks/api/get-task-list-from-api.ts`
- [ ] T033 [P] [US1] Create `frontend/app/src/entities/scheduled-flows/domain/model/scheduled-flow.ts` with the health labels, the health display order, and the schedule-sentence helper from research R8 (every-minute / every-N-minutes / hourly / daily, falling back to the raw cron)
- [ ] T034 [P] [US1] Write `frontend/app/src/entities/scheduled-flows/domain/model/scheduled-flow.test.ts` (Vitest) for the schedule sentence across all five catalogue schedules plus an unrecognised cron hitting the fallback, and for the health label mapping
- [ ] T035 [US1] Create `frontend/app/src/entities/scheduled-flows/domain/use-cases/get-scheduled-flows.ts` and `frontend/app/src/entities/scheduled-flows/ui/queries/get-scheduled-flows.query.ts`, following the `getTaskList` / `getTaskListQueryOptions` pattern. Set **no** polling interval (FR-019a)
- [ ] T036 [US1] Add a `scheduledFlows` key to `frontend/app/src/entities/tasks/ui/queries/tasks.query-keys.ts` so the existing `RefreshButton` invalidation reaches the new view
- [ ] T037 [P] [US1] Create `frontend/app/src/entities/scheduled-flows/ui/scheduled-flow-health-badge.tsx` rendering an icon **and** text for each verdict, never colour alone (FR-016a, SC-011). Check `dev/knowledge/frontend/shared-components.md` for an existing badge before building one
- [ ] T038 [US1] Write `frontend/app/src/entities/scheduled-flows/ui/scheduled-flow-health-badge.test.tsx` asserting each verdict is locatable by accessible text, not by class or colour (SC-011), and that `FAILED` and `CANCELLED` each render a distinct outcome word so the row is identifiable without opening it, sorting, or reading a timestamp (SC-004)
- [ ] T039 [US1] Create `frontend/app/src/entities/scheduled-flows/ui/scheduled-flow-items.tsx` rendering the table — name, type, schedule sentence, health badge, last-run outcome, time since last run — reusing the shared `Table` and `DateDisplay` used by `entities/tasks/ui/task-items.tsx`. Preserve backend ordering; do not re-sort client-side (FR-016). Include explicit loading and error states (FR-019) and a `RefreshButton`
- [ ] T040 [US1] Create the page `frontend/app/src/pages/tasks/scheduled.tsx` and register the `/tasks/scheduled` route in `frontend/app/src/app/router.tsx` alongside the existing `/tasks` entries (FR-014, plan Assumption A4)
- [ ] T041 [US1] Add a link from `frontend/app/src/pages/tasks/index.tsx` to the scheduled-flows view, keeping it within two clicks of the Tasks view (SC-001)

**Checkpoint**: US1 is independently shippable. The main Tasks list is untouched.

---

## Phase 4: User Story 2 — Drill into a background flow's runs and logs (P1)

**Goal**: from an unhealthy scheduled flow, reach that flow's recent runs
including failed and cancelled ones, and open any run's logs.

**Independent test**: follow the drill-down for one flow; the run list is scoped
to that workflow and contains its failed/cancelled runs; open one run and its
logs render (quickstart Scenario 7).

**Requirements covered**: FR-017, FR-018

**Depends on**: Phase 2 (the type-aware filter — see the planning note above)
and Phase 3 (the view to drill from).

- [ ] T042 [US2] Add the drill-down link to each row in `frontend/app/src/entities/scheduled-flows/ui/scheduled-flow-items.tsx`, navigating to the Tasks list scoped by `workflow` **and** the flow's `workflow_type`, with **no** state filter so failed and cancelled runs are included (FR-017). Build the URL with the shared `constructPath` helper, per `dev/guidelines/frontend/url-construction.md`
- [ ] T043 [US2] Verify in `frontend/app/src/entities/tasks/ui/task-items.tsx` that a `workflow` filter arriving from the URL is read through `useFilters()` and forwarded to both the list and count hooks; add the wiring if the existing `workflow` facet is not already threaded
- [ ] T044 [US2] Add `tests/e2e/tasks/test_scheduled_flows_view.py` covering US1 and US2 end to end: open `/tasks`, reach the scheduled view in at most two clicks (SC-001), assert every scheduled flow is listed with schedule and last-run outcome, assert an unhealthy row is identifiable from the list alone without opening or sorting (SC-004), assert each health verdict is locatable by accessible text (SC-011), drill into one flow, assert the resulting list is scoped and state-unfiltered, open a run and assert its logs render (SC-008). Do **not** extend `tests/e2e/tasks/test_tasks_view.py` — it is `@pytest.mark.skip`. Run with `--pdb` per `AGENTS.md`
- [ ] T044a [US2] Assert SC-006 in the same e2e file: while loading the scheduled-flows view, capture outbound GraphQL requests via Playwright's network interception and confirm the client issues a **constant** number regardless of how many flows are listed — i.e. no per-flow fan-out. This is the only automated guard on SC-006; the backend's per-flow work is intentionally out of scope for it (FR-012a covers that)

**Checkpoint**: the P1 MVP (US1 + US2) is complete and shippable.

---

## Phase 5: User Story 3 — Filter the Tasks list by workflow type (P2)

**Goal**: an operator widens the main Tasks list to include internal runs via a
Type facet. With the facet unset the list is exactly what it is today.

**Independent test**: with no Type filter, the list and count match the
pre-change behaviour (already gated by T015); apply Type = System and internal
runs appear (quickstart Scenario 2).

**Requirements covered**: FR-020, FR-021, FR-022, FR-023, FR-024, FR-025

**Depends on**: Phase 2 only. Independent of Phases 3–4.

- [ ] T045 [P] [US3] Add `WORKFLOW_TYPE_CORE` / `_USER` / `_INTERNAL`, `WORKFLOW_TYPES` and `WORKFLOW_TYPE_LABELS` (with `INTERNAL → "System"`, spec Assumption 5) to `frontend/app/src/entities/tasks/domain/model/task.ts`. Keep the label mapping in this one place so the API value and the operator-facing label cannot drift
- [ ] T046 [US3] Add `$workflowType: [WorkflowTypeEnum]` to the `GET_TASK_LIST` document in `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts`, passing it as `workflow_type`, and select the new `workflow_type` field on the node (FR-025)
- [ ] T047 [US3] Add the same variable to the `TASK_COUNT` document in `frontend/app/src/entities/tasks/api/get-task-count-from-api.ts` (FR-022)
- [ ] T048 [US3] Add a Type `DropdownField` to `frontend/app/src/entities/tasks/ui/tasks-filter-form.tsx` using `WORKFLOW_TYPES` and `WORKFLOW_TYPE_LABELS`, defaulting to **unset**. It must not pre-select all three — FR-004 and the spec's second edge case make "all types" a different query from "no type"
- [ ] T049 [US3] Write `frontend/app/src/entities/tasks/ui/tasks-filter-form.test.tsx` asserting the Type field renders the three options with "System" as the internal label and that its default value is unset, not all-selected
- [ ] T050 [US3] In `frontend/app/src/entities/tasks/ui/task-items.tsx`, read the type filter from `useFilters()` and pass `workflowType` to both `useGetTaskCount` and `useGetTaskList`; add a "Type" column that renders when the facet is active or any row carries a non-null `workflow_type` (FR-025)
- [ ] T051 [US3] Verify that the Type selection is reflected in the URL, counted by the active-filter indicator, and cleared by the existing clear-filters control in `frontend/app/src/entities/tasks/ui/task-filters.tsx` (FR-023). These operate on the generic filter array, so expect verification rather than new code — fix only if the generic path does not carry it
- [ ] T052 [US3] Verify that branch and related-node cells render empty for internal runs rather than erroring or showing a placeholder that implies a value (FR-024). Expect verification, not new code
- [ ] T053 [US3] Add `tests/e2e/tasks/test_tasks_type_filter.py`: apply Type = System, assert the list and count both narrow and that internal runs appear; reload and assert the filter survives in the URL (FR-023); assert branch and related-node cells are empty rather than erroring (FR-024)

**Checkpoint**: all three stories complete.

---

## Phase 6: Polish & Cross-Cutting

**Requirements covered**: FR-026, FR-027, FR-028, FR-029

- [ ] T054 [P] Update `docs/docs/deploy-manage/run-observe/tasks.mdx` to describe workflow types, the scheduled-flows view, and how to read each health verdict (FR-027). Follow `dev/guidelines/markdown.md`
- [ ] T055 [P] Extend the **Tagging System** section of `dev/knowledge/backend/async-tasks.md`: the workflow-type tag is now load-bearing for the Tasks view, the deployment-level and run-time tagging mechanisms mean different things, and reconciling them is deliberate follow-up work (spec Assumption 18, FR-029)
- [ ] T056 [P] Add the changelog fragment `changelog/+infp-68.added.md` using the `creating-changelog-entries` skill. Write it from the actual diff, not from this plan — `AGENTS.md` requires grepping the code for any identifier or default it names
- [ ] T056a [P] Update `dev/knowledge/frontend/entities-structure.md` (and `dev/knowledge/frontend/architecture.md` if the route table there enumerates pages) to cover the new `entities/scheduled-flows` slice and the `/tasks/scheduled` route. **Constitution requirement**, not optional polish: "Frontend architecture changes MUST update `dev/knowledge/frontend/`" — a new entity slice plus a new route is such a change
- [ ] T056b Confirm FR-013a: internal runs expose the same fields as `CORE`/`USER` runs and this feature introduces no new secret-bearing field. Add an assertion to `backend/tests/component/graphql/queries/test_task.py` that an internal run's `parameters` resolves like any other run's, and verify by inspection of the diff that `HttpRequest.headers` masking in `backend/infrahub/graphql/types/task.py` is unchanged and that no new `GenericScalar` field was added to `TaskNodeInterface`. Research R10 records why this is expected to pass — the task exists to prove it rather than assume it
- [ ] T057 Confirm FR-026: no recovery action becomes newly available on internal runs. `TaskActionGenerator.generate` returns `[]` for any workflow that is not `WEBHOOK_SEND`, so this is a verification task — add an assertion to `backend/tests/unit/graphql/queries/test_task_actions.py` pinning that an internal workflow name yields no actions
- [ ] T058 Confirm FR-029: `git diff` touches no `add_tags()` call site and no `namespace=` argument anywhere under `backend/infrahub/`. The eight self-tagging internal workflows and the single `namespace=False` opt-out in `backend/infrahub/groups/tasks.py` must be byte-identical
- [ ] T059 Run the full local CI gate: `uv run invoke format`, `uv run invoke lint`, `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`, `uv run invoke docs.generate && uv run invoke docs.validate`, `cd frontend/app && pnpm codegen`, `cd frontend && pnpm exec biome ci .`, `cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test`. Or run `/pre-ci`, which also covers the whole-repo `ruff check . --exclude python_sdk` that `invoke lint` misses. Commit every regenerated file — CI fails on stale generated output
- [ ] T060 Walk quickstart.md Scenario 4 manually (stop the task worker, wait past three intervals, confirm the every-minute flows flip to `OVERDUE`, restart and confirm recovery). This is SC-003, the motivating incident, and no automated tier reproduces it
- [ ] T061 Walk quickstart.md Scenario 6 manually (stop the Prefect server, confirm the view shows an explicit error and not an empty list reading as all-healthy) and Scenario 3's timing for SC-007. Plan Assumption A12 records that SC-007 has no automated gate

---

## Dependencies

```text
Phase 1 (setup)
   └─> Phase 2 (foundational selection layer)   ← blocks everything
          ├─> Phase 3 (US1, P1)  ──> Phase 4 (US2, P1)
          └─> Phase 5 (US3, P2)                 ← independent of 3 & 4
                          └─> Phase 6 (polish)
```

- **Phase 2 blocks all stories**, including US2 — see the planning note.
- **US1 → US2**: US2 drills down *from* the US1 view.
- **US3 is independent of US1/US2** and can be built in parallel by a second
  person once Phase 2 lands.
- Within Phase 2, T007/T008 precede T009/T010; T011 precedes T012; T013/T014
  follow T012; T015–T017 follow T012.
- Within Phase 3, T018 precedes T024/T026; T020 precedes T022; T023 precedes
  T024; T027 precedes T028 precedes T029; T031 follows T029; frontend
  T032–T041 follow T031 (they need the generated types).

## Parallel opportunities

- **Phase 1**: T002, T003
- **Phase 2 tests**: T004, T005, T006 together, before their implementations
- **Phase 3**: T018, T019, T021, T025 (all distinct new files) in parallel;
  then T032, T033, T034, T037 in parallel once types are generated
- **Phase 5**: T045 is parallel to anything in Phases 3–4
- **Phase 6**: T054, T055, T056 in parallel

## Implementation strategy

**MVP = Phase 1 + Phase 2 + Phase 3 + Phase 4** (US1 + US2, both P1). That is
the incident path: the operator can see whether every scheduled background flow
is alive and can drill into one that is not. The main Tasks list is untouched,
so the MVP carries no regression risk to the existing view beyond what T015
already gates.

**Increment 2 = Phase 5** (US3, P2), the general-purpose escape hatch.

**Then Phase 6.** T054–T056 (docs and changelog) must ship with whichever
increment lands first, not be deferred to the end — FR-027 and FR-028 apply to
each slice.

## Story summary

| Story | Priority | Tasks | Count | Independently testable |
|---|---|---|---|---|
| US1 — is the job alive? | P1 | T018–T041 | 24 | Yes — quickstart Scenarios 3, 4 |
| US2 — drill into runs/logs | P1 | T042–T044a | 4 | Yes — quickstart Scenario 7, given US1 |
| US3 — Type facet | P2 | T045–T053 | 9 | Yes — quickstart Scenarios 1, 2 |
| Setup / Foundational / Polish | — | T001–T017, T054–T061 (incl. T056a, T056b) | 27 | — |
| **Total** | | | **64** | |

## Requirement coverage

Every FR-### and SC-### in spec.md maps to at least one task. The ones whose
coverage is indirect are pinned here so a reviewer does not have to re-derive
them:

| Requirement | Tasks | Note |
|---|---|---|
| FR-013a | T056b | Verification, not new code — R10 explains why |
| SC-002 | T030 | Asserted by diffing against the catalogue, not a hard-coded five |
| SC-004 | T038, T044 | Distinct outcome word per verdict, asserted from the list |
| SC-006 | T044a | Client-side request count only; backend fan-out is FR-012a |
| SC-007 | T061 | **No automated gate** — plan Assumption A12 |
| SC-009 | T015 | The untagged internal run stays out of the default list |
| SC-010 | T025 | A newly added scheduled workflow appears with no code change |
