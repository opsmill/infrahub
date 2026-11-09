# Feature Specification: Priority Inheritance for Task Trees

**Feature Branch**: `priority-work-queues-ifc-2859`

**Created**: 2026-07-04

**Status**: Draft

**Input**: Idea brief "Priority Inheritance via InfrahubContext" (grilling session of 2026-07-04) — follow-up slice to IFC-2859 "Priority Work Queue Foundation" under INFP-635, implemented on the same branch as a second spec.

## Problem Statement

The priority work queue foundation (first IFC-2859 slice) gives every workflow a default priority lane and a dispatch-time override. But priority currently stops at the root of a task tree: when an expedited workflow dispatches sub-workflows (diff refresh, artifact generation, git sync), each sub-workflow falls back to its own catalogue default and queues behind the backlog. Under load, the root flow runs immediately and then waits on its own children — the expedition is invisible end-to-end.

This slice makes priority a property of the whole task tree: the execution context that already travels from parent to child carries the effective priority, and the dispatch path uses it whenever no explicit override is given. As with the foundation slice, nothing is reprioritized yet — no production caller dispatches non-medium — so observable behavior is unchanged while the inheritance mechanics land.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A task tree runs at the priority of its root (Priority: P1)

A workflow dispatched at an effective priority carries that priority in its execution context, and every sub-workflow dispatched with that context inherits the same lane unless a call site explicitly overrides it. Urgency belongs to the root operation: once classification later marks an operation high-priority, everything that operation spawns rides the high lane, making the expedition observable end-to-end.

**Why this priority**: This is the entire slice. Without inheritance, the foundation's priority lanes only ever apply to root flows, which defeats the purpose for every real operation that fans out into sub-workflows.

**Independent Test**: Dispatch a workflow with an explicit priority override and have it dispatch a sub-workflow (passing its context, no explicit priority); assert the sub-workflow's run lands in the same queue — including at depth ≥ 2.

**Acceptance Scenarios**:

1. **Given** an initialized instance with the three priority lanes, **When** a workflow is dispatched with an explicit high priority and it dispatches a sub-workflow passing its context with no explicit priority, **Then** the sub-workflow's run lands in the high queue.
2. **Given** a prioritized task tree, **When** a depth-1 sub-workflow dispatches its own sub-workflow (depth 2) passing its context, **Then** the depth-2 run lands in the root's lane — regardless of whether depth 1 was routed by explicit override or inherited context.
3. **Given** a running workflow whose context carries a low priority, **When** it dispatches a sub-workflow whose catalogue default is high (no explicit override), **Then** the sub-workflow runs low — inheritance is exact, never floored or raised by the child's catalogue default.
4. **Given** a running workflow whose context carries a priority, **When** it dispatches a sub-workflow with an explicit priority override at the call site, **Then** the override wins and re-roots the priority for that sub-tree.
5. **Given** a workflow dispatched with no explicit priority and a context carrying no priority, **When** the dispatch resolves, **Then** the run lands in the lane of the workflow's catalogue default (the foundation slice's behavior, unchanged).

---

### User Story 2 - No sub-dispatch silently drops priority (Priority: P2)

Every sub-workflow dispatch site inside a running task passes the execution context it already has in scope, so inheritance actually reaches all places as of this slice. Today a handful of sub-dispatch sites omit the context; those trees would silently lose their priority at that hop.

**Why this priority**: Inheritance mechanics (User Story 1) are worthless at the dispatch sites that don't pass a context. This one-time audit is the "in all places" half of the feature.

**Independent Test**: Enumerate all sub-workflow dispatch sites inside running tasks and verify each passes the in-scope context; covered by a review checklist in the change itself.

**Acceptance Scenarios**:

1. **Given** the audited codebase, **When** any running task that holds an execution context dispatches a sub-workflow, **Then** the call passes that context.
2. **Given** a dispatch site that is a tree root (no user context exists, e.g. scheduled or CLI-triggered work), **When** the audit is applied, **Then** the site is left unchanged — roots have no inheritance semantics.

---

### Edge Cases

- **Low parent, catalogue-high child**: the child runs low (exact inheritance). A floor/max rule would let bulk background trees elbow into the interactive lane — the inversion this feature exists to prevent.
- **Explicit override mid-tree**: the overriding call site re-roots priority for its subtree; descendants inherit the override, not the original root's priority.
- **Upgrade with in-flight runs**: contexts serialized before the upgrade carry no priority; they resolve to the catalogue default. One-time, benign degradation.
- **Cron-scheduled roots**: scheduled runs are created without passing through the dispatch path and carry no context priority; their trees run at catalogue defaults until classification assigns them one. Acceptable.
- **Context rebuilt mid-tree**: fresh execution contexts are only constructed at genuine entry points (API, GraphQL, CLI); no running task rebuilds one mid-tree today, so priority cannot be silently reset that way.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The execution context that travels from parent task to sub-task MUST carry an optional priority, absent by default; context payloads serialized before this change MUST deserialize with no priority set.
- **FR-002**: The dispatch path MUST resolve the effective priority as a strict precedence chain: explicit per-dispatch override, then the context's priority, then the workflow's catalogue default. Inheritance is exact — the resolved priority is never floored, capped, or otherwise combined with the child workflow's catalogue default.
- **FR-003**: The dispatch path MUST stamp the resolved effective priority into the context it hands to the child run, so descendants at depth ≥ 2 inherit correctly even when their parent was routed by catalogue default or explicit override.
- **FR-004**: Every sub-workflow dispatch site inside a running task that has an execution context in scope MUST pass that context (one-time audit). The context parameter remains optional on the dispatch interface; enforcement is this audit, not a type-level guarantee. Root-level dispatch sites without a user context are out of the audit's scope.
- **FR-005**: The priority MUST NOT leak into the event context or the SDK request context derived from the execution context — events and the client-facing contract are unchanged. Event-triggered workflows are new tree roots whose priority comes from their own classification, not from the lane of the emitting task.
- **FR-006**: The local (inline) execution adapter MUST mirror the priority resolution and context stamping of the worker adapter — while still performing no queue routing — so inheritance behavior is observable and testable in local execution.

### Key Entities

- **Execution context (InfrahubContext)**: existing entity carrying branch and account identity across the task tree; gains an optional priority. The only entity change in this slice.
- **Priority tier / lanes / dispatch override**: existing entities from the foundation slice (typed tier enum, three queues, per-dispatch override parameter); consumed, not modified.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A root dispatched with any explicit priority has 100% of its transitive sub-workflows (absent explicit overrides) land in the same lane, verified at depth ≥ 2.
- **SC-002**: Zero behavior change absent classification: the existing test suite passes unmodified, and all runs still land in the medium lane by default.
- **SC-003**: After the audit, 100% of sub-workflow dispatch sites inside running tasks pass an execution context (all known in-flow gaps fixed; root-level sites explicitly exempt).

## Scope Boundaries

### In Scope

- Optional priority on the execution context, absent by default and backward-compatible with previously serialized payloads.
- Effective-priority resolution (override → context → catalogue default) and context stamping on both dispatch entry points of the workflow adapter, mirrored by the local adapter.
- One-time audit passing the in-scope context at sub-dispatch sites inside running tasks that currently omit it.
- Update of the backend architecture knowledge doc for async tasks in the same change.

### Out of Scope

- Classifying individual workflows into tiers (everything stays medium in this slice).
- Client/frontend/API/SDK priority signal — priority remains internal plumbing.
- Priority on events or the SDK request context.
- Starvation protection (per-queue concurrency limits) — later slice, before the first real high-priority traffic.
- Making the context a required parameter on the dispatch interface (accepted residual risk: future dispatch sites can omit it silently).
- User documentation (no user-facing change); changelog fragment optional.

### Governance Gates

- Database schema or migration change — none.
- GraphQL schema modification — none.
- New dependency — none.
- CI/CD workflow change — none.
- Authentication / authorization change — none.

## Assumptions

- The foundation slice (priority lanes, tier enum, dispatch override) is present on this branch; this spec builds directly on it and the two ship together in one PR covering both specs.
- Exact inheritance is the agreed semantic: urgency is a property of the root operation, and the catalogue default only ever applies to tree roots.
- The dispatch adapter stamps the effective priority; call sites never compute it themselves.
- The audit is point-in-time: the context parameter stays optional, and keeping future dispatch sites honest is a review concern, not a type-system guarantee (explicitly accepted).
- No production caller dispatches a non-medium priority until the classification slice lands, so this slice is behavior-neutral (Constitution VII / YAGNI exception, same justification as the foundation slice: committed follow-up work under INFP-635, to be restated in the PR).
