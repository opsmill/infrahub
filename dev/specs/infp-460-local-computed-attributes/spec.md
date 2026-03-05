# Feature Specification: Local Execution of Jinja2 Computed Attributes

**Feature Branch**: `infp-460-local-computed-attributes`
**Created**: 2026-02-18
**Status**: Draft
**Jira Issue**: INFP-460
**Input**: "Refactor Jinja2 based computed attributes to handle local updates immediately within the original mutation rather than as background tasks, while continuing to use Prefect for remote updates."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Immediate Local Computed Attribute Updates (Priority: P1)

When users update attributes or relationships on a node that are used by computed attributes on that same node, the computed attributes are recalculated and updated immediately within the same operation.

**Why this priority**: This is the core optimization that addresses a high-impact scenario - local updates account for the majority of computed attribute updates and cause the most resource overhead. Delivers immediate value by eliminating thousands of background tasks in bulk update scenarios.

**Independent Test**: Can be fully tested by creating a node with a computed attribute based on local properties, updating those properties, and verifying the computed attribute updates immediately in the same response without triggering background tasks.

**Acceptance Scenarios**:

1. **Given** an existing TestingDevice node with computed attribute "device_identifier" based on TestingDevice.hostname and TestingDevice.role, **When** user updates the TestingDevice.hostname, **Then** the device_identifier is recalculated and updated immediately in the same mutation response
2. **Given** an existing TestingDevice node with computed attribute based on its Site relationship, **When** user changes the TestingDevice's Site relationship, **Then** the computed attribute updates immediately without creating a background task
3. **Given** a user performs bulk updates on 2,000 existing Interface nodes that have computed attributes dependent on the updated properties, **When** the bulk update completes, **Then** all computed attributes are recalculated inline during the update without creating 2,000 separate background tasks
4. **Given** a node with multiple computed attributes dependent on the same local property, **When** user updates that property, **Then** all computed attributes recalculate in a single operation

---

### User Story 2 - Consolidated Events for Local Updates (Priority: P2)

When users update attributes that trigger computed attribute recalculation, they receive a single consolidated event instead of multiple separate notifications.

**Why this priority**: Improves user experience by reducing notification noise and eliminates confusion from receiving multiple events for what should be a single logical change. Also reduces webhook overhead for integrations.

**Independent Test**: Can be tested by subscribing to webhooks/events, updating a node property used by a computed attribute, and verifying only one event is received containing both the original change and the computed attribute update.

**Acceptance Scenarios**:

1. **Given** a user subscribed to node update notifications, **When** they update an attribute used by a computed attribute, **Then** they receive exactly one notification containing both changes
2. **Given** an external system consuming webhooks, **When** a node is updated affecting computed attributes, **Then** the webhook payload includes all changes in a single event
3. **Given** a user viewing a node in the UI, **When** they update a property used by computed attributes, **Then** they see all updates reflected immediately without page refresh

---

### User Story 3 - Remote Computed Attribute Updates via Background Tasks (Priority: P3)

When users update attributes on related nodes that are referenced by computed attributes on other nodes, those remote computed attributes are updated via background tasks as before.

**Why this priority**: Maintains consistency with existing behavior for remote updates while benefiting from the local optimization. Remote updates are less frequent and have less resource impact than local updates.

**Independent Test**: Can be tested by creating a TestingDevice with a computed attribute referencing Site.name, updating the Site.name, and verifying the TestingDevice's computed attribute updates via background task.

**Acceptance Scenarios**:

1. **Given** a TestingDevice with computed attribute using Site.name, **When** user updates the Site.name, **Then** the TestingDevice's computed attribute is scheduled for background update
2. **Given** multiple TestingDevices referencing the same Site, **When** the Site is updated, **Then** all affected TestingDevice computed attributes are updated via background tasks
3. **Given** a cascading update affecting multiple related nodes, **When** the root node is updated, **Then** remote computed attributes on related nodes update asynchronously without blocking the original mutation

---

### Edge Cases

- What happens when a computed attribute depends on both local and remote properties? (The entire computed attribute recalculates based on the trigger location: if the mutation occurs on the node with the computed attribute—including attribute updates or relationship changes—it's calculated inline; if the mutation occurs on a related node's properties, it uses background tasks)
- What happens when a local update fails during computed attribute recalculation? (The entire mutation should fail atomically, preventing partial updates)
- What happens to existing background tasks for computed attributes when this change is deployed? (Existing Prefect tasks continue to work for remote updates)
- What happens when schema updates require regenerating all computed attributes for a node type? (Still uses automation reference to trigger bulk regeneration)
- How are transform-based computed attributes handled? (Transform-based computed attributes are excluded from this optimization and continue using background tasks)
- What happens when multiple users update the same node simultaneously? (Standard database concurrency controls apply; last write wins with appropriate locking)
- What happens when a computed attribute calculation takes longer than expected? (User experiences delay in mutation response; calculation completes within database transaction timeout limits without explicit application-level timeout)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST recalculate Jinja2-based computed attributes immediately within the original mutation when the triggering change is on the same node (local update)
- **FR-002**: System MUST continue using Prefect background tasks for Jinja2-based computed attribute updates when the triggering change is on a related node (remote update)
- **FR-003**: System MUST exclude transform-based computed attributes from local execution optimization - they continue using background tasks
- **FR-004**: System MUST consolidate all changes (original update + computed attribute updates) into a single event/notification for local updates
- **FR-005**: System MUST maintain atomic transaction behavior - if computed attribute recalculation fails during local update, the entire mutation fails and rolls back
- **FR-006**: System MUST align local computed attribute update behavior with how display_labels and HFID updates currently work
- **FR-007**: System MUST maintain automation reference in schema to trigger computed attribute regeneration when attribute definitions are updated
- **FR-008**: System MUST reduce background task creation for bulk update scenarios (e.g., updating 2,000 interfaces should not create 2,000 separate background tasks)
- **FR-009**: System MUST update computed attributes visible in UI immediately after local updates without requiring page refresh
- **FR-010**: System MUST maintain backward compatibility with existing remote computed attribute update behavior

### Key Entities

- **Computed Attribute**: A node attribute whose value is derived from a Jinja2 template that references other attributes on the same node (local) or related nodes (remote)
- **Local Update**: Any mutation on the node where the computed attribute lives, including updating attribute values OR changing relationship targets (e.g., updating TestingDevice.hostname or changing which Site a TestingDevice points to)
- **Remote Update**: A mutation to properties of a related/peer node that is referenced by a computed attribute on another node (e.g., updating Site.name when a TestingDevice references that Site)
- **Mutation Event**: The consolidated response and notification containing all changes from an update operation, including computed attribute recalculations
- **Automation Reference**: Schema metadata used to trigger bulk computed attribute regeneration when attribute definitions change

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Bulk update of 2,000 nodes with computed attributes completes without creating 2,000 separate background tasks
- **SC-002**: Local computed attribute updates complete within the same mutation response time (target: adds less than 100ms to mutation latency)
- **SC-003**: Users receive exactly one event/notification per logical update operation instead of multiple separate events
- **SC-004**: Background task queue size reduces by at least 70% for typical workloads involving computed attributes
- **SC-005**: Database query count for local computed attribute updates reduces by at least 50% compared to background task approach
- **SC-006**: CPU utilization for background workers decreases measurably during bulk update operations
- **SC-007**: Users see computed attribute updates reflected immediately in UI without page refresh for local changes
- **SC-008**: Remote computed attribute updates continue to function with no behavioral changes
- **SC-009**: System logs show reduced volume of computed attribute-related entries for local updates
- **SC-010**: Webhook consumers receive consolidated payloads with all changes in a single request

### Business Impact

- **Resource Optimization**: Reduces excessive CPU usage, database load, and logging overhead from background task processing
- **Improved User Experience**: Updates visible immediately; fewer confusing duplicate notifications
- **Better Scalability**: Frees up background worker capacity for other operations
- **Tech Debt Reduction**: Addresses highest priority item from tech debt list

## Dependencies & Assumptions *(mandatory)*

### Dependencies

- Schema must maintain automation reference for computed attribute regeneration on schema updates
- Existing Prefect infrastructure must remain functional for remote updates

### Assumptions

- Computed attribute Jinja2 template execution time is fast enough to not cause unacceptable mutation latency (target < 100ms, bounded by database transaction timeout)
- Most computed attribute updates are local (same-node) rather than remote
- Database transaction isolation levels provide sufficient consistency guarantees for atomic updates
- Database transaction timeout provides adequate boundary for inline computation duration
- Transform-based computed attributes remain excluded from this optimization
- Existing background task retry/error handling is sufficient for remote updates

### Out of Scope

- Transform-based computed attributes (continue using background tasks)
- Optimization of remote computed attribute updates
- Changes to computed attribute schema definition syntax
- Changes to Jinja2 template evaluation engine
- Performance optimization of Prefect background task infrastructure itself
- **INFP-441**: Placeholder automation refactor will be handled separately and done against all placeholder automations (display_label, HFID and computed attributes) after this refactoring is complete

## Clarifications

### Session 2026-02-18

- Q: When a computed attribute depends on both local and remote properties, which execution path determines the calculation mode? → A: The trigger location determines the mode. Any change on the node where the computed attribute lives (including attribute updates OR relationship changes) is a local change and calculated inline. Changes to related/peer node properties (e.g., updating Site.name when Device references that Site) are remote changes and use background tasks.
- Q: What timeout threshold should apply to inline computed attribute calculations, and what should happen when exceeded? → A: No explicit timeout - allow inline calculation to complete regardless of duration, relying on database transaction timeout as the natural boundary.
- Q: When an inline computed attribute calculation fails, what should the error handling and retry behavior be? → A: No special handling - treat computed attribute calculation failures exactly like any other attribute validation failure. The mutation fails atomically with an error, no automatic retry.
- Q: What specific metrics or observability signals should be emitted to monitor local computed attribute execution? → A: Use existing observability patterns - align with same monitoring approach as display_labels and HFID updates (no new metrics patterns).
- Q: What phasing approach should be used to roll out local computed attribute execution, and what are the rollback criteria? → A: Big bang deployment - deploy to all nodes simultaneously once code is ready and tested.

## Notes

### Current Behavior vs. Change

**Current Behavior:**

- **Initial node creation**: Jinja2 computed attributes are already calculated locally/inline (no change needed)
- **Node updates**: ALL computed attribute updates (both local and remote) are handled as background tasks via Prefect

**New Behavior (This Spec):**

- **Initial node creation**: Remains unchanged - computed attributes calculated locally
- **Node updates (local)**: Computed attributes calculated inline within the mutation (NEW)
- **Node updates (remote)**: Continue using background tasks via Prefect (unchanged)

This distinction is critical - the optimization applies only to updates of existing nodes, not initial creation which already works efficiently.

### Implementation Notes

This feature represents the highest priority tech debt item and delivers significant resource optimization. The distinction between local and remote updates aligns with existing patterns for display_labels and HFID updates, providing implementation consistency.

The slight trade-off of increased mutation latency for local updates is offset by eliminating convergence delays and providing immediate visibility to users. The consolidated event model also simplifies integration for webhook consumers.

Deployment will follow a big bang approach - deploying to all nodes simultaneously once code is ready and thoroughly tested, leveraging the implementation consistency with existing display_labels/HFID patterns to minimize risk.
