# Implementation Plan: Internal & Scheduled Background Flows in the Tasks View

**Branch**: `OPS-21-show-internal-and-scheduled-background-flows-in-the-tasks-view-infp-68`
| **Date**: 2026-09-24
| **Spec**: [spec.md](./spec.md)
| **Ticket**: infp-68

**Input**: Feature specification from
`specs/internal-scheduled-flows-tasks-view-infp-68/spec.md` (approved)

## Summary

Make Infrahub's internal and scheduled background flows observable in the
product without disturbing the Tasks list operators already use.

Two independently-shippable slices over one shared prerequisite:

- **Shared prerequisite** — teach the flow-run selection layer about workflow
  type, and decode the type tag onto every run.
- **Slice A (P1, the incident path)** — a new `task_manager/scheduled_flow/`
  package that reads Prefect *deployments*, derives a per-flow health verdict,
  and exposes it as one `InfrahubScheduledFlows` GraphQL query behind a new
  scheduled-flows page.
- **Slice B (P2, the escape hatch)** — a `workflow_type` argument on
  `InfrahubTask` and a Type facet in the Tasks filter panel.

The technical core is one change in
`flow_run/filters.py::FlowRunFilterBuilder.build_flow_run_filter`: the
unconditional `all_=[TAG_NAMESPACE]` becomes `all_` for AND-ed tags plus `any_`
for OR-ed workflow-type tags, with `TAG_NAMESPACE` added to `all_` **only when
no type was requested**. Research R1 verified against the installed Prefect that
`all_` and `any_` on one `FlowRunFilterTags` combine with AND, which is what
makes FR-002 and FR-005 expressible at all.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 / React 19.2
(frontend)

**Primary Dependencies**: FastAPI 0.131, graphene, Prefect 3.8.6 (pinned),
Pydantic 2.12, TanStack Query, Vite 8, Tailwind 4.2. **No new dependency** —
research R5 and R8 both chose in-tree options specifically to avoid an
Ask-First dependency addition with no human available.

**Storage**: None added. Prefect's own database is the system of record; Neo4j
is untouched. The Infrahub cache (Redis) holds one 60s-TTL summary key.

**Testing**: pytest 9 (`backend/tests/unit`, `.../component`), Vitest 4.1
(browser mode), pytest-playwright (`tests/e2e/`)

**Target Platform**: Linux server + browser

**Project Type**: Web application (backend + frontend)

**Performance Goals**: scheduled-flows view readable in <2s p95 with 24h of
every-minute history (SC-007); client issues a constant number of requests
regardless of flow count (SC-006)

**Constraints**: no auto-polling, ≤60s staleness (FR-019a); the summary must be
built from aggregate counts, never per-run reads (FR-012a); the default Tasks
list must be byte-for-byte unchanged (FR-003, SC-005)

**Scale/Scope**: 5 scheduled deployments and ~4,320 scheduled runs/day today;
19 internal workflows, 11 of them wholly invisible

## Constitution Check

Gates derived from `.specify/memory/constitution.md` v1.0.0. Evaluated before
Phase 0 and re-evaluated after Phase 1 design — same verdict both times.

| Principle | Verdict | Basis |
|---|---|---|
| I. Schema-Driven Integrity | **N/A** | No node, attribute, relationship or migration. Every entity is a read-only projection of Prefect state. Generated files (`schema/schema.graphql`, frontend GraphQL types) are regenerated, never hand-edited — enforced by the `validate-generated-documentation` CI job. |
| II. Branch-Safe by Default | **N/A** | No branched or temporal data. The `branch` value on a run is a decoded tag, not a graph query; the feature adds no database access. |
| III. Type Safety & Explicit Contracts | **PASS** | Full type hints; `str \| None` style; Pydantic models at the API boundary; GraphQL contract defined up front in `contracts/graphql.md`; outcome counts modelled as a typed list rather than `GenericScalar` so no untyped dict crosses the boundary; frontend consumes generated types, no `any`. |
| IV. Test Discipline | **PASS** | Unit tests for every pure decision (filter composition, health precedence, cron interval, schedule sentence); component tests against a real Prefect for the GraphQL queries; Vitest for frontend logic and components; e2e for both user-facing surfaces. See Testing Strategy. |
| V. Query Performance & Efficiency | **PASS** | No Cypher added. The N+1 risk is against Prefect, and is bounded by design: 2 calls per *scheduled flow* (R3, R4), issued concurrently, never scaling with run count. Aggregate counting is mandated by FR-012a and implemented via `/flow_runs/history`. |
| VI. Security & Input Boundaries | **PASS** | Read-only feature; no mutation, so the "authentication required for mutating operations" gate is not engaged (the Tasks view is already authenticated-only). Input is a bounded enum list, validated by graphene plus an explicit empty-list rejection. No new sensitive field — re-verified in R10 that `webhook-send` is already `CORE` with masked headers, and internal runs resolve to the plain `TaskNode`. |
| VII. Simplicity & Maintainability | **PASS with one justified deviation** | Follows the established Protocol + adapter + service + `build_*` factory pattern (R9) rather than inventing one. No new dependency. The deviation is the new sibling package — see Complexity Tracking. |

### Ask-First items (`AGENTS.md`)

`AGENTS.md` lists **GraphQL schema modifications** and **new dependencies**
under Ask First. No human answers during this pipeline, so per the issue
instructions these are stated explicitly rather than blocking:

- **GraphQL change**: fully specified in
  [`contracts/graphql.md`](./contracts/graphql.md). Purely additive. Recorded as
  Assumptions A1–A3.
- **New dependencies**: **none**. R5 and R8 record the two places a dependency
  was the obvious route and the in-tree alternative chosen instead.
- **Database/migration, auth, CI changes**: none.

## Project Structure

### Documentation (this feature)

```text
specs/internal-scheduled-flows-tasks-view-infp-68/
├── spec.md               # approved
├── plan.md               # this file
├── research.md           # Phase 0 — R1…R10
├── data-model.md         # Phase 1 — entities
├── quickstart.md         # Phase 1 — validation scenarios
├── contracts/
│   └── graphql.md        # Phase 1 — the complete API delta
├── checklists/
├── critiques/
└── tasks.md              # Phase 2 — /speckit-tasks
```

### Source code

```text
backend/infrahub/
├── task_manager/
│   ├── flow_run/                       # existing — runs
│   │   ├── filters.py                  # CHANGED: conditional namespace tag, any_ type tags
│   │   ├── models.py                   # CHANGED: FlowRunQueryCriteria.workflow_types,
│   │   │                               #          EnrichedFlowRun.workflow_type
│   │   ├── tags.py                     # CHANGED: WorkflowTagDecoder.workflow_type()
│   │   ├── service.py                  # CHANGED: carry the decoded type onto results
│   │   └── prefect_client.py           # CHANGED: DeploymentReading protocol +
│   │                                   #          read_deployments / flow_run_history on the adapter
│   └── scheduled_flow/                 # NEW — deployments
│       ├── __init__.py
│       ├── models.py                   # ScheduledFlowSummary, LatestRunInfo,
│       │                               # RecentOutcomeCounts, ScheduledFlowHealth, result
│       ├── schedule_window.py          # cron -> interval / next fire (R5); the ONLY
│       │                               # prefect.server.schemas import in the feature
│       ├── health.py                   # pure verdict function (R6)
│       ├── reader.py                   # deployments, latest run, outcome history
│       └── service.py                  # assembly, ordering, 60s cache, build_* factory
└── graphql/
    ├── queries/
    │   ├── task.py                     # CHANGED: workflow_type arg + serializer field
    │   └── scheduled_flow.py           # NEW: InfrahubScheduledFlows
    ├── types/
    │   ├── task.py                     # CHANGED: WorkflowTypeEnum, workflow_type on the interface
    │   └── scheduled_flow.py           # NEW: ScheduledFlow* object types
    └── schema.py                       # CHANGED: register InfrahubScheduledFlows

frontend/app/src/
├── entities/
│   ├── tasks/
│   │   ├── api/get-task-list-from-api.ts       # CHANGED: $workflowType
│   │   ├── api/get-task-count-from-api.ts      # CHANGED: $workflowType
│   │   ├── domain/model/task.ts                # CHANGED: WORKFLOW_TYPE* + labels
│   │   ├── ui/tasks-filter-form.tsx            # CHANGED: Type facet
│   │   ├── ui/task-items.tsx                   # CHANGED: read the filter, Workflow type column
│   │   └── ui/queries/tasks.query-keys.ts      # CHANGED: scheduled-flows key
│   └── scheduled-flows/                        # NEW entity slice
│       ├── api/get-scheduled-flows-from-api.ts
│       ├── domain/model/scheduled-flow.ts      # health labels, ordering, schedule sentence (R8)
│       ├── domain/use-cases/get-scheduled-flows.ts
│       ├── ui/queries/get-scheduled-flows.query.ts
│       ├── ui/scheduled-flow-health-badge.tsx  # icon + text, never colour alone
│       └── ui/scheduled-flow-items.tsx
├── pages/tasks/
│   ├── index.tsx                               # CHANGED: link to the scheduled view
│   └── scheduled.tsx                           # NEW page
└── app/router.tsx                              # CHANGED: /tasks/scheduled route

backend/tests/
├── unit/task_manager/flow_run/test_filters.py  # CHANGED
├── unit/task_manager/flow_run/test_tags.py     # CHANGED
├── unit/task_manager/scheduled_flow/           # NEW: test_health, test_schedule_window, test_service
├── unit/graphql/queries/test_task.py           # CHANGED
└── component/graphql/queries/test_task.py      # CHANGED: the SC-005 regression test
                                                # + test_scheduled_flow.py (NEW)

tests/e2e/tasks/                                # NEW: test_scheduled_flows_view.py,
                                                #      test_tasks_type_filter.py
docs/docs/deploy-manage/run-observe/tasks.mdx   # CHANGED (FR-027)
changelog/+infp-68.added.md                     # NEW (FR-028)
```

**Structure Decision**: Web application layout, matching the repo. Backend work
stays inside `task_manager/` and `graphql/`; frontend work follows the
Feature-Sliced `entities/*/{api,domain,ui}` convention already used by
`entities/tasks`.

## Implementation approach

### Phase A — shared prerequisite (FR-001, FR-005, FR-008, FR-025)

1. **`WorkflowTagDecoder.workflow_type(flow)`** — decode
   `infrahub.app/workflow-type/{t}` to `WorkflowType | None`, mirroring the
   existing `branch_name()`. Pure string work on tags already fetched, so it
   costs nothing on the default list.
2. **`FlowRunQueryCriteria.workflow_types`** — see `data-model.md` §1.
3. **`build_flow_run_filter`** — the core change:

   ```python
   all_tags: list[str] = []
   if not criteria.workflow_types:
       all_tags.append(TAG_NAMESPACE)          # unchanged default (FR-003)
   ...branch / related-node / caller tags append to all_tags as today...

   tags = FlowRunFilterTags(all_=all_tags or None)
   if criteria.workflow_types:
       tags.any_ = [WorkflowTag.WORKFLOWTYPE.render(identifier=t.value)
                    for t in criteria.workflow_types]
   ```

   `all_=None` when the list is empty matters: `has_all(ARRAY[])` is trivially
   true but emitting the clause at all is noise in the cache key, and
   `FlowRunCounter` hashes the serialised filter body.
4. **Carry the type through** `EnrichedFlowRun.workflow_type` →
   `FlowRunConnectionSerializer._serialize_node` → the new interface field.

FR-008 (single-run retrieval resolves internal runs) needs **no code change** —
`InfrahubTask(ids: [...])` already returns any run whose tags satisfy the
filter, and once a type is requested the namespace tag is no longer demanded.
It does need a test proving it, because the requirement is load-bearing for
Slice A's drill-down.

### Phase B — Slice A backend, the scheduled-flow summary

New `task_manager/scheduled_flow/` package (rationale in Complexity Tracking).

**`schedule_window.py`** — the single containment point for
`prefect.server.schemas.schedules.CronSchedule` (R5). Two pure-ish functions:
`next_fire_times(cron, timezone, n)` and `interval_seconds(cron, timezone)`,
derived by subtracting consecutive fire times. Returns `None` rather than
raising on an uninterpretable cron, so one bad schedule cannot take the view
down.

**`reader.py`** — three Prefect reads, all behind Protocols:

| Read | Call | Cost |
|---|---|---|
| deployments | `read_deployments()` | 1 |
| latest run per flow | `read_flow_runs(deployment_id=any_[id], limit=1, sort=EXPECTED_START_TIME_DESC)` | N |
| 24h outcome breakdown per flow | `POST /flow_runs/history` with one bucket | N |

`EXPECTED_START_TIME_DESC`, not `START_TIME_DESC` — R4 explains why this is a
correctness requirement rather than a preference: a collision-cancelled run has
no `start_time`, so the wrong sort key reproduces the motivating incident as a
bug. The per-flow reads are issued with `asyncio.gather`.

**`health.py`** — pure function over
`(latest_run, interval_seconds, active, deployment_created_at, now,
retention_days)`. Precedence fixed in R6; overdue = no expected start within
3 × interval (Assumption 6); `paused` suppresses `overdue`.

**`service.py`** — assemble, order unhealthy-first (`data-model.md` §4), compute
`catalogue_only` by diffing catalogue crons against registered deployments, and
cache the assembled result for 60s under one key using `KVTTL.ONE_MINUTE`
(R7). A `build_scheduled_flow_service(...)` factory mirrors
`build_prefect_task_service`.

Prefect errors propagate; there is deliberately no partial-success path
(FR-013).

### Phase C — Slice B backend, the `workflow_type` argument

Add `workflow_type=List(WorkflowTypeEnum)` to the `Task` field, thread it
through `Tasks.resolve` → `Tasks.query` → `FlowRunQueryCriteria`, and reject an
empty list with `ValidationError`. `TaskBranchStatus` passes nothing and so is
unaffected.

### Phase D — Slice A frontend, the scheduled-flows view

New `entities/scheduled-flows` slice plus a `/tasks/scheduled` route
(FR-014 — reachable and URL-addressable; the spec left tab-vs-route to planning,
and a sibling route is chosen because it is shareable during an incident and
costs nothing).

- `scheduled-flow-health-badge.tsx` renders an icon **and** text (FR-016a,
  SC-011). Reuse the design-system badge rather than a bespoke component —
  check `dev/knowledge/frontend/shared-components.md` first.
- The schedule sentence uses the R8 helper: pure, unit-tested, falls back to the
  raw cron.
- Backend ordering is preserved as-is; the client does not re-sort (FR-016).
- Explicit loading and error states (FR-019); `RefreshButton` for manual
  refresh, no polling interval on the query (FR-019a).
- Drill-down (FR-017) links to `/tasks?workflow=<name>` with **no** state
  filter, so failed and cancelled runs are included.

### Phase E — Slice B frontend, the Type facet

- `WORKFLOW_TYPE_LABELS` maps `INTERNAL → "System"` in one place
  (Assumption 5).
- `tasks-filter-form.tsx` gains a Type `DropdownField`, defaulting to unset.
  **It must not pre-select all three** — FR-004 and the spec's second edge case.
- `task-items.tsx` reads the filter through the existing `useFilters()` and
  passes `workflowType` to both the list and count hooks (FR-022). The URL, the
  active-filter count and clear-filters all work unchanged because they operate
  on the generic filter array (FR-023).
- A "Type" column renders when the facet is active or any internal run is in the
  page (FR-025). Branch and related-node cells already render empty for a null
  value, so FR-024 needs verification, not new code.

### Phase F — docs, changelog, generated files

- `docs/docs/deploy-manage/run-observe/tasks.mdx`: workflow types, the
  scheduled-flows view, how to read each health verdict (FR-027).
- `dev/knowledge/backend/async-tasks.md`: extend the **Tagging System** section
  — the workflow-type tag is now load-bearing for the Tasks view, and the two
  tagging mechanisms mean different things (spec Assumption 18 / FR-029).
- `changelog/+infp-68.added.md` via the `creating-changelog-entries` skill
  (FR-028). Write it from the diff, not from this plan.
- Regenerate and commit: `schema.generate-graphqlschema`, `pnpm codegen`,
  `docs.generate`. CI fails on stale generated files.

## Testing Strategy

Per Constitution IV, the level is chosen per behaviour rather than defaulting to
one tier.

**Unit** (`backend/tests/unit/`, no Prefect, seconds):

- `test_filters.py` — the FR-002/FR-004/FR-005 matrix. Critically: no type ⇒
  `all_ == [TAG_NAMESPACE]` and `any_ is None`; types requested ⇒ `TAG_NAMESPACE`
  absent from `all_` and `any_` carries the type tags; branch + type together ⇒
  branch in `all_`, types in `any_`.
- `test_tags.py` — type decoding, including a run with no type tag.
- `scheduled_flow/test_health.py` — every verdict and, explicitly, the
  precedence pairs: overdue-and-failed ⇒ `OVERDUE`; paused-and-late ⇒ `PAUSED`;
  no-runs-inside-retention ⇒ `NEVER_RUN` vs. outside ⇒ `NO_RECENT_RUNS`.
- `scheduled_flow/test_schedule_window.py` — the five catalogue crons, plus an
  uninterpretable cron returning `None` rather than raising.
- `scheduled_flow/test_service.py` — ordering, `catalogue_only` diffing, and
  that the outcome breakdown never reads individual runs (assert against a fake
  reader that fails if the run-list method is called — FR-012a as an executable
  constraint rather than a comment).

**Component** (`backend/tests/component/`, real Prefect via testcontainers):

- The **SC-005 regression test** in
  `component/graphql/queries/test_task.py`. Register both a namespace-tagged
  internal run and a wholly-untagged internal run, then assert the no-argument
  query returns the first and not the second — membership by observed result.
  FR-003 forbids writing this as "no internal runs are returned".
- `workflow_type: [INTERNAL]` returns the untagged internal run; the all-three
  selection strictly exceeds the default (FR-004); count matches list (FR-006);
  empty list errors.
- Single-run retrieval of an internal run by id (FR-008).
- `component/task_manager/test_scheduled_flow.py` — the summary against real
  registered deployments: all five present, schedules correct, never-run
  distinct from failed.

**Frontend unit** (Vitest): the schedule sentence, the health label/order
mapping, the filter-form Type field defaulting to unset and *not* to all-three,
and the health badge exposing accessible text.

**E2E** (`tests/e2e/tasks/`): the two user journeys in `quickstart.md`
Scenario 7. Note the existing `test_tasks_view.py` is `@pytest.mark.skip`
(ported from a `describe.fixme`), so these are new files and must not depend on
it being re-enabled. Run with `--pdb` per `AGENTS.md`.

**Not tested here**: SC-007's 2s p95 has no automated gate. Measuring it needs a
24h-history instance that no tier provisions. It is verified manually per
`quickstart.md` Scenario 3, and the design constraint that actually protects it
— constant per-flow work, aggregate counts — *is* asserted by the
`test_service.py` fake-reader test above. Flagged rather than silently dropped.

## Delivery sequencing

Phase A → then A-slice (B, D) and B-slice (C, E) in either order → F.

Slice A alone is shippable and is the P1 incident path: it leaves the main Tasks
list untouched and the scheduled view plus drill-down working. Slice B alone is
also shippable. If the reviewer rejects the GraphQL addition for one slice, the
other still lands.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| New `task_manager/scheduled_flow/` package (6 modules) rather than extending `flow_run/` | The two answer different questions against different Prefect resources: `flow_run/` selects runs by tag; this reads *deployments* and their schedules. Sharing a package would put deployment reads behind a module named for runs, and `flow_run/service.py` already composes five collaborators. | Adding deployment reads to `flow_run/` would grow an already-dense service and blur the one boundary that makes the existing code readable. The two share exactly one thing — the Prefect adapter — which stays in `flow_run/prefect_client.py` and is imported, not duplicated. This is the codebase's own pattern (`task_manager/event/` is a sibling for the same reason). |

Principle VII's "helpers must serve two callers" is respected: no shared
abstraction is extracted between the two packages beyond the existing adapter.

## Assumptions

Every item is an autonomous decision — no human is available during this
pipeline. Spec Assumptions 1–19 are inherited unchanged; these are the
additional ones planning forced.

**A1. The GraphQL schema change proceeds without sign-off.** `AGENTS.md` marks
it Ask First. The full delta is in `contracts/graphql.md`; it is purely
additive, so no existing query breaks. Recorded rather than blocked, per the
issue instructions.

**A2. `InfrahubScheduledFlows` is a new top-level query, not an argument on
`InfrahubTask`.** They return different entities (deployments vs. runs) with
disjoint field sets; overloading one query would force a union type or a
nullable-everything node.

**A3. `workflow_type` is added to `TaskNodeInterface` as a typed enum.** FR-025
needs the type per row. It is already in `tags`, but making the client parse
`infrahub.app/workflow-type/internal` out of a string array is the untyped
contract Constitution III rejects. It is a pure tag decode — no extra Prefect
call.

**A4. The scheduled-flows view is a sibling route `/tasks/scheduled`, not a
tab.** Spec Assumption 10 explicitly left this to planning. A route is
URL-addressable for free (FR-014) and shareable in an incident channel.

**A5. `EXPECTED_START_TIME_DESC` for "latest run".** A correctness decision, not
a preference — see R4. The existing `FlowRunReader` keeps `START_TIME_DESC`;
only the new reader differs.

**A6. Human-readable schedules are rendered client-side from structured facts,
with a raw-cron fallback.** Avoids an Ask-First dependency (`cronstrue`) and
covers all five catalogue schedules. See R8.

**A7. Cron interpretation uses `prefect.server.schemas.schedules.CronSchedule`.**
Avoids an Ask-First dependency (`croniter`). Established practice —
`backend/infrahub/prefect_server/` already imports `prefect.server.*` in
production code — and confined to one module so a Prefect upgrade has one place
to fix.

**A8. The 24h breakdown uses `POST /flow_runs/history`, reached through the
adapter's raw HTTP escape hatch.** The Python client exposes no history method.
`PrefectClientAdapter.count_flow_runs` already posts raw to
`/flow_runs/count`, so the pattern exists. One call per flow instead of four.
See R3.

**A9. An empty `workflow_type: []` is an error, not "unset".** Coercing it would
turn "the client asked for nothing" into "return everything" — the substitution
FR-004 forbids.

**A10. The retention window used to separate "never run" from "history purged"
is read from configuration, not hard-coded.** The CLI default is 30 days but
operators flush on their own cadence; a hard-coded constant would make the
verdict wrong for anyone who changed it. Where the comparison is inconclusive
the verdict is `NO_RECENT_RUNS`, per the spec's instruction not to guess.

**A11. Health verdict precedence puts `OVERDUE` above `FAILED`.** A flow can be
both. A stalled every-minute flow is the motivating incident; a single failed
run on a flow that is still ticking is less urgent.

**A12. No performance regression gate for SC-007.** No test tier provisions a
24h-history instance. Manual verification plus an executable assertion on the
design constraint that protects it. Called out rather than quietly dropped.

## Dependencies and risks

| Risk | Mitigation |
|---|---|
| A Prefect upgrade changes `prefect.server.schemas.schedules` or the `/flow_runs/history` payload | Both are confined to one module each (`schedule_window.py`, the adapter) with unit/component tests that fail loudly. Prefect is pinned at `==3.8.6`. |
| The SC-005 regression test gets written as "no internal runs returned" | FR-003 forbids it in the spec; the Testing Strategy and `tasks.md` both restate it; the component test registers a namespace-tagged internal run precisely so the wrong assertion fails. |
| `catalogue_only` drifts as workflows are added | It is computed by diffing the catalogue at request time, so a new scheduled workflow appears with no further work (SC-010). |
| Prefect round-trips grow if scheduled workflows proliferate | 2N concurrent calls, N = scheduled flows. At a few dozen this is fine; past that the summary would need batching. Not engineered for now (YAGNI, Principle VII). |
