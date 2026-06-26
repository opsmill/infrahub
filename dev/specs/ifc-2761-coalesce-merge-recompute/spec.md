# Feature Specification: Coalesce merge and rebase recompute fan-out

**Feature Branch**: `coalesce-merge-recompute-ifc-2761`
**Created**: 2026-06-25
**Status**: Draft
**Jira**: [IFC-2761](https://opsmill.atlassian.net/browse/IFC-2761) (the coalescing redesign, the work after the profile) · epic [INFP-608](https://opsmill.atlassian.net/browse/INFP-608)
**Input**: Coalesce the merge and rebase recompute fan-out so recompute work after a merge or rebase scales with the number of affected derived values, not with the changed-node count times automations.

## Overview

When a branch is merged or rebased, every changed node currently sends its own recompute work to the background engine, and each piece is matched against the per-node automations on its own. The profile of this path (the first task on IFC-2761, see [findings](../ifc-2761-merge-recompute-profile/findings.md)) showed that the cost that grows with scale is this background recompute that runs after the merge returns, not the merge call itself. It is linear in the size of the change (about 2000 recompute jobs and an 11 minute trailing window for 1000 changed nodes), and it leaves the instance degraded for that whole window. The merge call itself is fixed overhead.

This feature replaces the per-node fan-out on the merge and rebase path with a single coalesced recompute. The merge looks at the whole change it is about to apply, works out once the set of derived values that actually need recomputing, removes duplicates, and submits that set as one batch. The result is the same stored values as today, reached with far less work, so the instance returns to normal sooner after a large merge.

This is a behavior-preserving performance change. The derived values an instance ends up with must be identical; only the amount of background work to get there changes.

## Clarifications

### Session 2026-06-25

- Q: Which derived-value families should the coalesced recompute cover in this work? → A: Jinja2 computed attributes, display labels, and human-friendly ids in this increment; Python-transform computed attributes are a follow-up using the same approach.
- Q: How should the coalesced pass handle nodes that read a node deleted by the merge? → A: Recompute readers of deleted nodes so their derived values are refreshed or cleared.
- Q: How precise must the recompute targeting be? → A: Precise wherever the dependency derivation supports it; a bounded, logged safe over-approximation only where precise derivation is genuinely unavailable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast return to service after a large merge (Priority: P1)

An operator merges a large branch. Today the instance is slow or unusable for a long window while the per-node recompute drains. After this change the recompute that runs after the merge is proportional to the number of derived values that actually changed, so the window is much shorter.

**Why this priority**: This is the reported pain (long unusable window after big merges) and the reason the epic exists. It is the headline outcome.

**Independent Test**: Run the profiling harness at the large scale before and after the change. The number of recompute jobs and the trailing recompute window must drop substantially while the merged data ends up identical.

**Acceptance Scenarios**:

1. **Given** a branch that changes a large number of nodes that other nodes read, **When** it is merged, **Then** the count of recompute jobs after the merge is bounded by the number of affected derived values, not by the changed-node count times the number of automations.
2. **Given** the same merge, **When** the recompute finishes, **Then** the trailing recompute window is materially shorter than the profile baseline for the same change size.

### User Story 2 - No stale derived values after a merge or rebase (Priority: P1)

An engineer needs every derived value that depends on a merged change to be correct afterwards. Cutting recompute work must not skip a value that should have been recomputed.

**Why this priority**: This is the main risk of the change. A missed dependency leaves a wrong stored value after a merge, which is worse than doing extra work. Correctness gates the performance win.

**Independent Test**: After a merge or rebase, compare every computed attribute, display label, and human-friendly id on affected nodes against a from-scratch recompute. They must match, including values that depend on a changed node through a relationship.

**Acceptance Scenarios**:

1. **Given** a merge that changes a node other nodes read, **When** the merge completes, **Then** every reader's affected derived values match a full recompute and none are left at their old value.
2. **Given** a merge that creates nodes, **When** the merge completes, **Then** every new node's derived values are computed, including the human-friendly id.
3. **Given** a chain of dependencies (a value that reads a node that reads the changed node), **When** the merge completes, **Then** the whole chain is consistent.

### User Story 3 - Same improvement for rebase (Priority: P2)

Rebase carries the same per-node fan-out as merge and must get the same coalesced recompute, so a rebase of a long-lived branch does not reintroduce the slow window.

**Why this priority**: Rebase shares the mechanism and the cost. Leaving it on the old path would be an inconsistent and surprising gap.

**Independent Test**: Run the harness for a rebase at scale and confirm the same reduction in recompute jobs and window as for merge, with correct values.

**Acceptance Scenarios**:

1. **Given** a branch that is behind the default branch, **When** it is rebased, **Then** the recompute after the rebase is coalesced and the values are correct.

### User Story 4 - No regression for small changes (Priority: P3)

Most merges are small. The coalescing must not make small merges slower or add noticeable fixed overhead.

**Why this priority**: A change that helps large merges but taxes the common small case would be a poor trade. It must be at least neutral for small changes.

**Independent Test**: Run the harness at the small scale before and after; the small-merge recompute must be no slower within run-to-run tolerance.

**Acceptance Scenarios**:

1. **Given** a merge that changes a handful of nodes, **When** it is merged, **Then** the recompute time is no worse than the current behavior within tolerance.

### Edge Cases

- A single merge that both creates nodes and changes read-targets: both triggers must be handled in one coalesced pass.
- One changed node read by many nodes: each reader's affected families recompute, with no duplicate jobs for the same target.
- A derived value that reads only local fields (for example a human-friendly id built from the node's own name): it must recompute when its node is created but not when a related node it does not read changes.
- A node deleted by the merge: nodes that read the deleted node MUST be recomputed by the coalesced pass so their derived values are refreshed or cleared.
- The merge data-change path and the coalesced pass must not both process the same change (no double recompute).
- A merge that also changes the schema: schema-driven recompute (migrations) is a separate path and is out of scope here.
- Two merges close together: each merge's coalesced recompute must cover its own change and not drop work when they overlap.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A merge MUST recompute every derived value whose inputs were changed by the merge, across Jinja2 computed attributes, display labels, and human-friendly ids. Python-transform computed attributes are a follow-up increment using the same coalescing approach and are out of scope here.
- **FR-002**: A merge MUST NOT leave any such derived value stale. The stored value after the merge MUST equal a from-scratch recompute. Over-recompute is acceptable; under-recompute is not.
- **FR-003**: The recompute after a merge MUST be coalesced and deduplicated, so the same derived target is recomputed at most once even when several changed nodes affect it.
- **FR-004**: The amount of recompute work after a merge MUST scale with the number of affected derived values, not with the changed-node count multiplied by the number of matching automations.
- **FR-005**: The recompute MUST handle both change triggers and respect their per-family read scope: a change to a node that other nodes read recomputes each reader's families that read across the relationship; a node creation recomputes all of the new node's families. A family that reads only local fields MUST NOT be recomputed because a related node changed.
- **FR-006**: A branch rebase MUST use the same coalesced recompute as a merge.
- **FR-007**: The selection of affected derived values MUST NOT diverge from the live per-node recompute path. The computed-attribute deriver already exists and MUST be reused. No shared display-label or human-friendly-id deriver exists, so those MUST be built here following the same pattern, reading the dependency metadata already recorded on the display-label and HFID definitions, not as a parallel implementation.
- **FR-008**: The merge and rebase path MUST NOT both coalesce-recompute and per-node fan-out the same change.
- **FR-009**: The work MUST NOT make small merges slower than the current behavior beyond run-to-run tolerance.
- **FR-010**: The change MUST be behavior-preserving: the final derived values MUST be identical to the current behavior; only the work to reach them changes.
- **FR-011**: The improvement MUST be demonstrated with the profiling harness from the first task, before and after, at small, medium, and large scale.
- **FR-012**: Recompute targeting MUST be precise wherever the dependency derivation supports it. Where precise derivation is genuinely unavailable, a bounded, logged safe over-approximation (for example, all nodes of an affected kind) is permitted rather than risking under-recompute.
- **FR-013**: Nodes that read a node deleted by the merge MUST be included in the coalesced recompute, so their derived values no longer reflect the deleted node.
- **FR-014**: The coalesced recompute MUST run on the correct branch per operation: a merge recomputes on the destination branch, a rebase on the user branch. This difference MUST be preserved.
- **FR-015**: The coalesced recompute MUST cover readers that exist only on the destination branch (never touched by recompute on the source branch). Skipping readers already recomputed on the source branch and merged in is a permitted optimization only where proven safe; the default is to recompute, and under-recompute is never acceptable.

### Key Entities *(include if feature involves data)*

- **Merge change set**: the set of changes a merge or rebase is applying, described as changed nodes with their changed fields, created nodes, and deleted nodes.
- **Affected derived value**: a computed attribute, display label, or human-friendly id whose inputs are in the merge change set, either on the changed node itself (creation) or on a node that reads it (cross-node).
- **Coalesced recompute set**: the deduplicated union of affected derived values that the merge submits as one batch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At the large profile scenario (about 1000 changed read-targets), the number of recompute jobs after a merge is bounded by the number of affected derived values and is materially lower than the per-node fan-out baseline recorded by the profile.
- **SC-002**: At the large profile scenario, the trailing recompute window (from merge completion to all derived values settled) is reduced by a large margin versus the profile baseline (baseline about 11 minutes for 1000 changed nodes).
- **SC-003**: After a merge or rebase, no derived value that depends on the merged change is stale, verified against a full recompute, including cross-relationship and transitive dependencies, node creations, and readers of deleted nodes.
- **SC-004**: Small-graph merges (about 10 changed nodes) are no slower than the baseline within run-to-run tolerance.
- **SC-005**: Both merge and rebase show the reduction and the correctness guarantee.

## Assumptions

- The computed-attribute dependency deriver already exists (the scoping work in PR #9467) and is reused. No shared display-label or human-friendly-id deriver exists: IFC-2759 closed as not applicable, because those families are scoped on the schema-update path by trigger-modification detection, so none was built. The display-label and HFID derivation MUST therefore be built here, following the computed-attribute pattern and reading the dependency metadata already recorded on the display-label and HFID definitions, so it cannot drift from the live per-node path.
- Coordinate with IFC-2758 (the complementary correctness gap: merge emits no schema-updated event, so definition-only schema changes do not refresh nodes absent from the source branch) to avoid double processing.
- This spec branch is based on the profile branch (older code). On current develop the merge emits its node events from `core/merge/post_merge.py` and rebase emits inline in `core/branch/tasks.py`; the branch MUST be rebased onto current develop before implementation so the integration targets the real emission points.
- Optional related fix: on current develop the full-branch Jinja2 recompute loop submits one workflow per node without chunking (unlike the Python and transform paths); it may be chunked while this work is in the same area.
- Same-node updates already recompute inline during the save and are unchanged by this work; the target is the asynchronous cross-node and creation fan-out.
- Schema-changing merges (migrations) are out of scope. This work targets data-change recompute. The profile kept migration cost separate.
- Background task scheduling and throughput tuning (tracked separately) are out of scope here; this work reduces how much recompute is submitted, not how it is scheduled.
- A configurable per-instance recompute policy is out of scope for this work.
- The profiling harness from the first task (on the `merge-recompute-profile-ifc-2761` branch) is the before/after measurement tool and is available to this work.
- Python-transform computed attributes are deferred to a follow-up increment that reuses the same coalescing approach; this increment covers Jinja2 computed attributes, display labels, and human-friendly ids.
- Readers of a node deleted by the merge are recomputed by the coalesced pass so their derived values no longer reflect the deleted node.
- Absolute timings are stack-relative; the success criteria are judged on the growth shape and the relative reduction against the profile baseline, not on fixed second counts.
