# Response: Plan & Tasks critique, round 1

**Feature**: `internal-scheduled-flows-tasks-view-infp-68`

**Date**: 2026-09-24

**Responds to**: `critique-2026-09-24-plan-round-1.md`

**Author**: Planner (spec-kit pipeline)

Both must-address findings are accepted and fixed. I re-ran the reviewer's
probes against the installed `prefect==3.8.6` before changing anything; both
claims hold, and E1 turned out to be worse than reported in one specific way
that the fix had to account for.

---

## E1 — the latest-run read returns a future `SCHEDULED` run

**Accepted.** Verified independently:

```text
server.services.scheduler.enabled            = True
server.services.scheduler.min_runs           = 3
server.services.scheduler.min_scheduled_time = 1:00:00
```

No `PREFECT_API_SERVICES_SCHEDULER_*` override anywhere in the repo, so ~60
future `SCHEDULED` runs per every-minute schedule is the permanent steady
state. R4's read returned one of them, and R6's precedence fell through to
`HEALTHY`, exactly as the critique walked it.

### The fix goes further than the suggested one, because the suggested one is not sufficient

The critique proposed bounding the read with
`FlowRunFilterExpectedStartTime(before_=now)` and calling the state exclusion
optional. That bound is necessary but **not** sufficient, and the reason is the
same scheduler behaviour: Prefect pre-creates runs *whether or not any worker
is alive*. During the motivating incident there is a fresh row due one second
ago and another due 61 seconds ago, all the way back. So "the newest run whose
expected start is behind `now`" stays fresh for as long as the stall lasts,
and `OVERDUE` — whose rule keys off exactly that timestamp — still never fires.

The run that answers "is this job alive" is the newest run that **left the
queue**. So the read is bounded on both axes:

```python
FlowRunFilter(
    deployment_id=FlowRunFilterDeploymentId(any_=[deployment_id]),
    expected_start_time=FlowRunFilterExpectedStartTime(before_=now),
    state=FlowRunFilterState(
        type=FlowRunFilterStateType(not_any_=[StateType.SCHEDULED, StateType.PENDING])
    ),
)
# limit=1, sort=FlowRunSort.EXPECTED_START_TIME_DESC
```

Verified in 3.8.6: `FlowRunFilterExpectedStartTime` exposes `before_`/`after_`
and compiles to `expected_start_time <= before_`;
`FlowRunFilterStateType.not_any_` compiles to `state_type NOT IN (...)`;
`FlowRunFilter` carries both beside `deployment_id` under `and_`.

The state exclusion is the load-bearing clause; the time bound is kept because
it states the intent and guards a future non-`SCHEDULED` row.

`latest_run` now means **the newest run Prefect expected to have started by now
that got past the queue** — a phrase the read makes literally true.

### R6 restated, plus one gap of its own

Every rule is now written against that bounded read, with "no runs" replaced
throughout by "no executed run". Two rules changed beyond restatement:

- **`OVERDUE` gains a deployment-age guard.** Without it, a flow registered ten
  seconds ago is instantly "late". With it, a freshly registered daily flow
  falls to `NEVER_RUN`, which is what US1 acceptance scenario 4 asks for.
- **`PAUSED` moves from rank 6 to rank 1.** Reviewing the ordering under the new
  rules surfaced a latent bug the critique did not name: rule 1 guarded on
  `active`, so a *paused* deployment with no executed runs fell straight past
  the `PAUSED` rule into `NEVER_RUN`/`NO_RECENT_RUNS` and was never reported as
  paused at all. Ranking `PAUSED` first fixes it and makes "a paused flow is
  never reported as unhealthy" literally true. Nothing is lost: the last-run
  outcome is a separate displayed field (FR-015), so a paused flow whose last
  run failed still shows that failure in its own column.

Display ordering (`data-model.md` §4) keeps `paused` near the bottom. That is
deliberate and now says so — R6 answers "what is true of this flow", §4 answers
"how urgently should the operator look at it".

R6 also gained a worked-cases table, which T021 now has to cover row by row.

### R3 confirmed unaffected, with one addition

Agreed — the history window ends at `now`, so future runs fall outside it. R3
now also records the positive: runs that were *due* inside the window and that
nothing executed **are** counted, under `SCHEDULED`. During a stall the
breakdown reads "1440 scheduled, 0 completed", which is the second half of the
story `latest_run` tells. The contract and T039 now require the UI to render
whatever states come back rather than a fixed terminal set.

### Tests

- **T021** must cover the steady state as a named case: *a deployment whose
  only rows are future `SCHEDULED` runs, with the newest executed run hours
  old, resolves to `OVERDUE` and never `HEALTHY`* — and fixtures must include
  those future rows, because a past-runs-only fixture is a shape that does not
  occur in production.
- **T025**'s fake reader models the same steady state (critique E5).
- **T030** asserts it against a real registered every-minute deployment, the
  only tier where the pre-created rows appear without being faked.
- **quickstart Scenario 4** now says to check `latest_run.expected_start_time`
  is in the past while the worker is stopped. A future timestamp there is the
  signature of this regression.

### Drill-down consequence

Recorded, as asked. `/tasks?workflow=<name>` applies none of these bounds by
design, so the pre-created `SCHEDULED` runs appear there; they sort to the
bottom (`START_TIME_DESC`, no `start_time`). T042 states it, and T044 now says
to assert scoping by the presence of the flow's own runs rather than by "every
row is terminal".

---

## E2 — the retention window has no configuration to come from

**Accepted**, and the critique's option **(b)** is taken: a named constant,
`ASSUMED_RUN_RETENTION_DAYS = 30`, in `scheduled_flow/health.py`.

Verification went one step past the critique's and strengthens the choice:
`FlowRunRetention.purge` has **exactly one caller**, the CLI (`grep` for
`FlowRunRetention` and `days_to_keep` under `backend/infrahub/` returns only
`cli/tasks.py` and `retention.py`). Purging is not merely unconfigured — it is
not automatic at all. There is no cadence to read because nothing anywhere
persists one, so option (a) would have been inventing a setting to describe
operator behaviour the product never observes.

A10 and R6 now carry the *why*, in the form the critique asked for: a wrong
constant can only flip between `NEVER_RUN` and `NO_RECENT_RUNS` — two ways of
saying "no history to show you" — and can never produce a false `HEALTHY`,
`FAILED` or `OVERDUE`, because those rules never consult it. That asymmetry is
the justification, and it is recorded as a comment on the constant itself so a
later reader does not "improve" it into a setting.

T022 loses the `retention_days` parameter and gains the constant plus its
comment. The plan's Ask-First section is unchanged and still accurate:
"Database/migration, auth, CI changes: none", no new `config.py` surface, no
`configuration.mdx` regeneration.

---

## Non-blocking items

| ID | Disposition |
|----|-------------|
| **E3** | Fixed in `data-model.md` §2 and `contracts/graphql.md`: the Pydantic model holds `dict[StateType, int]`, the GraphQL type projects `[ScheduledFlowOutcomeCount!]!`, the serializer converts. Both documents now say so; neither reads as stale. |
| **E4** | Fixed in T036. The `scheduledFlows` key lives under `tasksQueryKeys` so one `RefreshButton` invalidation serves both views without a second primitive — now stated as the reason, with a code comment required. |
| **E5** | Fixed in T025, as described above. |

---

## One thing the review did not raise

While restating the contract I noticed `recent_outcomes` was computed (R3),
modelled (`data-model.md` §2), and exposed (`contracts/graphql.md`) but never
rendered — T039's column list stopped at the last-run outcome. That leaves the
ticket's "recurring flows show schedule + recent run outcomes (incl.
failed/cancelled)" acceptance criterion unmet by the task list, and wastes the
per-flow history call. T039 now renders the breakdown.

---

## Files changed

- `research.md` — R3 (one note), R4 (rewritten), R6 (rules restated, worked
  cases added, retention rewritten)
- `plan.md` — Phase B reader table and `health.py` description, Testing
  Strategy, Assumptions A5, A10, A11
- `data-model.md` — `LatestRunInfo` semantics, `RecentOutcomeCounts`
  dict-vs-list note, §4 ordering-vs-precedence note
- `contracts/graphql.md` — `latest_run` and `ScheduledFlowLatestRun` field
  descriptions, `counts` note
- `tasks.md` — T021, T022, T024, T025, T030, T036, T039, T042, T044
- `quickstart.md` — Scenario 4

No change to the architecture, slice boundaries, GraphQL type set, delivery
sequencing or task count (64).
