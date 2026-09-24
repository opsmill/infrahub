# Phase 1 Data Model: Internal & Scheduled Background Flows in the Tasks View

**Feature**: `internal-scheduled-flows-tasks-view-infp-68`

**Date**: 2026-09-24

Nothing here touches the Infrahub graph schema. No node, attribute, relationship
or migration is added — every entity below is a transport-agnostic Pydantic
model over data that already lives in Prefect. Constitution principles I
(Schema-Driven Integrity) and II (Branch-Safe by Default) are therefore not
engaged: there is no branched or temporal data in this feature.

---

## 1. Extended: `FlowRunQueryCriteria`

`backend/infrahub/task_manager/flow_run/models.py::FlowRunQueryCriteria`

One field added. Everything else is unchanged.

| Field | Type | Default | Notes |
|---|---|---|---|
| `workflow_types` | `list[WorkflowType] \| None` | `None` | **New.** `None` means "not requested" and preserves today's behaviour exactly (FR-003). An empty list is *not* the same as `None` — see the validation rule below. |

**Validation rule**: an empty list must be rejected at the API boundary rather
than silently coerced to `None`. `any_=[]` in Prefect means `has_any(ARRAY[])`,
which matches nothing, so coercing would turn "the client asked for nothing" into
"return everything" — the exact substitution FR-004 forbids. The GraphQL resolver
normalises `[]` to a `ValidationError`.

**Why the plural name**: FR-001 admits one *or more* types, and FR-005 requires
multiple types to match under OR. The field name states the cardinality.

---

## 2. New: `ScheduledFlowSummary`

`backend/infrahub/task_manager/scheduled_flow/models.py`

One entry per scheduled deployment. This is the spec's **Scheduled background
flow** entity (FR-009, FR-009a, FR-015).

| Field | Type | Source | Requirement |
|---|---|---|---|
| `deployment_id` | `UUID` | `DeploymentResponse.id` | drill-down key |
| `name` | `str` | `DeploymentResponse.name` | FR-009 |
| `workflow_type` | `WorkflowType \| None` | decoded from the `infrahub.app/workflow-type/{t}` tag on the deployment | FR-009, FR-009a |
| `cron` | `str` | `CronSchedule.cron` | FR-009 |
| `timezone` | `str \| None` | `CronSchedule.timezone` | FR-015 |
| `interval_seconds` | `int \| None` | derived, R5 | FR-015, drives the overdue window |
| `next_run_at` | `datetime \| None` | derived, R5 | FR-015 |
| `active` | `bool` | `DeploymentSchedule.active and not DeploymentResponse.paused` | FR-009 |
| `concurrency_limit` | `int \| None` | `DeploymentResponse.concurrency_limit` | spec Key Entities |
| `collision_strategy` | `str \| None` | `DeploymentResponse.concurrency_options` | spec Key Entities; explains a `CANCELLED` verdict |
| `latest_run` | `LatestRunInfo \| None` | R4 | FR-009, FR-010 |
| `recent_outcomes` | `RecentOutcomeCounts` | R3 | FR-009, FR-012a |
| `health` | `ScheduledFlowHealth` | derived, R6 | FR-011 |
| `deployment_created_at` | `datetime \| None` | `DeploymentResponse.created` | separates never-run from purged (FR-010) |

`workflow_type` is nullable because a deployment registered outside the
catalogue may carry no type tag — the spec's "deployment in Prefect that is not
in the catalogue" edge case. Rendering it as unknown is required; erroring is not.

### `LatestRunInfo`

**The newest run Prefect expected to have started by `now` that got past the
queue** — R4's bounded read, not "the newest row for this deployment". Prefect
pre-creates future `SCHEDULED` runs continuously, so the unbounded reading
names a run that has not happened. `SCHEDULED` and `PENDING` are excluded by
the read, so this field never carries either.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | drill-down target for FR-018 |
| `state_type` | `StateType` | never `SCHEDULED` or `PENDING`, by construction |
| `state_name` | `str \| None` | distinguishes a collision cancellation from a crash (Assumption 8) |
| `expected_start_time` | `datetime \| None` | the sort key, and the input to the overdue comparison (R4, R6) |
| `start_time` | `datetime \| None` | `None` for a run that never started |
| `end_time` | `datetime \| None` | |

Both `expected_start_time` and `start_time` are carried deliberately. A run
where the first is set and the second is `None` *is* the collision-cancelled
case the view must not present as a crash.

`None` for the whole field means "no executed run", which is what makes
`OVERDUE`, `NEVER_RUN` and `NO_RECENT_RUNS` reachable at all (R6).

### `RecentOutcomeCounts`

Aggregate only — never a list of runs (FR-012a).

| Field | Type |
|---|---|
| `window_hours` | `int` (24, per Assumption 7) |
| `counts` | `dict[StateType, int]` |
| `total` | `int` |

**On `counts` being a dict here and a list in GraphQL**: the Pydantic model
holds a `dict[StateType, int]` because that is the natural shape for the
`/flow_runs/history` response and for the ordering and test code that consume
it. The GraphQL type projects it as a typed
`[ScheduledFlowOutcomeCount!]!` list of `{ state_type, count }` pairs, because
a map of arbitrary keys crossing the API boundary would have to be
`GenericScalar`, which Constitution III rejects. Both statements are true at
once; the projection happens in the serializer (`contracts/graphql.md` §3,
T027).

`counts` may legitimately contain `SCHEDULED` — runs that were due inside the
window and that nothing picked up. That is a signal, not noise (R3), so the UI
renders whatever states come back rather than assuming terminal ones.

### `ScheduledFlowHealth` (enum)

`InfrahubStringEnum`, matching the codebase's enum convention
(`WorkflowType`, `WorkflowPriority`).

`healthy` · `failed` · `cancelled` · `overdue` · `never_run` ·
`no_recent_runs` · `paused`

Precedence and derivation are specified in research R6. FR-011's required
minimum (healthy / failed / cancelled / overdue) is covered; the extra three
exist because FR-010 forbids collapsing "no history" into either success or
failure, and because a paused schedule must not read as late.

---

## 3. New: `ScheduledFlowQueryResult`

| Field | Type | Notes |
|---|---|---|
| `flows` | `list[ScheduledFlowSummary]` | ordered unhealthy-first (FR-016), then by name |
| `catalogue_only` | `list[str]` | catalogue workflows with a cron but no registered deployment |

`catalogue_only` exists solely for the spec's partial-registration edge case:
"render what it can and say plainly which side is missing". A deployment with no
catalogue entry needs no separate list — it appears in `flows` with
`workflow_type = None`.

Prefect being unreachable is **not** modelled as a field. FR-013 requires it to
surface as an explicit error, so the exception propagates to GraphQL and becomes
an `errors[]` entry. A partial-success shape would be exactly the "empty list
that reads as all healthy" the spec forbids.

---

## 4. Ordering contract (FR-016)

Sort key, applied in the backend so the client cannot disagree with the badge:

1. health rank — `overdue` (0), `failed` (1), `cancelled` (2),
   `no_recent_runs` (3), `never_run` (4), `paused` (5), `healthy` (6)
2. name ascending, as a stable tiebreak

Ranking `overdue` first matches R6's precedence: a stalled every-minute flow is
the motivating incident.

**This is not R6's precedence order, and the difference is deliberate.** R6
orders *which verdict a flow gets* when several apply, and puts `PAUSED` first
so a switched-off schedule is never described as a fault. This table orders
*where a flow appears in the list* once it has a verdict, and puts `paused`
near the bottom for the same reason — it needs no attention. One question is
"what is true of this flow", the other is "how urgently should the operator
look at it".

---

## 5. Frontend types

Generated, not hand-written (Constitution I and III):
`frontend/app/src/shared/api/graphql/generated/` via `pnpm codegen`.

One hand-written domain constant set is added beside the existing task model in
`frontend/app/src/entities/tasks/domain/model/task.ts`:

| Constant | Value |
|---|---|
| `WORKFLOW_TYPE_CORE` / `_USER` / `_INTERNAL` | `"CORE"` / `"USER"` / `"INTERNAL"` (GraphQL enum casing) |
| `WORKFLOW_TYPES` | the three, for the filter facet |
| `WORKFLOW_TYPE_LABELS` | `INTERNAL → "System"` (Assumption 5), others title-case |

The `INTERNAL → System` mapping lives in exactly one place so the API enum value
and the operator-facing label cannot drift.

---

## 6. State transitions

None. Every entity here is a read-only projection of Prefect state. The feature
adds no mutation, no write path, and no lifecycle.
