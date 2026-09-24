# Plan critique — round 2 (approved)

**Feature**: internal & scheduled flows in the Tasks view (infp-68)
**Artifacts**: `plan.md`, `tasks.md` (+ `research.md`, `data-model.md`,
`contracts/graphql.md`, `quickstart.md`)
**Reviewed commit**: `f88ec0e16`
**Verdict**: **Approved.** No blocking defect remains.

## Round-1 blockers — both closed

### E1 — latest-run read returned future `SCHEDULED` runs

Fixed, and correctly diagnosed further than the critique went. The round-1
finding proposed `expected_start_time before_ now`; the response showed that
bound alone is insufficient, because Prefect's scheduler keeps pre-creating
runs during an outage, so the newest *due* run stays fresh throughout a stall
and `OVERDUE` still never fires. The state exclusion is the load-bearing
clause. That reasoning is correct and the time bound is rightly kept as an
intent statement.

Re-verified against the installed `prefect==3.8.6`:

| Claim | Result |
|---|---|
| `FlowRunFilterExpectedStartTime` exposes `before_` / `after_` | confirmed (`['before_', 'after_']`) |
| compiles to `expected_start_time <= …` | confirmed: `flow_run.expected_start_time <= :expected_start_time_1` |
| `FlowRunFilterStateType.not_any_` | confirmed (`['any_', 'not_any_']`) |
| compiles to `NOT IN` | confirmed: `flow_run.state_type NOT IN (__[POSTCOMPILE_state_type_1])` |
| `FlowRunFilter` carries `expected_start_time` and `state` | confirmed |
| `FlowRunSort.EXPECTED_START_TIME_DESC` | confirmed |
| `POST /flow_runs/history` body shape (`history_start`, `history_end`, `history_interval_seconds`, `flow_runs` filter) | confirmed on `prefect.server.api.flow_runs` |

R6 is now stated against the bounded read throughout; "no runs" has become "no
executed run" everywhere. Two changes beyond restatement are both improvements:

- The **deployment-age guard** on `OVERDUE`. Without it a freshly registered
  flow is instantly late and `NEVER_RUN` (US1 scenario 4) is unreachable from
  the other side.
- **`PAUSED` promoted to rank 1.** This closes a latent gap the round-1 review
  did not name: a paused deployment with no executed runs fell past the
  `PAUSED` rule into `NEVER_RUN`/`NO_RECENT_RUNS`. Nothing is lost, because
  last-run outcome is a separate field (FR-015). `data-model.md` §4 correctly
  explains why display order still puts `paused` near the bottom and why that
  is not a contradiction.

Test coverage follows the fix rather than trailing it: T021 names the
every-minute steady state as a required case *and* requires fixtures to contain
the future rows; T025's fake reader models the same shape; T030 asserts it
against a real registered deployment; quickstart Scenario 4 checks
`latest_run.expected_start_time` is in the past during the stall.

### E2 — retention window read from non-existent configuration

Fixed via option (b), with an additional verification that strengthens the
argument. Re-confirmed:

- `grep -n retention backend/infrahub/config.py` → no matches.
- `FlowRunRetention.purge` has exactly one caller: `backend/infrahub/cli/tasks.py`
  (lines 83 and 104). Purging is not automatic; no cadence is persisted.
- The 30 matches the `flush flow-runs` CLI default
  (`backend/infrahub/cli/tasks.py:72`); the unrelated `days_to_keep: int = 2`
  belongs to `FlowRunRetention.purge`'s own default and to `flush stale-runs`.

`ASSUMED_RUN_RETENTION_DAYS = 30` as a named constant is the right call, and
A10 carries the asymmetry argument in the form requested: a wrong value can
only flip between `NEVER_RUN` and `NO_RECENT_RUNS`, never produce a false
`HEALTHY`/`FAILED`/`OVERDUE`, because those rules never consult it. T022 no
longer takes a `retention_days` parameter. Ask-First remains accurate — no
`config.py` surface, no `configuration.mdx` regeneration.

## Round-1 nits — all closed

- **E3** `data-model.md` §2 now states the dict/list split explicitly (Pydantic
  holds `dict[StateType, int]`, GraphQL projects `[ScheduledFlowOutcomeCount!]!`,
  serializer converts). Neither document reads as stale.
- **E4** T036 records why the query key lives in the `tasks` slice
  (one `tasksQueryKeys.all` invalidation serves both views).
- **E5** T025's fake reader models the future-`SCHEDULED` steady state.

## Self-caught gap, accepted

The planner found that `recent_outcomes` was computed (R3), modelled and
exposed but never rendered — leaving the ticket's "recurring flows show recent
run outcomes (incl. failed/cancelled)" criterion unmet by the task list. T039
now renders the breakdown, including non-terminal `SCHEDULED` counts, which is
the second half of the stall story ("1440 scheduled, 0 completed").

## Non-blocking nits (do not re-review for these)

1. **R6 rule 6's "uninterpretable cron" disjunct is partly unreachable.**
   Rule 5 (`NEVER_RUN`) fires first whenever `deployment_created_at` is known
   and recent, regardless of whether the cron parsed. So the worked-case row
   "flow with an uninterpretable cron and no executed runs ⇒ `NO_RECENT_RUNS`"
   only holds when the deployment also predates the retention window or has an
   unknown creation time. T021 is told to cover the table row by row, so that
   row needs its deployment age stated, or rule 5 needs "and the interval is
   known" added. Low stakes by A10's own argument — the two labels differ only
   in wording — but pick one so the fixture is writable.
2. `plan.md` Assumption A5 and R4 both restate the three-clause read in full.
   Fine as emphasis; just keep them in sync if the read changes again.

## Not asking for changes on

- **SC-007** (2s p95 with 24h of history) still has no automated gate. A12
  flags it, `quickstart.md` verifies it manually, and T025 asserts the design
  constraint that protects it. Correct handling for a criterion no test tier
  can provision.
- **Ask-First GraphQL delta.** Purely additive, fully specified in
  `contracts/graphql.md`, recorded as A1–A3 rather than blocking, per the
  pipeline instruction that no human answers. Both slices stay independently
  droppable.
- **No new dependencies.** R5 and R8 each record where one was the obvious
  route and why the in-tree option was taken.

## Approved

Both blockers are closed with verified evidence, every round-1 nit is
addressed, and the planner found and fixed a coverage gap the review missed.
Architecture, slice boundaries, GraphQL contract, test strategy and the 64-task
breakdown are unchanged and sound. Ready for implementation (OPS-28).
