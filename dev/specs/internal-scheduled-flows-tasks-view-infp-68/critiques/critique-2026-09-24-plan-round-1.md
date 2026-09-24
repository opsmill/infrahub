# Critique: Plan & Tasks — Internal & Scheduled Background Flows (round 1)

**Feature**: `internal-scheduled-flows-tasks-view-infp-68`

**Date**: 2026-09-24

**Artifacts reviewed**: `plan.md`, `tasks.md`, `research.md`, `data-model.md`,
`contracts/graphql.md`, against the approved `spec.md`

**Reviewer**: Spec Reviewer (spec-kit pipeline)

**Verdict**: ⚠️ **PROCEED WITH UPDATES** — two must-address items, both in the
Slice A backend design. Everything else verified clean.

---

## Executive Summary

The plan is unusually well-grounded: every design decision in `research.md` was
closed against the installed `prefect==3.8.6` rather than from memory, and
re-verification confirms it. I independently re-ran the probes behind R1, R2,
R3, R4, R5 and R9 and spot-checked every file and symbol the plan names. All of
them exist and behave as claimed:

| Claim | Verified |
|---|---|
| `FlowRunFilterBuilder.build_flow_run_filter`, `filter_tags = [TAG_NAMESPACE]`, `FlowRunFilterTags(all_=filter_tags)` | ✅ `flow_run/filters.py:30,40` |
| R1 — `all_` and `any_` on one `FlowRunFilterTags` combine with AND | ✅ `_get_filter_list` appends `has_all` and `has_any` to the same list |
| `FlowRunQueryCriteria`, `EnrichedFlowRun` in `flow_run/models.py` | ✅ `:60`, `:88` |
| `WorkflowTagDecoder.branch_name` prefix-strip pattern | ✅ `flow_run/tags.py` |
| `PrefectClientAdapter.count_flow_runs` posts raw via `self.client._client` | ✅ `prefect_client.py:117-118` — the R3/A8 escape-hatch precedent holds |
| `POST /flow_runs/history` with `history_start`/`history_end`/`history_interval_seconds`, buckets on `expected_start_time` | ✅ `prefect.server.api.flow_runs` |
| `FlowRunSort.EXPECTED_START_TIME_DESC`, `read_deployments`, `CronSchedule.get_dates` | ✅ all present in 3.8.6 |
| `KVTTL.ONE_MINUTE`, `build_prefect_task_service`, `TaskState = Enum.from_enum(StateType)`, `HttpRequest.headers` masking, `TaskActionGenerator.generate` returning `[]` for non-`WEBHOOK_SEND` | ✅ all present |
| `task_manager/event/` sibling precedent for the new package | ✅ |
| Every test, frontend, docs and knowledge path named in `tasks.md` | ✅ incl. `tests/e2e/tasks/test_tasks_view.py` being `@pytest.mark.skip` |

The planner's correction to the spec's *Delivery Independence* slice boundary
(that the type-aware filter is foundational for US2's drill-down, not
Slice-B-only) is correct and well argued.

The two must-address items are both in the **scheduled-flow health** path —
Slice A's entire reason for existing. Neither is a style question; the first
would ship a view that reports every flow as healthy during the exact incident
that motivated the feature.

---

## Engineering Lens Findings

### 4b. Failure Mode Analysis

#### E1 🎯 Must-Address — the latest-run read returns a *future* `SCHEDULED` run, so the health verdict can never fire

**Where**: `research.md` R4; `plan.md` Phase B *reader.py* table and Assumption
A5; `tasks.md` T024 (and consequently T021, T022, T030).

**The design**: read the latest run per deployment with
`read_flow_runs(FlowRunFilterDeploymentId(any_=[id]), limit=1,
sort=FlowRunSort.EXPECTED_START_TIME_DESC)`.

**What R4 missed**: Prefect's `Scheduler` loop service **pre-creates flow runs
in the `SCHEDULED` state ahead of time**. Verified on the installed settings,
with no override anywhere in this repo (`grep` over `development/`, `tasks/`,
compose and env files finds no `PREFECT_API_SERVICES_SCHEDULER_*`):

```text
server.services.scheduler.enabled            = True
server.services.scheduler.min_runs           = 3
server.services.scheduler.min_scheduled_time = 1:00:00
```

For the three `* * * * *` catalogue schedules that means roughly **60 flow runs
sitting in `SCHEDULED` with an `expected_start_time` in the future, at all
times**. Sorting `EXPECTED_START_TIME_DESC` and taking `limit=1` therefore
returns a run that has not happened and will not have happened — for every
scheduled flow, permanently.

**Failure scenario** (the motivating incident, reproduced as a bug):

1. The worker stops. `clean-up-deadlocks` produces no further runs.
2. The reader still finds ~60 future `SCHEDULED` runs and returns the furthest
   one — say `expected_start_time = now + 59m`, `state_type = SCHEDULED`.
3. R6's precedence is evaluated against that run:
   - `OVERDUE` — the rule is "no run expected-started within 3 × interval".
     The latest run's expected start is *in the future*, so under any reading
     that keys off `latest_run`, it is not late. Does not fire.
   - `FAILED` / `CANCELLED` — `SCHEDULED` is neither. Do not fire.
   - `NEVER_RUN` / `NO_RECENT_RUNS` — the rules are "no runs"; there are 60.
     Do not fire.
   - → falls through to **`HEALTHY`**.
4. The view reports every scheduled flow healthy, with a last-run timestamp in
   the future, for as long as the stall lasts.

**Requirements this breaks**: FR-011 (health verdict), FR-015 (outcome and
timestamp of the *most recent* run), FR-010 and US1 acceptance scenario 4
(`NEVER_RUN` becomes unreachable — a brand-new deployment has future
`SCHEDULED` runs within one scheduler tick), US1 acceptance scenarios 2 and 3,
and **SC-003**, the criterion that names the motivating incident.

This is the same class of error R4 correctly caught in `START_TIME_DESC` — the
sort key silently redefines "latest run" into something that is not the thing
the operator is asking about. R4 fixed the "never started" half and introduced
the "not yet due" half.

**Suggested fix** (verified available in 3.8.6):

- Bound the latest-run read to runs Prefect expected to have started by now:
  `FlowRunFilter.expected_start_time = FlowRunFilterExpectedStartTime(before_=now)`
  (`FlowRunFilterExpectedStartTime` exposes `after_` / `before_` — confirmed).
  Optionally also exclude `SCHEDULED`/`PENDING` via the existing
  `FlowRunFilterStateType`, but the time bound is the load-bearing one: it is
  what makes "latest run" mean "latest run that was due".
- Re-state R6's `OVERDUE` rule explicitly against that bounded read: overdue =
  the newest *due* run's `expected_start_time` is older than `3 × interval`, or
  there is no due run at all while the deployment is older than that window.
- Re-state the `NEVER_RUN` / `NO_RECENT_RUNS` rules against "no **due** runs",
  not "no runs" — otherwise they stay unreachable.
- Add the regression to T021 as a named case: *a deployment whose only runs are
  future `SCHEDULED` ones (the steady state for an every-minute cron) must not
  resolve to `HEALTHY`.* Without that case the unit tests will be written
  against a fixture shape that never occurs in production.
- T030's component test should assert this against a real registered
  every-minute deployment, where the pre-created runs will actually be present.

**Note on R3**: the 24-hour breakdown is *not* affected — `run_history` buckets
on `expected_start_time` within `[history_start, history_end]`, and the window
ends at `now`, so future runs fall outside it. R3 stands as written.

**Secondary consequence worth a sentence in the plan**: US2's drill-down
(`/tasks?workflow=<name>` + type) will also surface those pre-created
`SCHEDULED` runs. The existing reader sorts `START_TIME_DESC` and they have no
`start_time`, so they will not crowd the top of the list — but T042/T044 should
state whether they are expected in the drill-down rather than leaving the e2e
author to discover them.

### 4g. Dependencies & Integration Risks

#### E2 🎯 Must-Address — the retention window is required to come "from configuration", and no such configuration exists

**Where**: `plan.md` Assumption A10; `research.md` R6 ("Retention window … read
from configuration rather than hard-coded"); `tasks.md` T022 ("Read
`retention_days` from configuration, never hard-coded (plan Assumption A10)").

**Verified**: there is no retention setting in `backend/infrahub/config.py`
(`grep -n retention` → no matches). The 30-day figure A10 cites is a **CLI
argument default**, `days_to_keep: int = 30` on `infrahub tasks flush
flow-runs` (`backend/infrahub/cli/tasks.py`), and `FlowRunRetention.purge`
carries its own unrelated `days_to_keep: int = 2` default
(`flow_run/retention.py:29`). Nothing persists an operator's chosen flush
cadence anywhere the backend could read it at request time.

**Failure scenario**: an implementer picks up T022 and finds the instruction
unexecutable as written. Either they hard-code 30 — directly contradicting the
task's own "never hard-coded", and leaving the `NEVER_RUN` vs `NO_RECENT_RUNS`
split wrong for every operator who flushes on a different cadence — or they add
a new `config.py` setting, which is an unplanned surface the plan does not
account for: it is absent from the Constitution Check, from the Ask-First
section (which asserts "Database/migration, auth, CI changes: none"), and its
generated-doc impact on `docs/docs/reference/configuration.mdx` is unstated.
T059 would catch the stale generated doc, but only after the fact.

**Suggested fix** — pick one and say so explicitly:

- **(a)** Add the config setting deliberately. State it in the plan's Ask-First
  section alongside the GraphQL delta (it is the same category of decision with
  no human to ask), name the setting and its default, and add a task for the
  `docs.generate` regeneration it forces.
- **(b)** Drop the configurability. Use a named module-level constant with the
  CLI default as its value, and rewrite A10 and R6 to say *why* — the
  distinction it powers (`NEVER_RUN` vs `NO_RECENT_RUNS`) is already the
  spec's "say 'no recent runs' rather than guess" fallback, so a wrong constant
  degrades to the honest verdict rather than to a false one. This is the
  cheaper option and stays inside the plan's own "no new surface" posture.

Either is defensible. What is not workable is shipping a task that names a
configuration source that does not exist.

---

## Recommendations (non-blocking)

| ID | Category | Finding | Suggestion |
|----|----------|---------|------------|
| E3 💡 | Contract consistency | `data-model.md` §2 types `RecentOutcomeCounts.counts` as `dict[StateType, int]`, while `plan.md`'s Constitution Check III and `tasks.md` T027 both require "a typed list, never `GenericScalar`". | Not a contradiction if the Pydantic model holds the dict and the GraphQL type projects a list — but say so in one line in `data-model.md`, or the implementer will pick one and the other document will read as stale. |
| E4 💡 | Slice boundaries | T036 puts the `scheduledFlows` query key in `entities/tasks/ui/queries/tasks.query-keys.ts`, i.e. the new slice's key lives in a sibling slice. | Defensible — it is what makes the existing `RefreshButton queryKey={tasksQueryKeys.all}` invalidation reach the new view without a new primitive. Record that as the reason in the task, so it does not read as an accident. |
| E5 💡 | Test fixture realism | T025's fake reader is the executable guard on FR-012a, which is good. | Have that fake also return the future-`SCHEDULED` steady state from E1, so the ordering and health assertions in `test_service.py` exercise the real shape too. |

---

## Product Lens

No must-address items. Scope, priorities (P1 scheduled view → P1 drill-down →
P2 type facet), the MVP boundary, the accessibility requirement (FR-016a /
SC-011, carried into T037 and T038 as *assert by accessible text, not colour*),
and the error/empty/loading states are all handled. The `catalogue_only` /
`workflow_type = None` pair covers both directions of the spec's
partial-registration edge case.

**SC-007** (2s p95 with 24h of history) having no automated gate is correctly
flagged rather than quietly dropped (A12, T061), and the design constraint that
actually protects it is asserted instead (T025). That is the right call — I am
not asking for a perf tier to be invented for it.

---

## Findings Summary

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 | Failure Modes | Latest-run read returns future `SCHEDULED` runs; health is permanently `HEALTHY`, `NEVER_RUN` unreachable, SC-003 fails | Bound the read with `FlowRunFilterExpectedStartTime(before_=now)`; restate R6's `OVERDUE`/`NEVER_RUN` rules against *due* runs; add the steady-state case to T021/T030 |
| E2 | Engineering | 🎯 | Dependencies | A10/R6/T022 require reading the retention window from a configuration that does not exist | Either add the config setting deliberately (declare it Ask-First, add the `docs.generate` task) or use a named constant and rewrite A10/R6 |
| E3 | Engineering | 💡 | Contracts | `counts` typed as dict in `data-model.md`, as a typed list in `plan.md`/T027 | One reconciling line in `data-model.md` |
| E4 | Engineering | 💡 | Structure | New slice's query key lives in the tasks slice | Record the `RefreshButton` invalidation rationale in T036 |
| E5 | Engineering | 💡 | Testing | Unit fixtures will not carry the production steady state | Have T025's fake reader return future `SCHEDULED` runs too |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**. E1 and E2 are blocking and both are contained —
E1 is a filter bound plus three restated rules in R6, E2 is a decision between
two stated options. Nothing about the architecture, the slice boundaries, the
GraphQL contract, or the test strategy needs rework. Re-review should be short.
