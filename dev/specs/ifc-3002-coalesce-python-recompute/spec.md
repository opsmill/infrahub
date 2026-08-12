# Feature Specification: Coalesce Python transform computed attributes on merge and rebase

**Feature Branch**: `coalesce-python-recompute-ifc-3002`

**Created**: 2026-08-11

**Status**: Draft (revised after critique)

**Jira**: [IFC-3002](https://opsmill.atlassian.net/browse/IFC-3002) (product idea [INFP-667](https://opsmill.atlassian.net/browse/INFP-667))

**Input**: Coalesce the merge and rebase recompute of Python transform computed attributes so the background work after a merge scales with the number of derived values that changed, not with the number of changed nodes.

## Overview

When a branch is merged or rebased, Python transform computed attributes are still refreshed one changed node at a time. Every changed node starts its own background job. Jinja2 computed attributes, display labels and human-friendly ids do not behave this way: a single coalesced pass replaces their per-node jobs, and their per-node automations ignore merge and rebase events.

Infrahub 1.11 reduced the cost of each Python refresh. It set up the transform repository once per batch, wrote the results in bulk, and stopped emitting an event when a value did not change. It did not reduce how many jobs start. The specification for that work states the limit directly: which nodes enter a batch was out of scope. So the amount of background work still grows with the size of the merge, and the instance stays degraded after the merge call returns.

This feature closes that gap. The merge or rebase works out once which derived values need recomputing, removes duplicates, and submits that set as a bounded number of batches. The stored values must be identical to today, and the number of transform executions must not go up.

### Context and constraints

Six facts shape the solution. They were established by reading the code and by an adversarial review of an earlier draft of this specification, and they are recorded here so the planning step does not rediscover them.

1. **Today's per-node path is already field-scoped on both axes.** The owner-axis automation matches only when a changed field is one the transform's query reads. The reader-axis automation does the same for the kinds it reads. Any coalesced replacement that drops that filter refreshes **more** nodes than today, not fewer, and would make merges slower on the common shape where a merge touches fields no transform reads. Reproducing the field filter is a requirement, not an optimisation.

2. **The reader set is runtime data.** Which nodes read a changed node lives in the query subscriber groups, not in the schema. Resolving it needs a lookup. The three existing families derive their targets from the schema alone and never look anything up, so this is a new kind of step in this pipeline and a new failure mode.

3. **Silencing the per-node automations alone would lose data.** The coalesced pass marks its own writes with a recompute origin so the existing families do not re-trigger themselves. The Python automations carry no origin filter today, and that is precisely why a chain that passes through them still works: a coalesced write still reaches a Python transform that reads it. Adding the filter without also making the coalesced pass aware of Python transforms would leave those chained values stale.

4. **A merge that carries a schema change already triggers a separate all-of-kind refresh.** Left alone, that refresh would run on top of the new coalesced pass. The two passes do not cover the same nodes: the coalesced pass visits only the nodes the merge touched, the schema-driven pass visits every node of the kind. A schema change alters how a value is computed, so it invalidates untouched nodes as well. The duplicate must therefore be removed from the coalesced pass, never from the schema-driven one.

5. **The reader refresh does not survive a delete today.** The reader-side automation listens for node updates only. It has no delete leg, so a deleted node never starts a reader refresh, on a merge or on a live edit. Even if it did fire, the membership record that identifies the readers is already closed by the time the lookup runs. This is a pre-existing gap with two independent causes.

6. **Submissions are chunked, so the job count is a step function, not a constant.** A coalesced pass splits each target's node ids into chunks bounded by the task-orchestration parameter limit. The win is that the count stops being one job per changed node, not that it becomes one job.

### Non-negotiable invariant

Over-recompute is acceptable. Under-recompute is not. A value that should refresh but does not leaves stale data in production. Every fallback and error path must default toward recomputing. [IFC-2937](https://opsmill.atlassian.net/browse/IFC-2937) is the cautionary case.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A large merge stops flooding the instance (Priority: P1)

An operator merges or rebases a branch that changed many nodes tied to a Python transform computed attribute. Today each changed node starts its own background job, and the instance stays slow until they all drain. After this change the refresh runs as a small bounded number of batches, the instance returns to normal quickly, and every affected value is the same as it would have been before.

**Why this priority**: This is the reported pain and the reason the feature exists.

**Independent Test**: Merge a branch that changes a known number of nodes tied to a Python transform computed attribute. Count the background jobs created and the transform executions, and measure how long background activity lasts. Compare the resulting attribute values against the same merge on the current behaviour.

**Acceptance Scenarios**:

1. **Given** a branch that changes many nodes which own a Python transform computed attribute, **When** the branch is merged, **Then** no background job is created for an individual node, and each node's attribute holds the value the per-node refresh would have produced.
2. **Given** a branch that changes many nodes read by a Python transform's query, **When** the branch is merged, **Then** no background job is created for an individual node, and every reader of those nodes holds the refreshed value.
3. **Given** either of the above branches, **When** the branch is rebased instead of merged, **Then** the same two outcomes hold on the rebased branch.
4. **Given** a merge that changes only fields no transform's query reads, **When** the merge completes, **Then** no transform is executed at all, matching today's behaviour.
5. **Given** a merge whose change refreshes a template-based derived value that a Python transform then reads, **When** the merge completes, **Then** the Python-derived value reflects the refreshed upstream value.
6. **Given** a merge whose change refreshes a Python-derived value that a template-based derived value then reads, **When** the merge completes, **Then** the template-based value reflects the refreshed upstream value.
7. **Given** a schema whose derived values form a cycle, **When** a merge triggers the chain, **Then** the chain stops at a bounded depth and the operator gets a warning naming the values left unrefreshed.
8. **Given** a Python transform whose affected readers cannot be determined, **When** a merge touches it, **Then** every node of that attribute's kind is refreshed for that attribute only, other attributes stay narrowly scoped, and the widening is recorded.
9. **Given** the reader lookup fails outright, **When** the merge completes, **Then** the affected pairs are widened rather than skipped, and the other derived-value families are still refreshed.
10. **Given** a merge that adds the first Python transform computed attribute to the schema, **When** the merge completes, **Then** the refresh runs, rather than being skipped because a worker had not yet seen the new schema.
11. **Given** the same merge run against the current behaviour and against the coalesced behaviour, **When** both settle, **Then** the set of nodes written and their final values are identical, and the coalesced run executes no more transforms than the current one.
12. **Given** an operator edits a node directly on a branch rather than merging, **When** the edit is saved, **Then** the Python transform computed attribute refreshes as it does today, and any derived value that reads it refreshes in turn.

---

### User Story 2 - A deleted peer refreshes its readers (Priority: P2)

An operator merges a branch that deletes a node other objects read. Today the readers keep a value that names the deleted object. After this change they refresh.

**Why this priority**: It is a correctness bug rather than a performance one, and it is independently valuable: the same gap affects a plain delete outside any merge, so fixing it improves normal use. It is separated from P1 because it can be built, tested and demonstrated on its own, and because P1 must not be blocked on it.

**Independent Test**: Delete a node that a Python transform reads, once through a merge and once directly, and check the readers.

**Acceptance Scenarios**:

1. **Given** a merge that deletes a node read by a Python transform, **When** the merge completes, **Then** the readers of that node are refreshed.
2. **Given** a direct delete of the same node outside any merge, **When** the delete completes, **Then** the readers are refreshed.
3. **Given** a merge that both deletes one node and updates another, **When** the merge completes, **Then** the readers of both are refreshed, and the update path is resolved against current data rather than against the pre-delete state.

---

### User Story 3 - A merge that also changes the schema does not refresh twice (Priority: P3)

An operator merges a branch that carries both schema edits and data changes. The schema edit already triggers a full refresh of the affected computed attributes, covering every node of the kind. Both would otherwise run and compute the same values twice for the nodes the merge touched. After this change the operator pays for that overlap once, and the wider schema-driven refresh is left untouched.

**Why this priority**: It is a real waste, and on a schema-carrying merge it would cancel out the P1 gain for the overlapping pairs. P1 delivers the win on the common data-only merge without it.

**Independent Test**: Merge a branch containing both a schema change and data changes to nodes with Python transform computed attributes. Count how many times each affected attribute-and-kind pair is refreshed, and confirm nodes the merge did not touch are still refreshed.

**Acceptance Scenarios**:

1. **Given** a merge carrying both a schema change and data changes to the same attribute-and-kind pair, **When** the merge completes, **Then** the nodes the merge touched are refreshed once rather than twice.
2. **Given** a merge whose schema change alters how an attribute is computed, **When** the merge completes, **Then** nodes of that kind which the merge did not touch are also refreshed and hold the new value.
3. **Given** a merge whose data change touches a pair the schema change does not affect, **When** the merge completes, **Then** that pair is still refreshed for the touched nodes.
4. **Given** a merge where the schema-driven refresh cannot be started or does not finish, **When** the merge completes, **Then** the merge-driven refresh still covers every node the merge touched.
5. **Given** the same merge, **When** the schema-driven path runs, **Then** it still reconciles the per-node automations for the changed schema.

---

### User Story 4 - An operator can see and control what happened (Priority: P4)

An operator looking at a slow or suspicious merge can tell from the task logs which computed attributes the refresh selected and which were widened. If the new behaviour misbehaves, they can turn it off without a release.

**Why this priority**: It changes no refresh behaviour, so it ships last. It is the feature's only user-visible surface, and the switch is the only rollback an operator has at three in the morning.

**Independent Test**: Run a merge mixing a narrowly scoped attribute with one whose readers cannot be determined, read the logs, then set the switch off and confirm the previous behaviour returns.

**Acceptance Scenarios**:

1. **Given** a merge that refreshes Python transform computed attributes, **When** the operator reads the task logs, **Then** a summary names the attribute-and-kind pairs selected and how many nodes each covers.
2. **Given** a merge where an attribute was widened to its whole kind, **When** the operator reads the task logs at a diagnostic level, **Then** the widened attribute and the reason are both recorded.
3. **Given** the feature switch is turned off, **When** a branch is merged, **Then** the per-node behaviour that exists today returns exactly, with no coalesced pass and no suppressed automations.

---

### Edge Cases

- A transform's query cannot be analysed precisely, so its read fields or readers cannot be derived. The attribute widens to its whole kind and nothing else widens with it.
- The reader lookup fails or times out during the merge. The failure must widen, and it must not prevent the other three derived-value families from refreshing.
- A merge deletes a node that Python transforms read. Covered by User Story 2.
- A merge adds the first Python computed attribute to the schema, so a worker may not have it yet.
- The derived-value dependency graph contains a cycle. The refresh must stop at a bounded depth and say what it left undone.
- A merge changes nodes of a kind that owns a Python computed attribute, but touches only fields the transform does not read. Nothing is executed.
- A merge is very large. The node ids cannot all be carried in one job submission.
- A refresh produces the same value it already had. No downstream work follows, as today.

## Requirements *(mandatory)*

### Functional Requirements

**Coalescing and suppression**

- **FR-001**: On a merge, the system MUST NOT start a separate background refresh for each changed node that owns a Python transform computed attribute.
- **FR-002**: On a merge, the system MUST NOT start a separate background refresh for each changed node that a Python transform's query reads.
- **FR-003**: On a rebase, the system MUST behave as FR-001 and FR-002 require for a merge.
- **FR-004**: The coalesced refresh MUST select nodes using the same read-field scoping the per-node automations apply today, on both the owner axis and the reader axis.
- **FR-005**: The coalesced refresh MUST NOT execute more transforms, nor write more nodes, than the per-node refresh would have, except where a widening is recorded under FR-009.
- **FR-006**: For a given merge, the set of nodes written and their final stored values MUST be identical to what the per-node refresh produces.
- **FR-007**: A derived value that a Python transform computed attribute depends on, or that depends on one, MUST reach its correct final value through the coalesced refresh.
- **FR-008**: The refresh chain MUST stop at a bounded depth that accounts for every family of derived value, including Python transform computed attributes, and MUST record which values it left unrefreshed when it stops.

**Failing safely**

- **FR-009**: When the affected readers or read fields of a Python transform computed attribute cannot be determined, the system MUST refresh every node of that attribute's kind for that attribute alone, and MUST NOT widen any other attribute as a result.
- **FR-010**: A widened refresh MUST actually be dispatched. It MUST NOT be representable in a way that silently produces no work.
- **FR-011**: A failure while resolving readers MUST widen the affected pairs and MUST NOT prevent the other derived-value families from being refreshed.
- **FR-012**: Before concluding that a branch has no Python transform computed attribute to refresh, the system MUST confirm it is reading a converged schema.
- **FR-013**: Refreshes triggered by ordinary user edits MUST keep their current behaviour, including the chaining that follows a live write. Whether a refresh is coalesced MUST be stated explicitly by its caller, not inferred from the shape of its arguments.

**Deleted peers**

- **FR-014**: A delete MUST start a refresh of the deleted node's readers, whether the delete arrives through a merge or through a direct edit.
- **FR-015**: The readers of a deleted node MUST remain identifiable after the delete has closed the membership records. Resolution against an earlier point in time MUST apply only to deleted nodes, so that memberships the merge itself created are not hidden from the other cases.

**Merge that carries a schema change**

- **FR-016**: When a schema change causes an attribute-and-kind pair to be refreshed across every node of its kind, the merge-driven refresh MUST NOT also refresh the nodes it touched for that pair.
- **FR-017**: The schema-driven refresh MUST NOT be narrowed or skipped because a merge-driven refresh covered part of its node set. It MUST keep refreshing every node of the kind, and it MUST keep reconciling the per-node automations for the changed schema.
- **FR-018**: If the schema-driven refresh cannot be started, or does not finish, the merge-driven refresh MUST still cover every node the merge touched.

**Observability and control**

- **FR-019**: The system MUST record, at a level an operator normally sees, which attribute-and-kind pairs the refresh selected and how many nodes each covers.
- **FR-020**: The system MUST record, at a diagnostic level, every widening together with the attribute it affected and the reason.
- **FR-021**: A single feature switch MUST turn the new behaviour off, restoring today's per-node behaviour exactly. It MUST default to on.

### Key Entities

No new persisted entity. The feature adds one derived-value family and reuses the existing change set, affected target, reader lookup, mutation origin and query subscriber group concepts.

One new in-memory concept: the **read-field index**, mapping each Python computed attribute to the kinds and fields its transform's query reads. It is what makes FR-004 possible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a merge changing N nodes tied to Python transform computed attributes, the number of background jobs created per affected attribute-and-kind pair is at most the number of chunks the submission limit requires, instead of one per changed node. Measured at 100, 1000 and 2000 changed nodes.
- **SC-002**: At 1000 changed nodes, the background activity that follows the merge settles at least 90% sooner than the measured baseline for the current behaviour.
- **SC-003**: For the same merge, the set of nodes written and their final values are identical between the current behaviour and the coalesced behaviour, at every measured scale.
- **SC-004**: The number of transform executions for the same merge is no higher than the current behaviour, at every measured scale.
- **SC-005**: Throughout the background window that follows the merge, the API answers every request without an error and without a timeout.
- **SC-006**: For any merge that refreshes Python transform computed attributes, an operator can determine from the task logs alone which attributes were refreshed and which were widened, without reading the source.
- **SC-007 (fail criterion)**: If, at 1000 changed nodes, the transform execution count exceeds the current behaviour, or the background window improves by less than 50%, the suppression is reverted and the feature is reconsidered rather than shipped.

The baseline does not exist yet. Measuring it is the first task, and the numbers above are meaningless until it does.

## Assumptions

- **The baseline must be measured before anything is built, and the tool to measure it does not exist here.** The timing harness from the earlier merge recompute profiling was never merged; it survives only on an unmerged branch, and the one helper that did land measures the three existing families only. Restoring it, pointing it at the Python jobs, and giving it a dataset with a real transform repository are all prerequisites of SC-002 and SC-007.
- **The measurement needs no private dataset.** The harness seeds its own synthetic data at a chosen scale. Larger reference figures quoted by earlier work live in a separate private repository and are not reproducible here.
- **The batching work already in place stays as it is.** One repository setup per batch, bulk writes and the skip-unchanged gate are all kept. This feature changes which nodes enter a batch, not how a batch is processed.
- **The existing per-submission size limit continues to bound a batch.** SC-001 is expressed in terms of it rather than assuming it away.
- **Origin labelling stays as it is.** The four origins and their meanings do not change.
- **No schema change, no migration, no API contract change.** The feature rewires background dispatch and adds one feature switch.

## Out of Scope

- Narrowing the refreshed set below the precision the per-node path achieves today.
- The profile-refresh family, still deferred from the earlier coalescing work.
- User action rules and webhooks. They keep receiving every event, whatever its origin.
- Combining the merge regeneration path for generators and artifacts with the coalesced recompute path into one mechanism.
- Replacing the client-based reader lookup with a database-direct one.
- A recovery workflow for nodes whose refresh failed.
- Refreshing derived values after an upgrade, tracked separately as [IFC-2887](https://opsmill.atlassian.net/browse/IFC-2887).

## Dependencies

- The batched Python recompute shipped in 1.11 ([#10034](https://github.com/opsmill/infrahub/pull/10034)).
- The coalesced merge and rebase recompute for the three existing families ([IFC-2705](https://opsmill.atlassian.net/browse/IFC-2705)).
- A restored timing harness, for the baseline. [IFC-2746](https://opsmill.atlassian.net/browse/IFC-2746) is the related benchmark item and has no work in flight.
