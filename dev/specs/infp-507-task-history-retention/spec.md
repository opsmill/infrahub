# Feature Specification: Task History and Activity Log Retention

**Feature Branch**: `task-history-retention-infp-507`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "INFP-507 Task history and Activity log retention. Source of truth: the Notion design doc *Task history and Activity log retention* (sections 1 Context, 2 Behaviour, 3 Technical Decisions D1-D10, 4 Boundaries and follow-ups), hardened in a grilling session on 2026-10-04. Target release 1.13."

**Source of truth**: [Notion design doc](https://app.notion.com/p/opsmill/Task-history-and-Activity-log-retention-3dc228b830258012ba28dc3a23eece65). Where this spec and the design doc disagree, the design doc wins.

## Context

Each Infrahub instance keeps two kinds of records in its task manager:

- **Task history**: finished runs of background tasks, with their logs and artifacts. Today it is never deleted and grows until the task manager's database fills its disk, which stopped three customer instances.
- **Activity log**: the Infrahub events shown on the Activities page. Today every event disappears after 7 days, because the task manager's default event retention applies to all events, and the task manager's own internal events (run state changes, heartbeats), about 70 % of stored events, share that retention.

Product decided that each instance keeps both kinds of records for a configured period, deletes older records automatically without affecting the instance, keeps the activity log for its own retention whatever the task manager keeps of its own records, and gets the disk space back. A year or more of activity log is supported in every edition, built so that long retention can become an Enterprise feature later.

The Activities page gets slower as the activity log grows: with a year of activity log, one page takes minutes today. The Activities page work therefore ships with this feature, ahead of the activity log retention.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Task history stops filling the disk (Priority: P1)

An operator upgrades an instance whose task history has grown for months. After the upgrade, finished runs older than the task history retention (30 days by default) are gone, the disk space they used is back, and from then on the instance deletes old runs on its own, so the task manager's storage levels off instead of growing without limit.

**Why this priority**: Unbounded task history is the incident: it stopped three customer instances. It is independent of the other stories and delivers value alone.

**Independent Test**: Seed an instance with finished, stuck and recent runs spanning more than the retention, run the upgrade, and verify that only finished runs older than the retention are gone, the task history storage shrank, and the hourly cleanup keeps deleting runs as they age past the retention.

**Acceptance Scenarios**:

1. **Given** a Compose instance with finished runs older than the task history retention, **When** the operator runs the upgrade, **Then** those runs, their logs and artifacts are deleted and the task history storage is rewritten before the instance starts, and runs within the retention, unfinished runs and their logs are kept.
2. **Given** a Helm instance with the same task history, **When** the operator rolls out the new release, **Then** the upgrade does not run the cleanup and does not fail, and the Helm upgrade guide's maintenance step (stop the server and task workers, run the command for old runs with the rewrite option, start them again) produces the same result as scenario 1.
3. **Given** an upgraded instance, **When** a finished run becomes older than the task history retention, **Then** the automatic cleanup deletes it, with its logs and artifacts, within about an hour.
4. **Given** an operator who needs older runs, **When** they set a longer task history retention before upgrading, **Then** the upgrade deletes only runs older than that value, and rewrites the tables only when the deletes freed most of them (in practice the first upgrade or after lowering a retention).
5. **Given** a run that stays RUNNING or PENDING after a worker crashed, **When** an admin runs the documented command for stuck runs, **Then** the run is marked CRASHED and is deleted once it is older than the task history retention.
6. **Given** an operator who lowered the task history retention, **When** the next automatic cleanup runs, **Then** the runs older than the new value are deleted, and the disk space comes back only after the operator runs the command for old runs with the rewrite option in a maintenance window.

---

### User Story 2 - The Activities page stays fast with a year of activity log (Priority: P2)

A user opens the Activities page on an instance that keeps a year of activity log and filters by account, branch, node or several filters at once, opens an activity's sub-activities, and scrolls back through older events. Pages load in about a second for single filters and within a few seconds for combined filters, the same events appear as today, and scrolling never repeats or skips events.

**Why this priority**: A longer activity log with today's queries makes the Activities page unusable (minutes per page), so this must land before User Story 3 raises what an instance can keep.

**Independent Test**: On a dataset with a year of activity log, compare every Activities filter against today's filters for identical results, and time the default view, single filters, combined filters, sub-activities and branch-name filters.

**Acceptance Scenarios**:

1. **Given** a year of activity log, **When** a user opens the default view or filters by account, branch or node, **Then** the page loads in about 1 s on a repeat load and up to about 3 s on the first load.
2. **Given** a year of activity log, **When** a user combines level, account, branch and event-type filters, **Then** the page loads in 3 to 6 s, and never more than 10 s.
3. **Given** any Activities filter, **When** its results are compared with today's filters over the same data, **Then** both return the same events.
4. **Given** a branch that was deleted, **When** a user filters by its name through an old link or the API, **Then** the page shows that branch's events, and a name that was deleted and created again shows only the current branch's events.
5. **Given** an activity a year old, **When** a user opens its details page, **Then** its sub-activities load in under a second.
6. **Given** a user scrolling the Activities page while new events arrive, **When** they load more events, **Then** the next page continues from the oldest event shown, with no event repeated or skipped.
7. **Given** an activity log retention longer than 180 days, **When** a user scrolls past 180 days, **Then** events up to the retention are returned.

---

### User Story 3 - Operators keep the activity log for a configured period (Priority: P3)

An operator who needs more than 7 days of activity log raises the activity log retention, for example to a year. Infrahub events stay on the Activities page for that period, while the task manager's own internal events are still deleted after their own, shorter retention, so the extra storage goes only to the events users read.

**Why this priority**: It closes the 7-day loss of history, but the default stays at 7 days, so it only takes effect once an operator raises the setting. It depends on User Story 2 shipping first.

**Independent Test**: Raise the activity log retention, generate Infrahub and task-manager events over a period longer than the task manager's own-event retention, and verify that no Infrahub event is deleted before the activity log retention, every task-manager event type is deleted after its own retention, and no related item is left behind.

**Acceptance Scenarios**:

1. **Given** an activity log retention of a year, **When** Infrahub events are older than 7 days, **Then** they are kept and shown on the Activities page until they are older than a year.
2. **Given** the default retentions, **When** the instance is upgraded, **Then** the activity log behaves as today (7 days) and the instance's activity log storage stays the size it is today.
3. **Given** the task manager's own events, **When** they are older than the own-event retention (7 days by default), **Then** they are deleted, whatever the activity log retention.
4. **Given** a task-manager event type missing from Infrahub's list, **When** it is older than the own-event retention, **Then** it is kept for the activity log retention instead, and no Infrahub event is ever deleted because of the list.
5. **Given** Community and Enterprise editions, **When** an operator sets any retention, **Then** both editions accept the same settings with no upper limit.

---

### User Story 4 - One place to configure retention (Priority: P4)

An operator sets how long task history, the activity log and the task manager's own events are kept, once, in the Infrahub configuration, Helm values or compose environment, using the configuration reference, and the values apply wherever the task manager's background services run.

**Why this priority**: Today retention means finding undocumented task-manager environment variables. The settings are delivered with User Stories 1 and 3; this story covers their single entry point, validation and documentation.

**Independent Test**: Set each value through the configuration and through environment variables, in the default deployment and with the background services in their own deployment, and verify that the cleanups use those values and that an invalid combination is rejected at start.

**Acceptance Scenarios**:

1. **Given** the three retention settings, **When** the task manager starts, **Then** its cleanups use them, without the operator setting any task-manager-specific variable.
2. **Given** the task manager's background services in their own deployment (a Helm option), **When** they start, **Then** they use the same retention values, because Infrahub's command starts them.
3. **Given** a retention shorter than 1 day, **When** the task manager starts, **Then** it refuses to start and names the setting.
4. **Given** an own-event retention longer than the activity log retention, **When** the task manager starts, **Then** it logs a warning and uses the activity log retention for Prefect's own events, because every event older than that is deleted anyway.

---

### Edge Cases

- **Upgrade interrupted** (stopped session, timeout, crash): the cleanup keeps running or can be re-run, and a re-run continues where the first one stopped, because it commits one day at a time and logs its progress.
- **Upgrade run against a task manager that is still the previous version** (Helm pre-upgrade): the command reports that the cleanup is not available and the upgrade continues instead of failing.
- **Little to delete** (retention longer than most task history, or a routine upgrade after the first): the upgrade deletes what is older than the retention and skips the rewrite unless the deletes freed most of the tables.
- **The task manager's own cleanup of old runs runs at the same time** (it is on, and runs during the upgrade): both finish and leave the same runs; neither fails.
- **Several task-manager replicas**: only one cleanup runs at a time; the command waits and continues when another replica runs one.
- **A table is locked by something else during the rewrite**: the rewrite waits a bounded time, retries, then skips that table and reports it, and the upgrade completes; other queries never queue behind a rewrite that is waiting for its lock.
- **Existing scripts call the command for old runs with `--days-to-keep` or `--batch-size`**: those options are removed (the command reads the retention setting); the changelog flags it as a breaking change.
- **Rewrite during operation**: the rewrite option is off by default, because each table is locked until its rewrite ends; running it while the instance is up is the operator's choice.
- **Not enough free disk for the rewrite**: the rewrite needs free space for a copy of the remaining rows (under 0.5 GB for 25 GB of task history, 2.2 GB for 100 GB); the upgrade guide states this.
- **PENDING runs that never started**: the command for stuck runs does not catch them; they stay until a follow-up fixes the command.
- **Runs stuck in SCHEDULED, LATE, PAUSED or CANCELLING**: not covered; whether they accumulate is an open question.
- **Branch deleted**: finished runs tagged with the branch are deleted as today, unchanged.
- **Branch name that matches no existing branch and has no "branch deleted" event inside the retention**: the activity log filter returns no events straight away.
- **Two events with exactly the same time at a page boundary**: kept once, by identifier.
- **New task-manager event type after a task-manager upgrade**: an automated check fails in CI; until it is listed, the type is kept for the activity log retention (disk cost only).
- **Lowering the activity log retention**: events older than the new value are deleted by the next cleanup; the event storage does not shrink, which is accepted because lowering is rare.
- **API clients paging the activity log by position**: deep pages of combined filters stay slow (about 70 s at offset 2,000); the Activities page pages by time instead.
- **Activity already lost to the 7-day limit before the upgrade**: not recovered.

## Requirements *(mandatory)*

### Functional Requirements

**Settings**

- **FR-001**: System MUST provide three retention settings: task history (default 30 days), activity log (default 7 days) and the task manager's own events (default 7 days), settable in the Infrahub configuration, Helm values and compose environment.
- **FR-002**: System MUST apply the three settings to the task manager's cleanups at start, without the operator setting task-manager-specific variables.
- **FR-003**: System MUST apply the same settings when the task manager's background services run in their own deployment, by starting that deployment through an Infrahub command.
- **FR-004**: System MUST refuse to start the task manager, naming the setting, when a retention is shorter than 1 day; when the own-event retention is longer than the activity log retention, it MUST log a warning and use the activity log retention for Prefect's own events.
- **FR-005**: System MUST accept the same retention settings, with no upper limit, in every edition.

**Task history**

- **FR-006**: System MUST automatically delete, about every hour, finished runs (completed, failed, cancelled, crashed) whose end time is older than the task history retention, together with their logs and artifacts.
- **FR-007**: System MUST NOT delete runs that are not finished through the automatic cleanup, the command for old runs or the upgrade.
- **FR-008**: The existing operator command for old runs MUST delete the same runs, logs and artifacts as the automatic cleanup, using the task history retention setting.
- **FR-009**: The command for old runs MUST offer a rewrite option, off by default, that returns the disk space of the deleted runs; it MUST rewrite only when the deletes freed most of the tables. The command MUST read the task history retention setting and no longer take a number of days or a batch size.
- **FR-010**: The command for old runs MUST commit its work in steps, log its progress, keep running if the caller disconnects, and be safe to re-run after an interruption.
- **FR-011**: On Compose, the upgrade MUST run the command for old runs with the rewrite option before the instance starts; the Compose upgrade guide offers no way to skip it.
- **FR-012**: The upgrade MUST NOT fail when the task manager it reaches does not yet provide the cleanup; it MUST report that the cleanup was not run.
- **FR-013**: On Helm, the upgrade hook MUST leave the cleanup out, also once the task manager provides it, because the instance is still serving; the Helm upgrade guide MUST describe the maintenance step after the rollout.
- **FR-014**: The command for stuck runs MUST be documented, including that it marks runs RUNNING or PENDING for more than 2 days as CRASHED, and that PENDING runs that never started are not caught.
- **FR-015**: Branch deletion MUST keep deleting the finished runs tagged with the branch, as today.

**Activity log**

- **FR-016**: System MUST keep Infrahub events for the activity log retention and MUST NOT delete an Infrahub event earlier.
- **FR-017**: System MUST delete the task manager's own events once they are older than the own-event retention, through a list of the task manager's event types that Infrahub maintains for the task-manager version it ships with.
- **FR-018**: System MUST delete an event's related items together with the event, leaving none behind.
- **FR-019**: The Activities page and the activity log API MUST return events up to the activity log retention, including events older than 180 days.

**Activities page**

- **FR-020**: The account, branch, node and parent-event filters, and the branch-name filter for merges, rebases and migrations, MUST return the same events as today's filters.
- **FR-021**: A branch-name filter MUST resolve to the current branch of that name; when no branch has that name, it MUST resolve to the branch named in the most recent "branch deleted" event with that name, and MUST return no events when there is none inside the retention.
- **FR-022**: The Activities page MUST load events newest first, reading the most recent time window first and widening it only while a page is not full, with the windows counted back from the oldest event shown (or now, on the first page).
- **FR-023**: The Activities page MUST load more events by continuing from the time of the oldest event shown, so that no event is repeated or skipped when new events arrive, keeping events with the same time at a page boundary once.
- **FR-024**: The activity log API MUST compute the total count only when a request asks for it.
- **FR-025**: The Activities page MUST keep not asking for the total count. (The page's query already omits it on `stable` and `develop`; today's cost comes from the server counting regardless, which FR-024 removes.)
- **FR-026**: Activities queries MUST keep their performance when the same query is repeated many times on one connection.

**Guards**

- **FR-027**: An automated check in CI MUST fail when a stored task-manager event type is missing from Infrahub's list.
- **FR-028**: An automated check in CI MUST fail when the command for old runs leaves different runs, logs or artifacts than the task manager's own cleanup on the same data.
- **FR-029**: An automated check in CI MUST fail when a new Activities filter returns different events than today's filter on the same data.

**Documentation**

- **FR-030**: The configuration reference MUST list the three retention settings and their defaults.
- **FR-031**: The upgrade guide MUST state that the upgrade deletes task history older than the retention and cannot be undone, that operators who need older runs set a longer retention before upgrading, the expected duration, the free disk needed for the rewrite, and the Helm maintenance step.
- **FR-032**: The documentation MUST state that lowering a retention frees disk only after running the command for old runs with the rewrite option in a maintenance window, and MUST give sizing guidance for the activity log (5.7 to 8.1 GiB per million stored events).

### Key Entities

- **Run (task history)**: one execution of a background task, with a state, an end time once finished, task runs, logs and artifacts. Finished runs older than the task history retention are deleted.
- **Infrahub event (activity log)**: a change recorded by Infrahub and shown on the Activities page, with related items (account, branch, node, parent event). Kept for the activity log retention.
- **Task-manager event**: an internal event of the task manager (run state changes, heartbeats, worker and deployment events). Never shown; kept for the own-event retention.
- **Retention settings**: the three durations above, owned by the Infrahub configuration.
- **Command for old runs**: the existing operator command, reimplemented to delete like the automatic cleanup, with a rewrite option; also called by the Compose upgrade.

## Success Criteria *(mandatory)*

Timings are indicative: they come from local benchmarks, not a production contract. Every criterion is evidenced by the private performance tests (opsmill/infrahub-private-tests) on restored production-scale backups, on Postgres 14 and 18, before each part ships.

### Measurable Outcomes

- **SC-001**: With a constant workload, the task manager's storage grows by less than 10 % over a second full task history retention period after the upgrade.
- **SC-002**: After a Compose upgrade, the task history storage is no larger than what the runs within the retention need, and the upgrade takes about 8.5 minutes longer per 25 GB of task history.
- **SC-003**: Operators set all retention in one place: 3 settings, zero task-manager-specific variables.
- **SC-004**: With a year of activity log, the Activities default view and the account, branch and node filters load in about 1 s on a repeat load and up to about 3 s on the first load; combined filters load in 3 to 6 s and never more than 10 s.
- **SC-005**: With a year of activity log, sub-activities, branch-name filters and deleted-branch filters load in under 1 s (against 40 s to 5 minutes today).
- **SC-006**: 100 % of Activities filters return the same events as today's filters on the same data.
- **SC-007**: Zero Infrahub events are deleted before the activity log retention, and zero related items are left behind by any cleanup.
- **SC-008**: With the default retentions, the activity log storage after the upgrade stays the size it is today.

## Clarifications

### Session 2026-10-04 (grilling of the design doc)

- Q: Target release? → A: 1.13, not 1.12.
- Q: Is the first upgrade's deletion safe by default? → A: Yes; it cannot be undone, operators who need older runs set a longer retention before upgrading. No skip option, no "keep everything" value.
- Q: How is disk reclaimed after lowering a retention? → A: The existing command for old runs with its rewrite option, in a maintenance window. The same command the upgrade runs. Event storage has no reclaim; lowering is rare.
- Q: Guard against running the rewrite on a live instance? → A: No; operators who run these commands know what they do. The rewrite is off by default.
- Q: Are the behaviour-table timings a contract? → A: No, indicative; 1 or 2 seconds either way is fine.
- Q: What happens to the existing command for old runs? → A: It is reused with the new implementation.
- Q: How do retention settings reach a separate background-services deployment? → A: A thin Infrahub command starts it after applying the same settings.
- Q: Are the SQL cleanup and the new filters checked on task-manager upgrades? → A: Yes, by CI equivalence checks.
- Q: Fallback if product refuses to remove the total count? → A: None; argue for removal. (Later found moot: the page never asked for the count; the design doc dropped D7 and Q2.)
- Q: Values accepted by the settings? → A: Durations of at least 1 day, refuse to start otherwise; an own-event retention longer than the activity log is capped to it with a warning (design doc D5).
- Q: Activity log default? → A: Stays 7 days; a year or more is a capability, not the default.
- Q: Helm upgrade? → A: The pre-upgrade hook does not run the cleanup; a maintenance step after the rollout does.
- Q: Load more by time and time windows? → A: Windows count back from the oldest event shown.
- Q: Auth on the cleanup endpoint? → A: Not added; out of scope.

## Assumptions

- The task manager is the only component that connects to its own database, so the cleanup used by the command for old runs runs inside the task manager.
- The task manager's built-in cleanup of old runs follows the same rules in the pinned version as measured (finished top-level runs by end time, logs and artifacts with their runs).
- Infrahub sets no custom run-state names, so the task manager's state events come only from its built-in states.
- Compose upgrades already stop the instance, so the cleanup adds time to an existing maintenance window.
- Nothing in Infrahub reads runs older than 30 days except to show them; whether customer tooling reads old runs through the task manager's API is unknown and is covered in the release notes.
- Production installs may run a database version OpsMill does not choose, so the Activities queries must work on the oldest supported version (Postgres 14) and later.

## Dependencies & Open Questions

- **Q1 (blocks the release notes)**: how long the upgrade step takes on a large instance. Measured about 8.5 minutes on 25 GB and about 2 h 20 min on 100 GB, almost all of it the deletes; why 100 GB is about 4 times slower per run is not confirmed. Known instances hold about 20 to 35 GB.
- **Deep scrolling by time**: scrolling far down a combined filter, on both supported database versions, is being measured.
- Non-blocking: whether runs accumulate in SCHEDULED, LATE, PAUSED or CANCELLING, and whether runs legitimately stay RUNNING more than 2 days; what happens to Community instances configured above a future Enterprise-only limit.
- **Release evidence**: the private performance tests listed in the design doc (Activities queries, concurrent paging, task history retention, the upgrade step, activity log retention, cleanups under load, database size and dead space) must pass and be attached to each part's PR and to INFP-507; PR #33 in opsmill/infrahub-private-tests lands first.
- Delivery order: part 1 task history (User Story 1), part 2 Activities page (User Story 2), part 3 activity log retention (User Story 3), part 4 documentation with parts 1 and 3. Part 2 lands before part 3.

## Out of Scope

- Tasks page performance at 1M+ runs, latency targets and an Infrahub-owned activity-log store (INFP-727).
- Memory growth from task-manager cache keys that never expire.
- The value of an Enterprise-only retention limit.
- Fixing the command for stuck runs to catch PENDING runs that never started (follow-up).
- New indexes or tables in the task manager's database, a capped total count, and the newest-events shortcut query (rejected in the design doc).
- Upstream task-manager changes (prefix keys in per-type retention, faster per-type cleanup).
- Keeping activity beyond the retention for audit (log forwarding, unchanged).
