# Feature Specification: Priority Work Queue Foundation for the Task Worker

**Feature Branch**: `priority-work-queues-ifc-2859`

**Created**: 2026-07-02

**Status**: Draft

**Input**: Jira IFC-2859 — PRD "Priority Work Queue Foundation for the Task Worker" (parent idea INFP-635, GitHub issue opsmill/infrahub#9785)

## Problem Statement

When an Infrahub instance is processing a large backlog of background tasks, interactive operations (branch create, merge, diff, proposed changes) are dispatched into the same single work queue as everything else and wait behind the entire backlog. Before any workflow can be expedited, the task execution layer needs a priority structure to route work into — today none exists.

This slice builds that structure only: three priority lanes, a default lane per workflow, and a dispatch-time override seam. Nothing is reprioritized yet — every workflow stays on the medium lane, so observable behavior is unchanged while the foundation lands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Priority-ready task infrastructure (Priority: P1)

After task-manager initialization, all workflows run exactly as before but through a priority-aware queue structure that a later change activates by assigning priorities. Every workflow in the catalogue carries a default priority tier (medium everywhere in this slice), deployments — including cron-scheduled workflows — are attached to the queue matching their tier, and the dispatch path accepts an optional priority override.

**Why this priority**: This is the entire slice. It is the foundation all follow-up prioritization work (workflow classification, client-facing priority signal) plugs into; without it none of that work has a seam to land in.

**Independent Test**: Initialize the task manager against a clean orchestrator, then assert the worker pool has high/medium/low queues, every catalogue deployment is attached to the queue matching its default tier, and a workflow dispatched with an explicit priority override lands in the corresponding queue.

**Acceptance Scenarios**:

1. **Given** a clean task-manager instance, **When** initialization completes, **Then** the worker pool has three priority work queues (high, medium, low) with priority ordering configured.
2. **Given** the task manager is initialized, **When** the workflow catalogue is deployed, **Then** every deployment — including cron-scheduled workflows — is attached to the queue matching its catalogue default priority (medium for all workflows in this slice).
3. **Given** an initialized instance, **When** a workflow is dispatched with an explicit priority override (any of the three tiers), **Then** the run lands in the queue matching that override.
4. **Given** an initialized instance, **When** a workflow is dispatched with no priority specified anywhere, **Then** the run lands in the medium queue.

---

### User Story 2 - Seamless upgrade of a deployed instance (Priority: P2)

An operator upgrades an existing Infrahub instance that was provisioned with the legacy single-queue layout. At startup, the system converges to the new three-lane layout automatically — no manual migration, no infrastructure change, no worker launch-configuration change.

**Why this priority**: Every existing deployment crosses this path exactly once on upgrade. It must be safe, but it reuses the same idempotent initialization as User Story 1.

**Independent Test**: Run task-manager initialization against an orchestrator state that predates priority queues (single default queue, deployments attached to it), then assert the three lanes exist and all deployments are re-attached to their tier queue.

**Acceptance Scenarios**:

1. **Given** an instance provisioned before priority queues existed, **When** it starts up after upgrade, **Then** the pool has the three priority queues and all catalogue deployments are re-saved onto the queue matching their default tier, with no manual steps.
2. **Given** runs created before the upgrade sitting in the legacy default queue, **When** workers poll after upgrade, **Then** those runs still execute, because workers consume all queues in the pool.
3. **Given** the instance restarts repeatedly, **When** initialization runs again, **Then** queue provisioning is idempotent — no duplicate queues, no errors, same converged layout.

---

### User Story 3 - Graceful degradation when a queue is missing (Priority: P3)

If a priority queue is missing at dispatch time (initialization race, or an operator deleted a queue via the task-manager UI), dispatch does not fail: the run executes in the default lane and a warning is emitted so the operator can investigate.

**Why this priority**: Defensive path; rare in practice but it is the guarantee that queue-layout drift can never break task execution.

**Independent Test**: Delete or omit one priority queue, dispatch a workflow targeting it, and assert the run completes in the default lane and a warning is logged.

**Acceptance Scenarios**:

1. **Given** the target priority queue does not exist on the pool, **When** a workflow is dispatched to it, **Then** the dispatch succeeds, the run executes in the default lane, and a warning is emitted identifying the missing queue.
2. **Given** any queue-layout drift, **When** work is dispatched, **Then** no dispatch ever fails because of queue layout.

---

### User Story 4 - Operator visibility of the three lanes (Priority: P3)

An operator opens the task-manager UI and sees the three priority lanes on the worker pool, so they can observe where work is routed once prioritization is activated.

**Why this priority**: Pure observability; falls out of creating the queues in the orchestrator (its native UI lists the pool's queues) rather than requiring separate work.

**Independent Test**: After initialization, list the pool's work queues via the task-manager UI/API and confirm the three lanes are visible with their priority ordering.

**Acceptance Scenarios**:

1. **Given** an initialized instance, **When** an operator views the worker pool in the task-manager UI, **Then** the high, medium, and low lanes are visible.

---

### Edge Cases

- **Upgrade of a deployed instance**: startup re-provisions the pool and re-saves all deployments, converging to the new queue layout; runs stranded in the legacy default queue still execute because workers poll all queues in the pool (User Story 2).
- **Missing queue at dispatch** (operator deletion in the task-manager UI): dispatch names the queue from the static tier mapping and proceeds; the orchestrator auto-creates a missing queue (at arbitrary precedence) and the next startup convergence restores its precedence. Dispatch never fails due to queue layout.
- **Starvation under real high-priority traffic**: impossible in this slice — nothing dispatches non-medium. Starvation protection (per-queue concurrency limits) is explicitly deferred and must land before or with the first real high-priority traffic.
- **Repeated startup**: queue provisioning is idempotent on every startup; re-running initialization never duplicates queues or errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create three priority work queues (high/medium/low) on the worker pool during task-manager initialization, idempotently on every startup.
- **FR-002**: Every workflow definition in the catalogue MUST carry a default priority, defaulting to medium.
- **FR-003**: Deployments MUST be created attached to the queue matching the workflow's default priority — including cron workflows, whose scheduled runs inherit the deployment's queue.
- **FR-004**: The dispatch path MUST accept an optional priority override that routes the run to the matching queue, on both execution entry points of the workflow adapter.
- **FR-005**: When no priority is specified anywhere, runs MUST land in the medium queue.
- **FR-006**: The dispatch path MUST derive the target queue from the static tier-to-queue mapping and MUST NOT perform a per-dispatch queue-existence check; queue existence is an initialization invariant (FR-001), and a queue recreated by the orchestrator on dispatch is converged back to its precedence at the next startup.
- **FR-007**: Workers MUST consume all pool queues with no worker-startup configuration changes (no new flags, environment variables, or compose/helm edits).
- **FR-008**: The priority tier vocabulary MUST be a typed enum (not free-form strings) at every boundary, and MUST be the single source of truth for the tier-to-queue mapping.

### Key Entities

- **Priority tier** *(new)*: `high` / `medium` / `low` — priority-semantic vocabulary, deliberately not the intent-based taxonomy (interactive/deferred) still in discovery under INFP-635. Single source of truth for tier-to-queue mapping.
- **Workflow definition (catalogue)**: existing entity; gains a default-priority field (medium by default).
- **Worker pool / work queues**: existing single pool gains three priority queues with priority ordering.
- **Dispatch path (workflow adapter)**: existing entry points gain priority routing via the static tier-to-queue mapping.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After initialization, three priority lanes exist and 100% of catalogue workflows (including cron workflows) are attached to the lane matching their default priority.
- **SC-002**: Explicit-priority dispatch lands in the matching lane 100% of the time, for all three priorities.
- **SC-003**: Zero behavior change — everything defaults to medium; the existing test suite passes unmodified.
- **SC-004**: Queue routing is verified for every path — catalogue default, explicit override, and cron deployment — by asserting the queue each run/deployment is attached to. Execution ordering under load is *not* tested: it is native task-orchestrator behavior we assume correct.

## Scope Boundaries

### In Scope

- Priority tier vocabulary (typed enum + tier-to-queue mapping) in the workflows constants layer.
- Provisioning of three priority work queues at task-manager initialization, idempotent.
- Default-priority field on workflow catalogue definitions; deployment creation carries the queue assignment (covers cron workflows).
- Optional priority override on both dispatch entry points of the workflow adapter, routed via the static tier-to-queue mapping (queues assumed provisioned at startup).
- Update of the backend architecture knowledge doc for async tasks in the same change.

### Out of Scope

- Classifying individual workflows into tiers (all stay medium in this slice).
- Client/frontend/API/SDK priority signal — the override is internal plumbing only.
- Priority inheritance by sub-flows.
- Dynamic worker-count-aware sizing.
- Starvation protection (per-queue concurrency limits) — must precede the first real high-priority traffic, in a later slice.
- User documentation (no user-facing change); changelog fragment optional.

### Governance Gates

- Database schema or migration change — none.
- GraphQL schema modification — none.
- New dependency — none (native task-orchestrator feature).
- CI/CD workflow change — none.
- Authentication / authorization change — none.

## Assumptions

- The orchestrator's native queue-priority waterfall provides ordering; we configure it, we don't reimplement or re-verify it.
- Worker processes need no launch-configuration changes; queue-consumption order is server-side (satisfies FR-007).
- Per-queue concurrency limits remain available later for starvation protection; this foundation doesn't preclude them.
- The follow-up slices under INFP-635 (workflow classification, client priority signal) are committed work — this justifies landing plumbing with no production caller yet (Constitution VII / YAGNI exception, to be restated in the PR).
- Exact queue-name strings and the catalogue field name are implementation details resolved during planning.
- Task-manager UI visibility of the lanes (User Story 4) falls out of the orchestrator's native pool/queue UI; no frontend work is implied.
