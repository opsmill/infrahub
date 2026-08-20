# Feature Specification: Batch Python Computed-Attribute Recompute

**Feature Branch**: `batch-python-recompute-infp-608`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Optimize the recompute of Python-transform computed attributes so a change affecting many nodes no longer overwhelms the instance. Today (develop), when a source change fans out to N reader nodes, the per-node path initializes the transform's git repository once per node, issues one update mutation per node, and every mutation's events re-trigger target queries and further recompute dispatches (an echo storm measured at 73k flow runs for one device-type rename on a large dataset, ending in resource exhaustion). Goal: initialize the repo once per batch, collect the recomputed values, persist them through the existing shared bulk recompute writer, isolate per-node transform failures, and keep the process flow runs visible in branch-filtered task queries."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instance stays usable after a wide-impact change (Priority: P1)

A network operator renames a device type's part number (directly or by merging a branch). That single change invalidates a Python-computed description on every device of that type — potentially thousands of nodes. Today the resulting background refresh floods the system with follow-on work that grows with the number of affected nodes, keeping the instance degraded for minutes to hours and, at large scale, exhausting server resources until the API stops responding. After this feature, the same change is absorbed as one bounded background pass: the instance stays responsive throughout, and the refresh settles promptly.

**Why this priority**: This is the customer-reported pain ("every merge recomputes everything → instance unusable for ~20 minutes to an hour"). Removing the self-amplifying churn is the core value; everything else in this feature supports it.

**Independent Test**: On a restored production-scale dataset, rename one device type and measure (a) time from the change until background activity settles, (b) the number of background task runs spawned, (c) API availability during the window. Compare against the same operation before the change.

**Acceptance Scenarios**:

1. **Given** a dataset where one device type is used by N devices, **When** the device type's part number is renamed, **Then** every affected device's computed description reflects the new value once background processing settles.
2. **Given** the same rename, **When** background processing runs, **Then** the number of background task runs is bounded by the fan-out size (no per-node write tasks, no self-retriggered follow-on waves), and the API remains available throughout.
3. **Given** a branch containing the rename, **When** the branch is merged, **Then** the post-merge refresh behaves identically to scenarios 1–2 on the destination branch.

---

### User Story 2 - Unchanged values cause no follow-on work (Priority: P2)

Many recompute passes produce a value identical to what is already stored (e.g. a re-sync or a change that does not alter the rendered text). An operator whose change leaves most computed values untouched should not pay for update events or cascading refreshes on those untouched nodes.

**Why this priority**: The echo storm is fed by no-op writes emitting events that re-trigger the recompute machinery. Suppressing no-op propagation is what converts an unbounded cascade into a single pass.

**Independent Test**: Recompute a set of nodes twice in a row; the second pass must produce zero update events and zero follow-on recompute dispatches.

**Acceptance Scenarios**:

1. **Given** a node whose recomputed value equals the stored value, **When** the batch is persisted, **Then** no update event is emitted for that node and no downstream refresh is dispatched for it.
2. **Given** a node whose recomputed value differs, **When** the batch is persisted, **Then** exactly the same per-node update event is emitted as an equivalent direct edit of that attribute would emit today.

---

### User Story 3 - One broken transform target does not block the rest (Priority: P3)

A user's transform code can fail for a specific node (raise an exception, or return a value of the wrong type) — for example, one device has missing related data. The operator expects every other node in the batch to still be refreshed, with the failing node keeping its previous value and the failure being discoverable in logs.

**Why this priority**: With batched persistence, a naive implementation would let one bad node abort the whole batch — a regression from today's per-node behavior. Isolation preserves partial progress.

**Independent Test**: Point a computed attribute at a transform that fails for exactly one node out of many; verify the others update and the failing node retains its prior value with a logged reason.

**Acceptance Scenarios**:

1. **Given** a batch of N nodes where one node's transform raises, **When** the batch runs, **Then** N−1 nodes are updated, the failing node's previous value is preserved, and the failure and its reason are logged.
2. **Given** a transform that returns a non-text value for one node, **When** the batch runs, **Then** that node is skipped exactly as in scenario 1 (no null/garbage value is written).

---

### User Story 4 - Operators can still see recompute activity per branch (Priority: P4)

An operator investigating "did my change refresh the computed values on branch X?" filters the task list by branch. The recompute's processing runs must appear there, both while running and after completion.

**Why this priority**: Batching replaces many visible per-node tasks with fewer batch runs; if those batch runs are not visible in branch-filtered queries, operators lose their only progress/audit surface for recompute.

**Independent Test**: Trigger a recompute on a branch and query the task list filtered by that branch; the processing run(s) must be listed.

**Acceptance Scenarios**:

1. **Given** a recompute triggered on branch B, **When** the task list is filtered by branch B, **Then** the recompute processing run(s) appear with their state and completion.

---

### Edge Cases

- Transform raises for every node in the batch → all nodes keep prior values, all failures logged, flow completes without writing.
- Transform returns a non-text value (None, number, object) for some nodes → those nodes are skipped with a logged reason; text values persist unchanged semantics.
- A node in the batch is deleted between fan-out and persistence → the write pass skips it without failing the batch.
- The branch is deleted between fan-out and persistence → the batch is abandoned without error.
- The fan-out exceeds the per-submission size limit → the work is split into multiple bounded batch runs, every affected node processed exactly once.
- The recomputed value equals the stored value for all nodes (full no-op pass) → zero events, zero follow-on dispatches.
- The transform's source repository is unavailable at batch start → the batch fails visibly before touching any node (no partial ambiguity from per-node repository setup).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST prepare the transform's execution source (repository checkout) once per batch of affected nodes, not once per node.
- **FR-002**: The system MUST persist the recomputed values of a batch through the existing shared bulk recompute write path (bounded write transactions), not via one client-visible update operation per node.
- **FR-003**: A persisted value identical to the stored value MUST NOT emit an update event and MUST NOT trigger any downstream recompute dispatch.
- **FR-004**: A persisted value that differs from the stored value MUST emit the same per-node update event an equivalent direct attribute update emits, so downstream consumers (webhooks, UI, dependent computed values) observe no behavioral change.
- **FR-005**: A node whose transform raises or returns a non-text value MUST be skipped — previous value preserved, reason logged — without affecting the persistence of other nodes in the batch.
- **FR-006**: Batch processing runs MUST remain discoverable via branch-filtered task queries, during and after execution.
- **FR-007**: The per-node data reads performed by the recompute MUST keep registering each node as a subscriber of the transform's query (the reverse-index that routes future source changes to affected readers must stay current).
- **FR-008**: Fan-outs larger than the existing per-submission size limit MUST be split into multiple bounded batches, with every affected node processed exactly once across batches.
- **FR-009**: The final stored values after a batch recompute MUST be identical to what today's per-node path produces for the same inputs (correctness parity).

### Key Entities

- **Computed attribute (Python transform)**: a read-only attribute whose value is produced by user-supplied transform code reading the node's own data via a named query.
- **Recompute batch**: the set of affected node ids processed by one background run — reads and transform executions per node, one shared persistence pass.
- **Skipped node**: a batch member whose transform failed; retains its prior value, recorded with a reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the reference small dataset, post-merge background processing settles in under 10 seconds (previously ~4.6 minutes); on the reference large dataset, the same operation settles without API unavailability (previously never settled and took the instance down).
- **SC-002**: Total background task runs spawned by one source change drop by ≥ 99% at scale (reference: 73,000+ runs for one rename on the large dataset → bounded by ⌈N / submission-limit⌉ plus a constant).
- **SC-003**: Final computed values are byte-identical to the previous behavior for the same inputs (100% correctness parity on the reference scenarios).
- **SC-004**: The API remains available (no sustained error responses attributable to the recompute) throughout the refresh on the large reference dataset, where previously the instance became unresponsive.
- **SC-005**: With one failing node in a batch of N, N−1 nodes are refreshed and the failure is discoverable in logs (no silent data loss, no batch abort).

## Assumptions

- The existing shared bulk recompute writer (used by the template-based computed attributes) is the persistence mechanism to reuse; it already provides bounded transactions, skip-unchanged gating, and per-node update events for real changes.
- The existing per-submission size limit (derived from the task-orchestration platform's parameter cap) continues to bound batch size; this feature does not introduce a new limit.
- Which nodes are affected by a change (fan-out scoping, all-of-kind vs affected-only) is explicitly out of scope — this feature changes how a batch is processed, not which nodes enter it.
- Per-node update events for real changes are retained at the same granularity; consumers of those events are unaffected.
- Transform code is user-supplied and opaque: per-node execution cannot be merged or vectorized; only setup and persistence around it can be shared.
- Failure recovery/retry UX for skipped nodes (discovery surface, one-click re-run) is a separate follow-up effort, not part of this feature.
