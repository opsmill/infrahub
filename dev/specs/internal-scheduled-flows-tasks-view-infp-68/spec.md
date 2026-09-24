# Feature Specification: Internal & Scheduled Background Flows in the Tasks View

**Feature Branch**: `OPS-21-show-internal-and-scheduled-background-flows-in-the-tasks-view-infp-68`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Infrahub runs background flows that are invisible in the web UI: scheduled/recurring flows (git repository sync, deadlock cleanup, telemetry, webhook reconfigure) and event-driven internal flows. The Tasks view only ever shows CORE/USER workflows. When a background flow misbehaves, operators have no signal in the product — they must go straight to the Prefect API/DB. (ticket infp-68)"

## Overview

Infrahub's Tasks view is the product's only window onto background execution. It
shows every `CORE` and `USER` workflow run, and it shows internal runs only by
accident — whichever ones happen to stamp the namespace tag on themselves while
running. Eleven of the nineteen internal workflows never do, and that set is
where the most operationally-critical background jobs live: repository sync,
deadlock reclamation, merge watching, telemetry, webhook reconfiguration.

The motivating incident: a global lock sat in Redis for 10+ days, held by a
worker that no longer existed. The reclamation path is the `clean-up-deadlocks`
flow, scheduled every minute. Because it is an internal workflow, nothing in the
product could answer "is it running? is it succeeding? is it failing?" The
answer only existed in the Prefect API.

This feature makes internal and scheduled background flows observable inside
Infrahub, without drowning the existing Tasks list in the ~4,320 runs/day the
every-minute flows generate.

### Verified current behaviour

The paths quoted in the original feature request were stale. Re-verified against
the branch point (`origin/develop`):

| Fact | Location |
|------|----------|
| The flow-run filter unconditionally requires the namespace tag: `filter_tags = [TAG_NAMESPACE]`, applied as `FlowRunFilterTags(all_=filter_tags)` | `backend/infrahub/task_manager/flow_run/filters.py:30` and `:40` |
| `TAG_NAMESPACE = "infrahub.app"` | `backend/infrahub/workflows/constants.py:31` |
| At **deployment** registration the namespace tag is stamped on non-internal workflows only; the workflow-type tag is stamped on **all** of them | `backend/infrahub/workflows/models.py:88-92` (`get_tags()`) |
| At **run** time a flow can add tags to itself, and does so *with the namespace tag by default* (`namespace: bool = True`) | `backend/infrahub/workflows/utils.py:22-64` (`add_tags()`), default at `:26` |
| The one deliberate opt-out from that default | `backend/infrahub/groups/tasks.py:22` (`namespace=False`) |
| Workflow-type tag shape: `infrahub.app/workflow-type/{internal\|core\|user}` | `WorkflowTag.WORKFLOWTYPE`, `backend/infrahub/workflows/constants.py:33-44` |
| GraphQL `InfrahubTask` arguments — `limit`, `offset`, `related_node__ids`, `branch`, `state`, `workflow`, `ids`, `q`, `log_limit`, `log_offset`. No workflow-type argument. | `backend/infrahub/graphql/queries/task.py:183-197` |
| Selection criteria carried into the filter builder | `FlowRunQueryCriteria`, `backend/infrahub/task_manager/flow_run/models.py` |
| Frontend list + count queries (no type variable) | `frontend/app/src/entities/tasks/api/get-task-list-from-api.ts`, `…/get-task-count-from-api.ts` |
| Filter form offers Branch and State only | `frontend/app/src/entities/tasks/ui/tasks-filter-form.tsx` |
| List columns: title, branch, state, related nodes, progress, workflow, updated at | `frontend/app/src/entities/tasks/ui/task-items.tsx` |
| Tasks page shell | `frontend/app/src/pages/tasks/index.tsx` |
| No Prefect *deployment* read capability exists today (the adapter exposes flow runs, logs, artifacts, flows, counts, state writes — not deployments or their schedules) | `backend/infrahub/task_manager/flow_run/prefect_client.py` |

### Two different tags, doing two different jobs

The feature request (and the first draft of this spec) treated "is internal" and
"lacks the namespace tag" as the same statement. They are not, and the difference
is load-bearing for this feature.

- **Workflow type** is a per-**deployment** classification, fixed in the
  catalogue and stamped as `infrahub.app/workflow-type/{type}` on every run of
  every workflow, internal included.
- **The namespace tag** is, in practice, a per-**run** "show this in the Tasks
  view" switch. Deployment registration grants it to `CORE` and `USER`
  workflows; a running flow can also grant it to itself by calling `add_tags()`,
  which adds it unless the caller passes `namespace=False`.

So the default Tasks list today is *not* "`CORE` and `USER` runs". It is "runs
carrying the namespace tag", and eight `INTERNAL` workflows already put
themselves in it:

| Internal workflow already visible today | `add_tags()` call |
|---|---|
| `action-run-generator` | `backend/infrahub/actions/tasks.py:169` |
| `action-run-generator-group-event` | `backend/infrahub/actions/tasks.py:194` |
| `generator-definition-run` | `backend/infrahub/generators/tasks.py:153` |
| `diff-refresh-all` | `backend/infrahub/core/diff/tasks.py:62` |
| `proposed-changed-run-generator` | `backend/infrahub/proposed_change/tasks.py:407` |
| `proposed-changed-repository-checks` | `backend/infrahub/proposed_change/tasks.py:624` |
| `artifacts-generation-validation` | `backend/infrahub/proposed_change/tasks.py:753` |
| `proposed-changed-refresh-artifacts` | `backend/infrahub/proposed_change/tasks.py:1331` |

That this is intentional rather than incidental is settled by the single
opt-out in the codebase: `graphql-query-group-update` passes `namespace=False`
so it stays out of the list. Every other caller takes the default.

Two consequences this spec has to respect:

1. **Removing internal runs from the default list would be a user-visible
   regression**, not a no-op. Any redefinition of the default filter that keys
   on workflow type instead of on the namespace tag silently drops these eight.
2. **Even for those eight, visibility starts late.** The tag is written from
   inside the running flow, so a run that crashes, is cancelled by a concurrency
   collision, or never leaves `Scheduled`/`Pending` never reaches its
   `add_tags()` call and never appears. The failures most worth seeing are
   precisely the ones this mechanism cannot show.

### Verified inventory of hidden flows

`backend/infrahub/workflows/catalogue.py` declares **19** `INTERNAL` workflows
(the request said 16). Eight of them are already partly visible per the table
above; the remaining **eleven** are invisible in every state:
`anonymous_telemetry_send`, `branch-purge-tasks`, `clean-up-deadlocks`,
`git-repository-diff-names-only`, `git_repositories_sync`,
`graphql-query-group-update`, `merge-watcher`, `proposed-changed-pipeline`,
`webhook-configure`, `webhook-invalidate-headers`, `webhook-process`.

The feature's motivation survives the correction intact: **five** internal
workflows are scheduled (the request listed four — it missed `merge-watcher`, a
third every-minute `CANCEL_NEW` flow), and not one of the five calls a tagging
helper, so all five are wholly invisible today.

| Workflow | Cron | Concurrency | Collision strategy |
|----------|------|-------------|--------------------|
| `git_repositories_sync` | `* * * * *` | 1 | `CANCEL_NEW` |
| `clean-up-deadlocks` | `* * * * *` | 1 | `CANCEL_NEW` |
| `merge-watcher` | `* * * * *` | 1 | `CANCEL_NEW` |
| `anonymous_telemetry_send` | `<random minute> 2 * * *` | — | — |
| `webhook-configure` | `<random minute> 3 * * *` | 1 | `ENQUEUE` |

The remaining 14 are event-driven: `action-run-generator`,
`action-run-generator-group-event`, `generator-definition-run`,
`diff-refresh-all`, `branch-purge-tasks`, `graphql-query-group-update`,
`git-repository-diff-names-only`, `proposed-changed-pipeline`,
`proposed-changed-refresh-artifacts`, `proposed-changed-run-generator`,
`proposed-changed-repository-checks`, `artifacts-generation-validation`,
`webhook-process`, `webhook-invalidate-headers`. Eight of these fourteen are the
already-partly-visible ones listed above.

Three every-minute schedules means roughly **4,320 runs/day** from schedules
alone (the request's 2,880 figure assumed two). All three use `CANCEL_NEW`: if
one run hangs, every subsequent run is silently cancelled and the job stalls
with no signal anywhere in the product. That failure mode is the single most
important thing this feature has to make visible.

## Clarifications

No human reviewer is available during this pipeline, so each question below was
answered from the codebase and the feature request. The rationale for every
answer is recorded in **Assumptions**.

### Session 2026-09-24

- Q: Should an internal run's flow parameters be shown in task detail, or masked/withheld? → A: Shown, same as today for `CORE`/`USER` runs; no new masking introduced.
- Q: How is the 24-hour outcome breakdown bounded so the summary stays fast at ~4,320 runs/day? → A: Aggregate counts only, never per-run reads; work scales with flow count, not run count.
- Q: Does the scheduled-flows view auto-refresh? → A: No auto-polling; manual refresh plus a cache no staler than 60s.
- Q: Does the scheduled-flows view cover internal schedules only, or every scheduled workflow? → A: Every workflow that carries a schedule, whatever its type.
- Q: How is a flow's health conveyed? → A: Text or icon plus colour, never colour alone.

### Session 2026-09-24 (review round 1)

- Q: Eight internal workflows tag themselves into the default Tasks list at run time. Do they keep appearing there? → A: Yes, unchanged. Removing them would be an unrelated user-visible regression; see Assumption 18.
- Q: Prefect's tag filter has no "lacks tag X" predicate. How is the default selection expressed once the type facet exists? → A: The default keeps requiring the namespace tag; the namespace requirement becomes *conditional* rather than unconditional, and is replaced by workflow-type tags only when a type is actually requested. See Assumption 19.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find out whether a background job is alive (Priority: P1)

An operator is investigating a stuck branch merge or a repository that has not
picked up its latest commit. They open the Tasks view, switch to the scheduled /
system view, and immediately see every scheduled background flow with its
schedule, the outcome and timestamp of its most recent run, and whether it is
behind schedule.

**Why this priority**: This is the incident scenario that motivated the work. It
is the smallest slice that would have shortened a 10-day outage to minutes, and
it delivers value without any change to how the existing Tasks list behaves.

**Independent Test**: Load the scheduled-flows view on an instance with the five
scheduled deployments registered; confirm each one is listed with its schedule
and last-run outcome. Stop the worker, wait past the overdue threshold, and
confirm the affected flows are flagged.

**Acceptance Scenarios**:

1. **Given** an Infrahub instance with the scheduled deployments registered and
   a healthy worker, **When** the operator opens the scheduled-flows view,
   **Then** all five scheduled flows are listed, each showing its name, its
   schedule in human-readable form, the state of its most recent run, and when
   that run happened.
2. **Given** `clean-up-deadlocks` whose most recent run was `CANCELLED`,
   **When** the operator opens the scheduled-flows view, **Then** that flow is
   visually distinguished as unhealthy and its outcome is stated without the
   operator having to open anything.
3. **Given** `git_repositories_sync` with no run started in the last three
   scheduled intervals, **When** the operator opens the scheduled-flows view,
   **Then** that flow is flagged as overdue and the time since its last run is
   shown.
4. **Given** a scheduled flow that has never run on this instance, **When** the
   operator opens the scheduled-flows view, **Then** the flow is still listed,
   with its schedule, and its run state reads as "never run" rather than as an
   error or an empty cell.

---

### User Story 2 - Drill into a background flow's runs and logs (Priority: P1)

Having spotted an unhealthy scheduled flow, the operator drills into it and sees
that flow's recent run history — including failed and cancelled runs — and can
open any individual run to read its logs, exactly as they can for a `CORE` task
today.

**Why this priority**: A health signal that dead-ends is not actionable. Story 1
tells the operator *that* something is wrong; this story is how they find out
*what*. Together they are the MVP.

**Independent Test**: From the scheduled-flows view, follow the drill-down for
one flow and confirm the resulting run list is scoped to that flow and contains
its failed/cancelled runs; open one run and confirm its logs render.

**Acceptance Scenarios**:

1. **Given** the scheduled-flows view, **When** the operator drills into one
   flow, **Then** they land on a task list filtered to that workflow's runs,
   most recent first, including runs in every terminal state.
2. **Given** an internal flow run in the drill-down list, **When** the operator
   opens it, **Then** the existing task-detail page resolves the run and renders
   its logs, state, timestamps and parameters.
3. **Given** an internal flow run that failed, **When** the operator opens it,
   **Then** the failure is presented with the same prominence the Tasks view
   already gives failed `CORE` runs.

---

### User Story 3 - Filter the Tasks list by workflow type (Priority: P2)

An operator working in the main Tasks list wants to widen it to include internal
runs — for example to see every run, of any type, that touched a given branch
during an incident window. They apply a Type filter and internal runs appear,
including the eleven internal workflows that never show up without it. With no
Type filter applied, the list is byte-for-byte what it is today.

**Why this priority**: This is the general-purpose escape hatch behind the
curated views in stories 1 and 2. It is valuable but secondary: the curated
scheduled view is what an operator reaches for first, and the raw list at 4,320
runs/day is only useful once narrowed by another facet.

**Independent Test**: With no Type filter, snapshot the Tasks list and count and
confirm they match the pre-change behaviour. Apply Type = System and confirm
internal runs appear.

**Acceptance Scenarios**:

1. **Given** a fresh Tasks view with no Type filter applied, **When** the list
   and count load, **Then** the results are exactly the runs they contain today
   — every run carrying the namespace tag, which includes the runs of the eight
   internal workflows that tag themselves — and nothing has been added or
   removed.
2. **Given** the Tasks filter panel, **When** the operator selects Type =
   System, **Then** the list and the count both narrow to internal runs only,
   including runs of internal workflows that never carry the namespace tag and
   runs that ended before reaching their `add_tags()` call.
3. **Given** Type = System combined with a Branch or State filter, **When** the
   list loads, **Then** both conditions are applied together.
4. **Given** Type = System, **When** internal rows render, **Then** columns that
   do not apply to them (branch, related nodes) are shown as empty rather than
   as an error or a placeholder that implies a value.
5. **Given** a Type filter is active, **When** the operator reloads or shares the
   page URL, **Then** the filter is preserved, consistent with the other Tasks
   filters.

---

### Edge Cases

- **An internal run carries the namespace tag** because its flow called
  `add_tags()` with the default. It is in the default Tasks list today and must
  stay there. It must *also* be reachable by Type = System, so the same run is
  returned by two different selections — that is correct, not a bug.
- **Selecting all three types is not the same as selecting none.** The default
  selection is defined by the namespace tag; an explicit type selection is
  defined by the workflow-type tags. Selecting `core` + `user` + `internal`
  returns a strict superset of the default (it picks up the eleven internal
  workflows that never tag themselves). The UI must not imply the two are
  interchangeable, e.g. by auto-selecting all types as the "default" state.
- **An internal run ends before it reaches its `add_tags()` call** — crashed on
  start, cancelled by a `CANCEL_NEW` collision, or stuck in `Scheduled`. It has
  its deployment's workflow-type tag but no namespace tag, so it is invisible
  today even for the eight otherwise-visible workflows. The Type facet must
  reach it.
- **A scheduled deployment exists in Prefect that is not in the catalogue**, or
  a catalogue entry has no matching deployment (partial or failed deployment
  registration). The view must render what it can and say plainly which side is
  missing, rather than erroring or silently omitting.
- **Prefect is unreachable or returns an error** while the scheduled-flows view
  loads. The view must show an explicit error state, not an empty list that
  reads as "all healthy".
- **A schedule with a randomised minute** (`anonymous_telemetry_send`,
  `webhook-configure`) must render its actual configured schedule, not the
  literal template.
- **Run history has been purged.** Flow-run retention is an operator-run CLI
  (`infrahub tasks flush flow-runs`, default 30 days,
  `backend/infrahub/cli/tasks.py:68`; `… flush stale-runs`, default 2 days) and
  is not itself scheduled, so history depth varies per deployment. "Never run"
  and "history purged" are separable without new bookkeeping: a deployment
  created more recently than the retention window and with no runs has genuinely
  never run, whereas one created long before it and with no runs has had its
  history purged. Where the comparison is inconclusive the view must say "no
  recent runs" rather than guess — and neither case may read as a failure.
- **A cancelled-by-collision run** (`CANCEL_NEW`) is not the same failure as a
  run that raised. The view must not present a routine collision cancellation
  identically to a crash, because the every-minute flows generate the former in
  normal operation whenever a run overruns its minute.
- **Volume.** Requesting internal runs without narrowing must remain bounded by
  the existing pagination; the type filter must not be a way to pull thousands
  of rows into one response.
- **Counting.** The count shown alongside the list must be filtered identically
  to the list, including by type.

## Requirements *(mandatory)*

### Functional Requirements

#### Backend — selection

- **FR-001**: The flow-run selection layer MUST accept workflow type as a
  first-class selection criterion, admitting one or more of the three workflow
  types.
- **FR-002**: The namespace-tag requirement MUST become conditional rather than
  unconditional. When one or more workflow types are requested, the tag filter
  MUST be built from the corresponding workflow-type tags and MUST NOT
  additionally require the namespace tag. When no type is requested, the
  namespace tag remains the membership rule (FR-003).
- **FR-003**: When no workflow type is requested, the selection MUST return
  exactly the set of flow runs it returns today: every run carrying the
  namespace tag. That set already includes runs of the eight internal workflows
  that call `add_tags()` with its default `namespace=True`, and those runs MUST
  keep appearing. The regression test covering this MUST assert membership by
  observed result — the same runs in, the same runs out — and MUST NOT be
  written as "no internal runs are returned", which would encode the very
  regression it exists to catch.
- **FR-004**: An explicit selection of all three workflow types MUST NOT be
  treated as equivalent to requesting no type. The two are deliberately
  different sets: the former is defined by the workflow-type tags and is a
  strict superset of the latter, which is defined by the namespace tag. Neither
  the API nor the UI may substitute one for the other, and the UI's unset state
  MUST NOT be implemented as "all types selected".
- **FR-005**: Requesting a workflow type MUST compose with every existing
  selection criterion (branch, state, related node, workflow name, id, free-text
  search, pagination) under AND semantics; requesting multiple types MUST match
  runs of any of them.
- **FR-006**: The run count MUST honour the workflow-type criterion identically
  to the run list.

#### Backend — API surface

- **FR-007**: The task query MUST expose a workflow-type argument accepting a
  list of workflow types, defaulting to unset (preserving today's behaviour).
- **FR-008**: Retrieving a single task run by id MUST resolve internal runs, so
  that a task-detail view can render an internal run's state, timestamps,
  parameters and logs.
- **FR-009**: The system MUST expose the registered scheduled background flows
  as a queryable summary, each entry carrying at minimum: the workflow name, its
  workflow type, its configured schedule, whether the schedule is currently
  active, the state and timestamp of its most recent run, and a count of its
  recent runs broken down by outcome.
- **FR-009a**: That summary MUST cover every workflow that carries a schedule,
  regardless of its workflow type — not only internal ones — so a scheduled
  `CORE` or `USER` workflow added later appears without further work.
- **FR-010**: The scheduled-flow summary MUST report a flow with no run history
  distinctly from a flow whose latest run failed, and MUST not represent either
  as success.
- **FR-011**: The scheduled-flow summary MUST derive a per-flow health verdict
  covering at least: healthy, latest run failed, latest run cancelled, and
  overdue (no run started within the overdue window derived from the flow's own
  schedule).
- **FR-012**: The scheduled-flow summary MUST be answerable in a single request
  — an operator opening it during an incident MUST NOT trigger one request per
  flow from the client.
- **FR-012a**: The recent-outcome breakdown MUST be computed from aggregate
  counts. Producing the summary MUST NOT require reading individual run records
  for the counted window, and the work it does MUST scale with the number of
  scheduled flows (a few dozen at most), not with the number of runs in the
  window (~4,320/day today).
- **FR-013**: Errors reaching the orchestration backend MUST surface as an
  explicit error to the caller, never as an empty or partially-silent success.
- **FR-013a**: Internal runs MUST expose the same fields as `CORE` and `USER`
  runs do today, including flow parameters, and this feature MUST NOT introduce
  a new secret-bearing field into the response. Existing masking (such as
  webhook request-header masking) continues to apply unchanged.

#### Frontend — scheduled flows view

- **FR-014**: The Tasks area MUST offer a dedicated view of scheduled background
  flows, reachable from the Tasks view and addressable by URL.
- **FR-015**: Each entry in that view MUST display the flow name, its type, its
  schedule in human-readable form, the outcome and timestamp of its most recent
  run, and the time elapsed since that run.
- **FR-016**: Entries whose health verdict is failed, cancelled or overdue MUST
  be visually distinguished from healthy entries, and MUST be ordered ahead of
  healthy entries by default so that a problem is visible without scrolling or
  sorting.
- **FR-016a**: A health verdict MUST be conveyed by text or an icon in addition
  to colour, never by colour alone.
- **FR-017**: Each entry MUST offer a drill-down that opens the task list scoped
  to that flow's runs, unfiltered by state so failed and cancelled runs are
  included.
- **FR-018**: A run opened from that drill-down MUST render in the existing
  task-detail view, including its logs.
- **FR-019**: The scheduled-flows view MUST render an explicit loading state and
  an explicit error state.
- **FR-019a**: The scheduled-flows view MUST NOT poll automatically. It MUST
  offer a manual refresh control, consistent with the existing Tasks list, and
  the data it shows MUST be no more than 60 seconds stale relative to the last
  refresh.

#### Frontend — Tasks list type filter

- **FR-020**: The Tasks filter panel MUST offer a Type facet allowing the
  operator to select one or more workflow types.
- **FR-021**: The Type facet MUST default to unset, and with it unset the Tasks
  list and count MUST be unchanged from today.
- **FR-022**: The selected type MUST be threaded through both the task list
  request and the task count request.
- **FR-023**: The Type selection MUST participate in the existing filter
  mechanics: reflected in the URL, counted in the active-filter indicator, and
  cleared by the existing clear-filters control.
- **FR-024**: When internal runs are displayed, columns that carry no value for
  them (branch, related nodes) MUST render empty.
- **FR-025**: The Tasks list MUST display the workflow type of each run when a
  Type filter is active or internal runs are present, so a mixed list is not
  ambiguous.

#### Cross-cutting

- **FR-026**: Recovery actions (retry, cancel) MUST NOT become newly available
  on internal runs as a side effect of making them visible; the existing
  action-availability and permission rules continue to govern which actions a
  run offers.
- **FR-027**: User-facing documentation for the Tasks view MUST be updated to
  describe workflow types, the scheduled-flows view, and how to read the health
  verdicts.
- **FR-028**: The change MUST carry a changelog fragment, as a user-visible UI
  and API change.
- **FR-029**: This feature MUST NOT change which flows call `add_tags()`, nor
  the `namespace` argument any of them passes. Run-time namespace tagging stays
  exactly as it is: the eight internal workflows keep their default-list
  membership through it, and `graphql-query-group-update` keeps its opt-out.
  Reconciling the two tagging mechanisms into one is separate work.

#### Delivery independence

The two frontend surfaces are independently shippable and can be sequenced in
either order:

- **Shared prerequisite** — FR-001, FR-005, FR-008: workflow type as a selection
  criterion, and single-run retrieval resolving internal runs. Both slices need
  these; neither is user-visible on its own.
- **Slice A — scheduled-flows view** (FR-009 – FR-013a, FR-014 – FR-019a) then
  needs the new deployment read path and nothing else.
- **Slice B — Type facet** (FR-002 – FR-004, FR-006, FR-007, FR-020 – FR-025)
  then needs only the filter and query-argument changes.

Slice A is the P1 incident path. Shipping A without B leaves the scheduled view
and its drill-down working and the main Tasks list untouched. FR-026 – FR-029
apply to whichever slice ships.

### Key Entities

- **Workflow type** — the classification (`core`, `user`, `internal`) already
  declared on every workflow in the catalogue and already stamped onto every
  flow run as a tag. This feature promotes it from an internal implementation
  detail to a user-facing facet.
- **Scheduled background flow** — a catalogue workflow that carries a cron
  schedule. Attributes an operator needs: name, type, schedule, whether the
  schedule is active, collision strategy, latest run outcome and timestamp,
  recent outcome breakdown, health verdict.
- **Health verdict** — the derived per-flow judgement (healthy / failed /
  cancelled / overdue / never run) that lets an operator triage the list at a
  glance instead of reading timestamps.
- **Task run** — an individual flow run, already modelled by the Tasks view.
  Unchanged except that internal runs become reachable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator who suspects a stalled background job can determine,
  from inside Infrahub and without any external tooling, whether every scheduled
  background flow has run recently and succeeded — in under 30 seconds and at
  most two clicks from the Tasks view.
- **SC-002**: Every scheduled background flow declared in the catalogue (five
  today, including the three every-minute ones) appears in the scheduled-flows
  view; none is missing.
- **SC-003**: The motivating incident is detectable: with the worker stopped so
  that `clean-up-deadlocks` stops producing runs, the view flags it as overdue
  within three of its scheduled intervals.
- **SC-004**: A flow whose latest run failed or was cancelled is identifiable
  without opening it, sorting, or reading a timestamp.
- **SC-005**: With no Type filter applied, the Tasks list and its count return
  exactly the results they returned before this change — including the runs of
  the eight internal workflows that already appear there — verified by an
  automated regression test, not by inspection.
- **SC-006**: Opening the scheduled-flows view issues a bounded, constant number
  of **client-to-backend** requests regardless of how many scheduled flows
  exist. (Backend-to-Prefect work still scales with the number of scheduled
  flows, per FR-012a; what is fixed is that the client never fans out per flow.)
- **SC-007**: The scheduled-flows view becomes readable within 2 seconds at the
  95th percentile on an instance carrying a full 24 hours of every-minute run
  history.
- **SC-008**: An operator can reach the logs of any internal flow run from the
  scheduled-flows view.
- **SC-009**: The default Tasks list remains usable at production volume: the
  ~4,320 daily runs from the every-minute schedules never enter it unless the
  operator asks for them.
- **SC-010**: Adding a new scheduled workflow to the catalogue makes it appear
  in the scheduled-flows view with no further UI or query work.
- **SC-011**: Every health verdict is legible to an operator who cannot
  distinguish the status colours.

## Out of Scope

- Replacing or embedding the Prefect UI. This feature surfaces a curated
  operational summary, not general-purpose orchestration tooling.
- Changing any schedule, concurrency limit, or collision strategy.
- A "trigger now" / manual-run control for scheduled flows — a plausible
  follow-up, deliberately excluded here.
- Pausing, resuming, or editing schedules from the UI.
- Alerting, notification, or webhook emission on an unhealthy background flow.
- Changing flow-run retention behaviour or making retention scheduled.
- Exposing internal flows through the Python SDK or the CLI.
- Historical trend charts or SLO reporting over background flow health.
- Fixing the underlying `CANCEL_NEW` stall behaviour. This feature makes the
  stall visible; remedying it is separate work.
- Reconciling the two tagging mechanisms. Deployment-level type tagging and
  run-time namespace tagging overlap and mean different things; collapsing them
  into one — and deciding whether the eight self-tagging internal workflows
  should stop tagging themselves — is a deliberate follow-up, not part of this
  change (Assumption 18, FR-029).

## Assumptions

Every decision below was made autonomously, because no human is available to
answer during this pipeline. Each records the option chosen and why.

1. **Both the Type filter and a dedicated scheduled view are in scope.** The
   acceptance criteria said "Type filter and/or System tab", and separately
   required per-flow schedule and latest-run information. A Type filter alone
   cannot satisfy the schedule requirement (schedules live on deployments, not
   on runs), so both are specified. The scheduled view is P1 and the Type filter
   is P2, because the curated view is what answers the incident question.

2. **Deployment/schedule exposure is required, not optional.** The request
   marked it "optionally". It is the only source of "schedule" and of "this flow
   should have run and did not", both of which the acceptance criteria demand,
   so it is treated as required scope.

3. **No new permission gates viewing.** The request said "consider gating behind
   admin perms". Chosen: no new permission. Rationale — the Tasks view is
   already authenticated-only; the data exposed (flow names, states, schedules)
   is of the same sensitivity as the `CORE` task data already shown to every
   authenticated user; and a permission gate would lock out exactly the
   on-call operator this feature exists for, at exactly the wrong moment. There
   is no existing "view tasks" permission to extend, so gating would mean
   inventing one. Mutating actions stay governed by the existing per-action
   permission checks (FR-026).

   The sensitivity concern was checked against the catalogue rather than
   assumed. The payload-bearing webhook workflow is `webhook-send`, which is
   already `WorkflowType.CORE` (`catalogue.py:535-540`) and therefore already
   visible today, with its request headers already masked
   (`HttpRequest.headers`, `backend/infrahub/graphql/types/task.py`). The
   internal webhook workflows — `webhook-process` and
   `webhook-invalidate-headers` — carry ids and fan-out arguments, not
   payloads. The rest of the internal set takes branch names, node ids and
   flags. So exposing internal parameters adds no new class of sensitive data
   (FR-013a). **Flagged for review**: this is the one decision where a reviewer
   could reasonably land differently; if they do, the narrower remedy is to
   restrict the parameter field on internal runs, not to gate the whole view.

4. **No internal run becomes newly visible by default.** The ticket phrases this
   as "internal hidden by default"; the accurate form is that the default list's
   membership does not change in either direction. The eleven internal workflows
   that are invisible today stay invisible until the operator asks for them
   (volume alone makes any other default unusable — see Assumption 13), and the
   eight that are visible today stay visible (Assumption 18).

5. **User-facing label for `INTERNAL` is "System".** The enum value stays
   `internal` on the API. "System" matches the wording in the request and reads
   better to an operator than "Internal", which invites the question "internal
   to what?".

6. **Overdue threshold: no run started within three of the flow's own scheduled
   intervals.** Chosen over a fixed wall-clock threshold so one rule covers both
   an every-minute flow and a daily one. Three intervals rather than two gives
   headroom for a single skipped tick, worker restart, or clock skew without
   crying wolf; for the every-minute flows that means a stall is flagged within
   three minutes, which is far inside the incident window this feature targets.

7. **"Recent runs" for the outcome breakdown means the last 24 hours.** It
   covers a full cycle of every schedule in the catalogue, including the two
   daily ones, and bounds the query cost. A per-flow tunable is not specified.

8. **Collision cancellations are distinguished from failures where the data
   permits.** With `CANCEL_NEW` on three every-minute flows, treating every
   cancellation as a failure would make the view permanently red and therefore
   useless. Where a cancellation cannot be attributed, it is presented as
   cancelled — not as failed, and not as success.

9. **Drill-down reuses the existing Tasks list and task-detail pages** rather
   than introducing a parallel run browser. Keeps one place where a run is read,
   and is why FR-008 (single-run retrieval must resolve internal runs) exists.

10. **The scheduled-flows view is a view within the Tasks area**, reachable from
    the Tasks view and URL-addressable. Whether it renders as a tab, a panel, or
    a sibling route is a design decision left to the planning phase; the spec
    only requires that it be reachable and addressable.

11. **The default-selection behaviour is defined by its result set, not by its
    implementation.** FR-003 pins the observable outcome — the same runs in, the
    same runs out — so the refactor cannot silently change what the Tasks view
    shows, whatever tags it ends up filtering on.

12. **No change to retention.** History depth for internal runs is therefore
    whatever the operator's flush cadence leaves behind. FR-010 and the "run
    history purged" edge case exist so the view degrades honestly rather than
    misreporting.

13. **The three every-minute flows are the volume driver** — ~4,320 runs/day,
    correcting the request's ~2,880 (which predated `merge-watcher`). All volume
    reasoning in this spec uses the corrected figure.

14. **The summary aggregates, it does not enumerate** (FR-012a). At ~4,320 runs
    in the counted window, materialising run records to tally outcomes would
    make the view slower than the Prefect API it is meant to replace. Counting
    is already the cheap path in this codebase — `FlowRunCounter`
    (`backend/infrahub/task_manager/flow_run/count.py`) counts server-side and
    caches above a configurable threshold — so the summary is specified in terms
    of counts.

15. **No auto-polling; manual refresh and a ≤60s cache** (FR-019a). Chosen over
    a live-updating view because three every-minute flows plus per-state counts
    would turn every open tab into sustained load on Prefect, and because the
    existing Tasks list already sets the interaction precedent with its manual
    refresh control. 60 seconds matches the shortest schedule in the catalogue,
    so the view can never miss more than one tick.

16. **The scheduled view is type-agnostic** (FR-009a). Every scheduled workflow
    today happens to be `INTERNAL`, but keying the view on "has a schedule"
    rather than "is internal" costs nothing now and means a future scheduled
    `CORE` workflow is covered automatically.

17. **Health is never colour-only** (FR-016a). An incident-triage surface whose
    entire value is "which row is wrong" must not encode that in hue alone.

18. **The eight self-tagging internal workflows keep appearing in the default
    Tasks list** (FR-003, FR-029). The alternative — moving them behind the Type
    facet so the default becomes cleanly `CORE` + `USER` — is defensible on
    consistency grounds, and was rejected. Reasons: it is a user-visible
    regression unrelated to anything this ticket asks for; the runs it would
    hide (proposed-change checks, generator runs, artifact refresh) are the ones
    users most plausibly look for after triggering a proposed change; and the
    lone `namespace=False` opt-out proves the current membership is a choice
    someone made deliberately, not an oversight. Reconciling the two tagging
    mechanisms is listed as out of scope so it gets its own decision and its own
    changelog fragment rather than riding along here.

19. **The namespace requirement becomes conditional, not removed** (FR-002).
    The ticket's fifth acceptance criterion asks for a filter "driven by the
    workflow-type tag, not a hardcoded namespace requirement". Taken literally —
    default membership rewritten as "has a `core` or `user` type tag" — it
    collides with Assumption 18, and Prefect offers no way to split the
    difference: `FlowRunFilterTags` (3.8.6) exposes only `operator`, `all_`,
    `any_` and `is_null_`, with no "lacks tag X" predicate, so "has the
    namespace tag AND is not internal" is inexpressible. What is both
    expressible and faithful to the request's own wording ("default unchanged
    when no type requested") is to drop the word *unconditional*: the namespace
    tag stays the default membership rule, and a requested type replaces it
    rather than narrowing it. That satisfies the criterion's intent — the filter
    is type-driven whenever type is the question — while leaving the default
    list untouched.

## Dependencies

- Prefect deployment metadata (schedules, active state) must be readable from
  the backend. No such read path exists today
  (`backend/infrahub/task_manager/flow_run/prefect_client.py` covers flow runs,
  logs, artifacts, flows and counts only), so one has to be added.
- The workflow catalogue remains the source of truth for which workflows exist
  and what type each one is.
- The workflow-type tag must keep being stamped on every workflow run
  (`WorkflowDefinition.get_tags()`); this feature makes that tag load-bearing for
  the Tasks view.
- The namespace tag must keep being written by `add_tags()` at its current
  default; the default Tasks list's membership depends on it (FR-003, FR-029).
