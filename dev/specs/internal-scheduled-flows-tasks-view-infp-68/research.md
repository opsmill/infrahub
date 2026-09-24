# Phase 0 Research: Internal & Scheduled Background Flows in the Tasks View

**Feature**: `internal-scheduled-flows-tasks-view-infp-68`

**Date**: 2026-09-24

Every question below was opened by the spec and closed against the code and
against the installed Prefect (`prefect==3.8.6`, pinned in `pyproject.toml`) —
not from memory. Probe commands are recorded so a reviewer can re-run them.

No `NEEDS CLARIFICATION` items remain.

---

## R1 — Can the tag filter express "branch AND node AND (any of N workflow types)"?

**This is the load-bearing question of the whole feature.** FR-002 makes the
namespace requirement conditional and FR-005 requires the type criterion to
compose with every other criterion under AND, while multiple requested types
must match under OR. The spec (Assumption 19) established that
`FlowRunFilterTags` has no negation predicate; it did not establish whether
`all_` and `any_` can be used *together*.

**Decision**: Use `all_` and `any_` on the same `FlowRunFilterTags`.

- `all_` carries the AND-ed tags: branch, related node, caller-supplied tags,
  and `TAG_NAMESPACE` **only when no workflow type was requested**.
- `any_` carries the OR-ed workflow-type tags, set only when types were
  requested.

**Evidence**: `prefect.server.schemas.filters.FlowRunFilterTags` derives from
`PrefectOperatorFilterBaseModel`, whose `operator` defaults to `and_`, and its
`_get_filter_list()` emits one SQL condition per populated field:

```python
if self.all_:  filters.append(db.FlowRun.tags.has_all(as_array(self.all_)))
if self.any_ is not None: filters.append(db.FlowRun.tags.has_any(as_array(self.any_)))
```

So a filter carrying both yields `has_all(all_) AND has_any(any_)` — precisely
the required semantics. Verified by reading the installed source:

```bash
uv run python -c "import inspect; from prefect.server.schemas.filters import FlowRunFilterTags; print(inspect.getsource(FlowRunFilterTags))"
```

**Alternatives rejected**:

- *Client-side post-filtering of runs by type tag* — breaks pagination and the
  count (FR-006), and would read runs only to discard them.
- *A separate `FlowRunFilter` per type, unioned in Python* — multiplies Prefect
  round-trips and makes `limit`/`offset` incoherent.
- *Negation (`has the namespace tag AND is not internal`)* — inexpressible;
  already settled in spec Assumption 19.

**Consequence for FR-004**: because the default and the explicit-all-types
selections are built from *different* fields (`all_` vs `any_`), the two are
naturally distinct in the implementation. Nothing needs to special-case them.

---

## R2 — How are deployments and their schedules read?

The spec's Dependencies section states no deployment read path exists today.
Confirmed: `backend/infrahub/task_manager/flow_run/prefect_client.py` exposes
flow runs, logs, artifacts, flows, counts and state writes only.

**Decision**: Add a `DeploymentReading` protocol to the existing
`prefect_client` module and implement it on `PrefectClientAdapter` with
`PrefectClient.read_deployments()`.

**Evidence** (`uv run python` probe of the installed client):

```text
read_deployments(*, flow_filter, flow_run_filter, task_run_filter,
                 deployment_filter, work_pool_filter, work_queue_filter,
                 limit, sort, offset) -> list[DeploymentResponse]
```

`DeploymentResponse` carries everything FR-009 asks for except run history:
`id`, `name`, `flow_id`, `tags`, `schedules`, `paused`, `status`,
`concurrency_limit`, `concurrency_options`, `work_queue_name`, `created`.

`DeploymentSchedule` carries `schedule`, `active`, `slug`, `max_scheduled_runs`.
For Infrahub's catalogue the inner `schedule` is always a `CronSchedule`
(`WorkflowDefinition.to_deployment()` only ever builds `CronSchedule`), which
carries `cron`, `timezone`, `day_or`.

**Note on `created`**: `DeploymentResponse.created` is what makes the spec's
"never run vs. history purged" edge case separable without new bookkeeping — a
deployment created inside the assumed retention window with no *executed* runs
has genuinely never run. This is the only field that supports that distinction,
so it must be read. It also guards the `OVERDUE` rule, keeping a
just-registered flow out of "late" (R6).

---

## R3 — How is the 24-hour outcome breakdown computed without reading runs?

FR-012a forbids materialising run records and requires work to scale with flow
count, not run count (~4,320 runs/day).

**Decision**: One `POST /flow_runs/history` call per scheduled deployment, with
`history_interval_seconds` set to the full window so exactly one bucket comes
back. The response's `states[]` gives `state_type`, `state_name` and
`count_runs` — the entire breakdown, aggregated server-side, in one call.

**Evidence**: the route exists in the installed Prefect server
(`prefect.server.api.flow_runs.flow_run_history`) and accepts `history_start`,
`history_end`, `history_interval_seconds`, plus `flows`, `flow_runs`,
`deployments` filters. Response schema `HistoryResponse` →
`states: list[HistoryResponseState]` with `count_runs`.

The Python client has **no** `read_flow_run_history` method, so this goes
through `self.client._client.post(...)` on the adapter — the same escape hatch
`PrefectClientAdapter.count_flow_runs` already uses for `/flow_runs/count`. The
precedent is established, so this is not a new pattern.

**Important semantic**: `run_history` buckets on `expected_start_time`, not
`start_time`:

```python
run_model.expected_start_time >= history_start,
run_model.expected_start_time < history_query_end,
```

This is *better* for this feature, not a caveat to work around. A run cancelled
by a `CANCEL_NEW` collision never starts, so it has no `start_time` — bucketing
on `start_time` would make exactly the failure mode this feature exists to
surface invisible in the breakdown. Bucketing on `expected_start_time` counts
every run Prefect expected in the window.

**Unaffected by R4's trap 2.** Prefect pre-creates future `SCHEDULED` runs, but
the window ends at `now`, so they fall outside it and cannot inflate the
breakdown. Runs that were *due* inside the window and are still `SCHEDULED`
(nothing picked them up) **are** counted, under the `SCHEDULED` state — and
that is wanted: during a stall the breakdown reads "1,440 scheduled, 0
completed", which is the second half of the story R4's `latest_run` tells. The
UI must therefore render whatever states come back rather than assuming only
terminal ones.

**Alternatives rejected**:

- *N flows × M outcomes calls to the existing `count_flow_runs`* — satisfies
  FR-012a literally (5 × 4 = 20 calls today) but is 4× the round-trips of the
  history call for the same answer, and puts SC-007's 2s p95 at needless risk.
  The existing counter stays in use for the Tasks *list* count (FR-006); it is
  just not the right tool for a per-flow state breakdown.
- *Reading runs and tallying in Python* — explicitly forbidden by FR-012a.

---

## R4 — How is "latest run" read, given Prefect pre-creates runs and collision-cancelled runs never start?

The question has two traps, one on each side of `now`. Both were found by
probing the installed Prefect; the first was found only after plan review
round 1 (critique E1).

### Trap 1 (behind `now`) — a cancelled run has no `start_time`

The existing reader sorts `START_TIME_DESC` (`FlowRunReader.read_flow_runs`),
which is correct for the Tasks list and wrong here. A run cancelled by a
`CANCEL_NEW` collision never starts, so `start_time = None` and it sorts below
older runs that did start. The view would report a stale "last run: Completed"
while every subsequent tick was being silently cancelled — the motivating
incident, reproduced by a sort key. `EXPECTED_START_TIME_DESC`
(verified present in `FlowRunSort`) is populated for every scheduled run
whether or not it ever ran.

### Trap 2 (ahead of `now`) — Prefect pre-creates future `SCHEDULED` runs

Prefect's `Scheduler` loop service creates flow runs in the `SCHEDULED` state
ahead of time. Verified on the installed settings, with no override anywhere in
this repo:

```text
server.services.scheduler.enabled            = True
server.services.scheduler.min_runs           = 3
server.services.scheduler.min_scheduled_time = 1:00:00
```

For each `* * * * *` catalogue schedule that is roughly **60 runs sitting in
`SCHEDULED` with an `expected_start_time` in the future, at all times**. A
plain `EXPECTED_START_TIME_DESC` / `limit=1` read therefore returns a run that
has not happened, permanently, for every scheduled flow — and, worse, the
scheduler keeps producing them whether or not any worker is alive, so even
"newest run whose expected start is behind `now`" stays fresh during a total
stall.

Bounding the read at `now` alone is not enough. **The run that answers "is this
job alive" is the newest run that actually left the queue** — anything that
reached `RUNNING` or a terminal state.

### Decision

One read per scheduled deployment:

```python
FlowRunFilter(
    deployment_id=FlowRunFilterDeploymentId(any_=[deployment_id]),
    expected_start_time=FlowRunFilterExpectedStartTime(before_=now),
    state=FlowRunFilterState(
        type=FlowRunFilterStateType(not_any_=[StateType.SCHEDULED, StateType.PENDING])
    ),
)
# sort=FlowRunSort.EXPECTED_START_TIME_DESC, limit=1
```

This is the feature's `latest_run`: **the newest run Prefect expected to have
started by now that got past the queue.** Call it the *latest executed run* in
prose; the two filter clauses are what make the phrase true.

**Verified in 3.8.6**: `FlowRunFilterExpectedStartTime` exposes `before_` /
`after_` and compiles to `expected_start_time <= before_`;
`FlowRunFilterStateType.not_any_` compiles to `state_type NOT IN (...)`;
`FlowRunFilter` carries both alongside `deployment_id`, combined with `and_`.

**Why both clauses and not just the state exclusion**: today a future run is
always `SCHEDULED`, so the time bound is redundant. It is kept because it is
the clause that states the intent — a future `CRASHED` run, however it arose,
must not become "the last run" — and because it makes the read's meaning
legible without knowing Prefect's scheduler internals.

**What this deliberately hides**: a due run still sitting in `SCHEDULED`
because no worker picked it up. That is correct. Such a run is not an outcome;
its absence from `latest_run` is precisely what lets the R6 overdue rule fire.
The breakdown in R3 still counts it — see the note there — so the operator sees
both halves: *last completed run 3 days ago* **and** *1,440 runs scheduled, 0
completed in 24h*.

**Consequences downstream**: R6's `OVERDUE`, `NEVER_RUN` and `NO_RECENT_RUNS`
rules are stated against this bounded read, not against "no runs at all". They
are unreachable under any unbounded reading.

**Consequence for US2's drill-down**: `/tasks?workflow=<name>` applies no such
bound, so the pre-created `SCHEDULED` runs *will* appear there. The existing
reader sorts `START_TIME_DESC` and they have no `start_time`, so they do not
crowd the top of the list. This is expected, not a defect — the drill-down is
the raw run list — and the e2e task says so explicitly rather than leaving the
author to discover it.

**Cost**: 2 calls per scheduled flow (this plus R3), issued concurrently with
`asyncio.gather`. 10 calls for today's five schedules. Scales with flow count,
never with run count — FR-012a satisfied, and SC-006's "client never fans out"
is satisfied because all of it happens behind one GraphQL field.

---

## R5 — Where does the overdue threshold come from?

Spec Assumption 6: overdue = no run started within three of the flow's own
scheduled intervals. That needs the interval, derived from the cron.

**Decision**: Derive the interval by asking Prefect for the next two fire times
and subtracting, using
`prefect.server.schemas.schedules.CronSchedule.get_dates(n=2, start=...)`.

**Evidence** (probe):

```text
CronSchedule(cron="* * * * *").get_dates(n=3, start=now) -> 06:42, 06:43, 06:44
CronSchedule(cron="17 2 * * *").get_dates(n=2, start=now) -> 2026-09-25 02:17, 2026-09-26 02:17
```

**No new dependency.** Prefect vendors croniter
(`from prefect._vendor.croniter import croniter`). Adding `croniter` or
`cron-descriptor` to `pyproject.toml` would be an "Ask First" item under
`AGENTS.md` with no human available to ask, so avoiding it is both simpler and
unblocking.

**On importing from `prefect.server`**: this is established practice in this
codebase, not a reach into internals — `backend/infrahub/prefect_server/`
(`app.py`, `database.py`, `models.py`, `events.py`, `bootstrap.py`) and
`backend/infrahub/cli/db_commands/reset.py` already import `prefect.server.*`
in production code. The client-side `CronSchedule` has no `get_dates`
(verified), so the server schema is the only in-tree option.

**Containment**: the import is confined to one module
(`task_manager/scheduled_flow/schedule_window.py`) behind a narrow function, so
a future Prefect upgrade has exactly one place to fix, guarded by a unit test.

**Alternatives rejected**:

- *Fixed wall-clock overdue threshold* — already rejected by Assumption 6; one
  threshold cannot serve a one-minute flow and a daily one.
- *Prefect's `deployment.status`* (`READY`/`NOT_READY`) — reports work-pool
  polling health, not whether the schedule is producing runs. It answers a
  different question and would have been green during the motivating incident.

---

## R6 — Where is the health verdict computed?

**Decision**: Backend, in a pure function over
`(latest_run, schedule_interval, now, deployment_created_at)`.

**Rationale**: FR-012 requires one request; recomputing in the client would mean
shipping raw history and the cron and duplicating the rule in TypeScript. A pure
backend function is unit-testable without Prefect (Constitution IV: unit tests
run in seconds) and keeps one definition of "unhealthy".

**Every rule below is stated against R4's bounded `latest_run`** — the newest
run whose expected start is behind `now` *and* which got past the queue. "No
runs" throughout means "no such run", never "no rows for this deployment":
there are always rows, because Prefect pre-creates them (R4, trap 2). Written
against unbounded runs, rules 1, 4 and 5 are all unreachable.

**Verdict precedence** (first match wins):

1. `PAUSED` — the schedule exists but is inactive
   (`not schedule.active or deployment.paused`). Ranked first so that "nothing
   is running because it is switched off" never masquerades as a time-based
   fault; a paused flow is never reported as unhealthy. Nothing is lost by
   ranking it above `FAILED` — the last-run outcome is a separate displayed
   field (FR-015), so a paused flow whose last run failed still shows that
   failure in its own column.
2. `OVERDUE` — the flow is active, the interval is known, the deployment has
   existed for at least 3 × interval, and either there is no `latest_run` or
   its `expected_start_time` is older than `now - 3 × interval`. The
   deployment-age guard is what keeps a freshly registered daily flow out of
   `OVERDUE` (it has simply not come due yet) and into rule 4.
3. `FAILED` — `latest_run` in `FAILED` or `CRASHED`.
4. `CANCELLED` — `latest_run` in `CANCELLED` or `CANCELLING`. This is the
   `CANCEL_NEW` collision signal: those runs *are* terminal, so they are
   `latest_run` material and produce a recent `CANCELLED` verdict rather than
   `OVERDUE`. `collision_strategy` is carried on the summary so the UI can
   explain why.
5. `NEVER_RUN` — no `latest_run`, and `deployment_created_at` is known and
   within `ASSUMED_RUN_RETENTION_DAYS` (below). The deployment is too young for
   purging to explain the absence.
6. `NO_RECENT_RUNS` — no `latest_run` and the comparison is inconclusive:
   `deployment_created_at` unknown, or it predates
   `ASSUMED_RUN_RETENTION_DAYS`, or the cron could not be interpreted so no
   overdue window exists. This is the spec's "say 'no recent runs' rather than
   guess".
7. `HEALTHY` — otherwise.

`NEVER_RUN`, `NO_RECENT_RUNS` and `PAUSED` are distinct from both success and
failure, satisfying FR-010.

**Worked cases** (each is a required unit test — see T021):

| Situation | Verdict |
|---|---|
| every-minute flow, worker alive, last run Completed 30s ago | `HEALTHY` |
| every-minute flow, worker stopped 3 days ago; ~60 future `SCHEDULED` runs exist; newest executed run Completed 3 days ago | `OVERDUE` ← the motivating incident, SC-003 |
| every-minute flow whose ticks are being `CANCEL_NEW`-cancelled | `CANCELLED` |
| daily flow registered 2h ago, no runs yet | `NEVER_RUN` |
| every-minute flow registered 10s ago, no runs yet | `NEVER_RUN` (age guard suppresses `OVERDUE`) |
| flow with an uninterpretable cron and no executed runs | `NO_RECENT_RUNS` |
| paused schedule, whatever else is true | `PAUSED` |

**Retention window** for rules 5/6 — `ASSUMED_RUN_RETENTION_DAYS`, a named
module-level constant in `scheduled_flow/health.py`, valued at 30 to match the
`infrahub tasks flush flow-runs` CLI default.

It is **not** read from configuration, and plan review round 1 (critique E2)
was right that the earlier "read it from configuration" instruction was
unexecutable: there is no retention setting in `backend/infrahub/config.py`
(`grep -n retention` → no matches), and purging is not automatic at all —
`FlowRunRetention.purge` has exactly one caller, the CLI (verified: no other
reference under `backend/infrahub/`). There is no cadence to read because
nothing persists one.

Adding a setting was the alternative (critique E2 option (a)) and is rejected:
it would be a new Ask-First surface with a generated-doc obligation
(`docs/docs/reference/configuration.mdx`) bought for a single label. A wrong
constant is cheap here by construction — it can only flip **between
`NEVER_RUN` and `NO_RECENT_RUNS`**, two ways of saying "no history to show
you". It can never produce a false `HEALTHY`, `FAILED` or `OVERDUE`, because
those rules never consult it. That asymmetry is the whole justification; the
constant carries it as a comment so a later reader does not "improve" it into a
setting.

---

## R7 — How is the ≤60s staleness bound met without polling?

FR-019a: no auto-polling, manual refresh, data no more than 60s stale.

**Decision**: Cache the assembled summary in the existing Infrahub cache under a
single key with a 60-second TTL, reusing `KVTTL.ONE_MINUTE` — the same TTL
`FlowRunCounter` already uses.

The frontend's existing `RefreshButton` + TanStack Query invalidation provides
manual refresh with no new UI primitive. A manual refresh inside the TTL will
serve the cached value; that is within the stated bound and is the deliberate
trade for not hammering Prefect.

**Rejected**: per-flow cache keys (turns one cache round-trip into N, and lets
the view render a self-inconsistent mix of ages).

---

## R8 — Human-readable schedule rendering

FR-015 requires the schedule in human-readable form.

**Decision**: The backend returns structured facts — `cron`, `timezone`,
`interval_seconds`, `next_run_at`, `active`. The frontend renders the sentence
with a pure, unit-tested TypeScript helper, falling back to the raw cron
expression when the shape is not recognised.

Derivation from `interval_seconds` + `next_run_at` covers all five schedules in
the catalogue today:

| interval | rendering |
|---|---|
| < 1 h, whole minutes | "Every minute" / "Every N minutes" |
| exactly 1 h | "Hourly at :MM" |
| exactly 24 h | "Daily at HH:MM UTC" |
| anything else | the raw cron expression |

**No new dependency.** `cronstrue` is not in `frontend/app/package.json`
(verified) and adding it is an "Ask First" item. The fallback keeps the helper
honest rather than pretending to handle arbitrary crons.

---

## R9 — Existing patterns this feature must follow

Read from the code, to keep the plan inside established structure
(Constitution VII):

| Concern | Established pattern | Where |
|---|---|---|
| Prefect access | Narrow `Protocol` per capability, one `PrefectClientAdapter` implementing all | `task_manager/flow_run/prefect_client.py` |
| Orchestration | A service composing filter-builder + reader + counter + enricher, built by a `build_*` factory | `task_manager/flow_run/service.py::build_prefect_task_service` |
| Transport-agnostic I/O | Pydantic criteria/result models; GraphQL never sees Prefect objects | `task_manager/flow_run/models.py` |
| GraphQL shaping | A serializer class turning result models into the connection dict | `graphql/queries/task.py::FlowRunConnectionSerializer` |
| Selection-set awareness | `extract_graphql_fields` → `FlowRunFetchOptions`, so unselected data is never fetched | `graphql/queries/task.py::_build_fetch_options` |
| Caching | Hash the filter body into a key; TTL-bounded | `task_manager/flow_run/cache_key.py`, `count.py` |
| Frontend entity slice | `api/` (graphql doc + thin caller) → `domain/use-cases/` (unwrap, throw on errors) → `ui/queries/` (TanStack options + hook) → `ui/` (components) | `frontend/app/src/entities/tasks/**` |
| Frontend filters | `useFilters()` reads URL-backed filters; `tasks-filter-form.tsx` renders fields; `getFiltersFromFormData` maps back | `entities/tasks/ui/task-filters.tsx` |

**Consequence**: the scheduled-flows work becomes a sibling package
`task_manager/scheduled_flow/` mirroring `flow_run/`, not new machinery inside
`flow_run/`. The two answer different questions (deployments vs. runs) and share
only the Prefect adapter.

---

## R10 — Does making internal runs selectable expose anything new?

Spec Assumption 3 / FR-013a already settled that no new class of sensitive data
is exposed, having checked that the payload-bearing `webhook-send` workflow is
already `CORE` and already masks headers.

**Re-verified for the plan**: `HttpRequest.headers` in
`backend/infrahub/graphql/types/task.py` is documented as "Request headers as
sent, with secret values masked", and `WEBHOOK_SEND` is the only entry in
`TASK_TYPES` besides the default. Internal runs resolve to the plain `TaskNode`
type via `TaskNodeInterface.resolve_type`, so they gain no extra fields.

**Decision**: no masking work in this feature; no new permission gate
(Assumption 3). FR-026 is satisfied structurally — `TaskActionGenerator` keys
off workflow name and state, neither of which this feature changes.
