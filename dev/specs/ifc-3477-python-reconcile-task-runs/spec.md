# Feature Specification: One branch deletion records the same number of task runs whatever the number of open branches

**Feature Branch**: `python-reconcile-task-runs-ifc-3477`

**Created**: 2026-11-04

**Status**: Draft

**Input**: The PRD in [issue #11165, comment 6470511683](https://github.com/opsmill/infrahub/issues/11165#issuecomment-6470511683), for the bug [#11165](https://github.com/opsmill/infrahub/issues/11165), tracked in Jira as [IFC-3477](https://opsmill.atlassian.net/browse/IFC-3477).

## Problem Statement

Operators who create and delete branches from automation, for example one branch per proposed change in a CI pipeline, have a task manager database that grows with every deletion, by an amount that depends on how many branches are open.

- Every branch deletion and every schema update starts the built-in flow `computed-attribute-setup-python` ([triggers.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/triggers.py#L68-L70)).
- That flow gathers the Python computed attributes of every branch that is not global twice:
  - once to select the attributes to recompute ([tasks.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/tasks.py#L601));
  - once to rebuild the node-input automations, the step this spec calls the reconcile ([tasks.py, reconcile](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/tasks.py#L67-L87), called at [line 665](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/tasks.py#L665)).
- Each gather records one task run per branch that is not global ([gather.py, loop](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/gather.py#L156-L162)). The task run is recorded before the check for a Python computed attribute on the branch ([gather.py, task](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/gather.py#L31-L49)), so instances that define no Python computed attribute record these task runs too.
- On a branch deletion, the flow selects no attribute to recompute ([tasks.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/tasks.py#L635)). The reconcile is its only effect.
- A create, update or delete of a Python transform starts the flow `computed-attribute-process-transform-lifecycle`, which runs the same reconcile ([tasks.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/computed_attribute/tasks.py#L701)).
- The setup flows for HFIDs, display labels and profiles run on the same events, but each gathers every branch inside one task. Only the Python computed-attribute gather records task runs per branch.

The code cited above is the same on `stable` at `5ca7c05db8`, the base of this branch. `develop` at `0152b898be` keeps the per-branch task in the same loop.

Figures from the task manager database dump described in the issue, which covers 47 days and takes 7.2 GB once restored ([analysis, OpsMill access only](https://claude.ai/artifact/Mk9hH8sLXST89KV6Nh32N9)):

- About 4,900 branches were deleted in two days. These deletions started 4,933 runs of `computed-attribute-setup-python`, which recorded 742k task runs: 150 per flow run on average, up to 340.
- Over 47 days, this flow holds 748,308 of 837,273 task runs (89%) and 2.26 M of 2.56 M task-run states (88%).
- Estimated from those shares, the flow takes about 2.8 GB with indexes, close to 40% of the database.
- The Infrahub version that produced the dump is not known. The dump records Prefect 3.7.5.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A branch deletion records a fixed number of task runs (Priority: P1)

An operator's automation deletes one branch. The `computed-attribute-setup-python` run that the deletion starts holds the same number of task runs whether 5 or 500 branches are open. From the code, that number would be 4 (two gather task runs and two trigger-setup task runs), where today it is 4 plus 2 per open branch. The node-input automations after the deletion are the same as today.

**Why this priority**: Branch deletions started 4,933 of the runs in the dump, which recorded 742k task runs in two days. This story alone stops the growth that the issue reports. It also means that an OpsMill support engineer who reads a database dump no longer finds that the number of open branches explains most of its size.

**Independent Test**: Delete one branch out of 2, then one branch out of 10, and compare the number of task runs in the two `computed-attribute-setup-python` runs. Then compare the node-input automations after the deletion with the automations a full reconcile builds.

**Acceptance Scenarios**:

1. **Given** 100 open branches and at least one Python computed attribute, **When** automation deletes one branch, **Then** the `computed-attribute-setup-python` run that the deletion starts holds the same number of task runs as with 5 open branches.
2. **Given** 100 open branches and no Python computed attribute, **When** automation deletes one branch, **Then** the run that the deletion starts holds the same number of task runs as with 5 open branches.
3. **Given** a branch that owns node-input automations, **When** automation deletes that branch, **Then** the automations owned by the deleted branch are removed, and every other automation matches what a full reconcile builds. The default-branch automation stops listing the deleted branch as excluded, as it does today.

---

### User Story 2 - Schema updates and Python transform changes record a fixed number of task runs (Priority: P2)

An operator applies a schema change, or imports a repository that creates, updates or deletes a Python transform. The run that the event starts holds the same number of task runs whatever the number of open branches.

**Why this priority**: These events run the same reconcile, so a change to the shared gather would likely deliver this story together with User Story 1. It has its own test so that its coverage is not assumed.

**Independent Test**: Run the User Story 1 count comparison for a schema update and for each Python transform event.

**Acceptance Scenarios**:

1. **Given** 100 open branches, **When** a schema update is applied, **Then** the `computed-attribute-setup-python` run it starts holds the same number of task runs as with 5 open branches.
2. **Given** 100 open branches, **When** a Python transform is created, updated or deleted, **Then** the `computed-attribute-process-transform-lifecycle` run it starts holds the same number of task runs as with 5 open branches.

---

### User Story 3 - Warnings and errors name the branch they come from (Priority: P3)

Today the name of each per-branch task run, `Gather Python transform attributes for <branch>`, tells the operator which branch a warning or an error comes from. Once these task runs are gone, the operator still needs to find the branch to correct.

**Why this priority**: Without it, removing the per-branch task runs removes the only place where the branch appears next to a missing-transform warning or a gather error.

**Independent Test**: Run the gather with a computed attribute whose transform is missing on one branch, and read the warning. Run the reconcile with a fixture where gathering fails on one branch, and read the error.

**Acceptance Scenarios**:

1. **Given** a Python computed attribute on branch `X` whose transform is not found on `X`, **When** the reconcile runs, **Then** the flow run logs a warning that names branch `X` and the transform.
2. **Given** gathering fails on branch `X`, **When** the reconcile runs, **Then** the flow run fails, and the error in the run's log names branch `X`. The branch appears in the traceback of that error. The run's state message keeps the original error text, which does not always name the branch.

---

### User Story 4 - An operator finds how to remove the rows already written (Priority: P3)

An operator who upgrades an instance whose task manager database has already grown reads the changelog entry for this fix. The entry names `infrahub tasks flush flow-runs` as the way to remove the rows that the previous behavior wrote, and states what that command removes.

**Why this priority**: The fix stops new growth but does not remove existing rows. No migration removes them.

**Independent Test**: Read the changelog fragment and compare each statement with the sources in [Resolved clarifications](#resolved-clarifications).

**Acceptance Scenarios**:

1. **Given** the release notes for this fix, **When** an operator reads the entry, **Then** it names `infrahub tasks flush flow-runs` and states only what the sources confirm about the rows it removes and the disk space it frees.

---

### Edge Cases

- No branch other than `main`: the reconcile gathers `main` only, and FR-001 holds.
- Gathering fails on one branch: the whole reconcile fails, as it does today. The deleted branch's automations stay until the next reconcile succeeds. This spec does not change that.
- A worker's registry still lists the deleted branch: the reconcile gathers it too, as it does today. Whether this logs a missing-transform warning is not known, because the query on that branch can still return the transform from `main`. [#8872](https://github.com/opsmill/infrahub/issues/8872) reports a `KeyError` from this case, and the open pull request [#11095](https://github.com/opsmill/infrahub/pull/11095) handles it. When each worker removes a deleted branch from its registry is not known. This spec does not change it.
- A Python computed attribute wired to its transform by UUID: the gather looks transforms up by name only. It logs the missing-transform warning even though the transform exists, and builds no node-input automation for that attribute, as it does today ([test_transform_lifecycle_recompute.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/tests/component/computed_attribute/test_transform_lifecycle_recompute.py), the `computed_by_id` case). This spec does not change it.
- A burst of deletions: each deletion starts one reconcile with a fixed number of task runs. Combining them is out of scope.
- `infrahub upgrade` runs the flow `trigger-configure-all`, which calls the same gather ([trigger/tasks.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/trigger/tasks.py#L27-L30)). That run also stops recording one task run per branch. This spec sets no separate requirement for it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Infrahub MUST record the same number of task runs in the `computed-attribute-setup-python` run that a branch deletion starts, whatever the number of open branches.
  - Test: delete one of 2 branches, then one of 10 branches, and compare the task-run counts of the two runs.
- **FR-002**: Infrahub MUST leave the same node-input automations in the task manager after a branch deletion as it does today.
  - Test: with a branch that owns automations, compare the automations after the deletion with the automations a full reconcile builds.
- **FR-003**: FR-001 MUST also hold for a schema update, and for a create, update or delete of a Python transform. For a Python transform event, the run is the `computed-attribute-process-transform-lifecycle` run that the event starts.
  - Test: the FR-001 test, run for each of these events.
- **FR-004**: When a computed attribute names a transform that is not found on a branch, Infrahub MUST log a warning in the flow run that names the branch and the transform.
  - Test: assert on the text of the message.
- **FR-005**: When gathering fails on one branch, Infrahub MUST fail the flow run with an error that names the branch.
  - Test: a fixture where gathering fails on one branch.
- **FR-006**: The fix MUST ship with a `fixed` changelog entry that names `infrahub tasks flush flow-runs` as the way to remove the rows already written. Any statement that the entry, the pull request description or the release notes make about what the command removes, or about the disk space it frees, MUST match [Resolved Clarifications](#resolved-clarifications).
  - Test: review of the fragment and the pull request description against the sources.

### Key Entities *(all existing, no new entity)*

- **Branch**: each reconcile gathers every branch that is not global.
- **Python computed attribute**: an attribute whose value comes from a Python transform.
- **Python transform** (`CoreTransformPython`).
- **Node-input automation**: a task manager automation that recomputes a Python computed attribute when a node that its transform's query reads changes ([computed-attributes.md](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/dev/knowledge/backend/computed-attributes.md#node-input-automations)).
  - There is one automation per attribute and one per kind that the query reads.
  - Each automation belongs to one branch. The default-branch automation lists the branches it excludes.
- **Reconcile**: rebuilding the node-input automations from the schema of every branch, under the trigger-registry lock.
- **Flow run and task run**: the records of the task manager database.

The change stores no per-branch result between runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an instance with 75 open branches, 100 branch deletions record at most 5% of the task runs that `computed-attribute-setup-python` records today.
  - Today: about 15,400 task runs, from 100 × (4 + 2 × 75).
  - Target: at most 770.
  - The figure of 75 open branches comes from the dump's average of 150 task runs per flow run.
- **SC-002**: After those 100 deletions, the node-input automations match what a full reconcile builds, with zero missing and zero extra automations.
- **SC-003**: On the same instance, the run that one deletion starts takes no longer than it does today. The speed has not been measured, so this spec sets no speed target.

## Scope Boundaries

### In Scope

- The per-branch gather of Python computed attributes records no task run of its own.
- The missing-transform warning names the branch, and a gather failure on one branch names the branch.
- A `fixed` changelog entry that points to `infrahub tasks flush flow-runs`.
- An update to `dev/knowledge/backend/computed-attributes.md` only if the description of the reconcile changes.

### Out of Scope

- Combining the reconciles of deletions that arrive close together.
- Reducing the graph database reads that one deletion makes. The setup flow keeps gathering twice per run.
- Storing per-branch results between runs.
- A migration that deletes the rows already written.
- Keeping the reconcile going for the other branches when one branch fails.
- Scheduled flows that run every minute ([#11166](https://github.com/opsmill/infrahub/issues/11166)).
- Large flow-run parameters ([#11167](https://github.com/opsmill/infrahub/issues/11167)).
- Correcting the [hardware requirements page](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/docs/docs/deploy-manage/install-configure/hardware-requirements.mdx), which says that "Infrahub periodically prunes old activity logs, so storage usage tends to plateau". The [critique](critiques/critique-2026-11-04.md) lists it as a follow-up.

### Governance Gates

From the "Ask First" lists in `AGENTS.md` and `backend/AGENTS.md`, this change crosses none:

- [ ] Database schema or migration change
- [ ] GraphQL schema modification, new mutation or new query
- [ ] New dependency
- [ ] CI/CD workflow change
- [ ] Authentication or authorization change
- [ ] New database index, core schema definition change or new REST endpoint

## Delivery Order and Open Pull Requests

- Target `stable` first, for a 1.11 patch release, and do not wait for [#11093](https://github.com/opsmill/infrahub/pull/11093) or [#11095](https://github.com/opsmill/infrahub/pull/11095). Rebase onto whichever merges first. Both were open on 2026-11-04.
- `develop` receives the change through the usual merge from `stable` into `develop`. Expect a conflict in `gather.py`, because `develop` changed the grouping logic around the same loop. Remove the per-branch task in that loop too.
- On `develop` at `0152b898be`, two more callers use the per-branch gather. Both need checking during that merge:
  - the merge recompute in `core/merge/python_target_sources.py`, which already runs inside a flow;
  - a test in `tests/component/computed_attribute/test_gather.py`, which calls it outside any flow or task. Once the per-branch gather is no longer a task, that test needs a run context for its logger.
- #11093 changes the first lines of the same flow. Once it merges, the purge after a branch deletion no longer removes the `computed-attribute-setup-python` run that the deletion starts, so that run's rows stay until an operator runs a flush.
- #11095 edits the body of the per-branch gather. Its skip for a branch with no repository commit must stay when the task wrapper goes.

## Resolved Clarifications

The PRD left two questions open. Both concern what the changelog entry (FR-006) can promise. This spec answers them from the sources below.

- **Does deleting a flow run also delete its task runs, task-run states and logs?** Yes, in Prefect 3.7.5, the version the dump records, and in Prefect 3.8.6, the version `stable` pins.
  - The database deletes a flow run's task runs, and each task run's states, through `ON DELETE CASCADE` foreign keys ([orm_models.py at 3.7.5](https://github.com/PrefectHQ/prefect/blob/3.7.5/src/prefect/server/database/orm_models.py)).
  - The log table has no foreign key. The delete endpoint of the Prefect API schedules a background job that deletes the flow run's logs ([api/flow_runs.py at 3.7.5](https://github.com/PrefectHQ/prefect/blob/3.7.5/src/prefect/server/api/flow_runs.py)).
  - `infrahub tasks flush flow-runs` deletes each flow run through that endpoint ([retention.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/task_manager/flow_run/retention.py)). It deletes every flow run, of any flow, that is in a completed, failed or cancelled state and that started more than `--days-to-keep` days ago, 30 by default ([cli/tasks.py](https://github.com/opsmill/infrahub/blob/d83c03b4ebd55fd32b6b6fcbca850e5ef638c108/backend/infrahub/cli/tasks.py#L68-L87)). It does not select the runs of `computed-attribute-setup-python` only.
- **Does the task manager's PostgreSQL database return the disk space after a flush, without `VACUUM FULL`?** No. Vacuuming, including autovacuum, makes the space of deleted rows available to new rows in the same table. It returns space to the operating system only when the pages at the end of a table are empty ([PostgreSQL documentation, Recovering Disk Space](https://www.postgresql.org/docs/current/routine-vacuuming.html#VACUUM-FOR-SPACE-RECOVERY)). `VACUUM FULL` returns the space. It takes an `ACCESS EXCLUSIVE` lock on each table while it processes it. It also needs extra disk space, because it writes a new copy of the table and keeps the old copy until it finishes ([PostgreSQL documentation, VACUUM](https://www.postgresql.org/docs/current/sql-vacuum.html)).

## Assumptions

- It is not known whether any user or support workflow reads the per-branch `Gather Python transform attributes for <branch>` entries. This spec assumes none does.
- The figures come from one dump of an instance whose Infrahub version is not known. The per-branch task is present on `stable` at `d83c03b` and `5ca7c05db8`, and on `develop` at `b2eeb26` and `0152b898be`.
- The fixed number of task runs is read from the code: two calls to the shared gather and two trigger-setup calls per `computed-attribute-setup-python` run. In production, each recompute that a run submits adds one more task run, so a schema update that selects attributes records more than 4. That number depends on the attributes selected, not on the number of branches. The pull request records the count observed on a running instance.
