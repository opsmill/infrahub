# Feature Specification: Local Computation of Jinja2 Computed Attributes

**Feature Branch**: `ifc-2273-local-computation-jinja2`
**Created**: 2026-03-19
**Status**: Draft
**Input**: IFC-2273 — Optimize Jinja2 computed attribute updates by handling "local" changes immediately within the original mutation rather than as background tasks, while continuing to use Prefect for "remote" changes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Immediate Computed Attribute Updates on Local Attribute Changes (Priority: P1)

A user updates an attribute on a node that has a Jinja2-based computed attribute depending on that same attribute. The computed attribute is recalculated and persisted as part of the same mutation. When the mutation response returns, the computed attribute already reflects the new value — no background task, no page refresh needed.

**Why this priority**: This is the core value proposition. It eliminates the most common source of unnecessary background tasks (local attribute changes) and directly improves perceived performance and user experience.

**Independent Test**: Can be fully tested by updating an attribute used in a computed attribute on the same node and verifying the computed value is correct in the mutation response.

**Acceptance Scenarios**:

1. **Given** a Device node with a computed attribute `name` using Jinja2 template `{{ instance__value }}-{{ site__name__value }}`, **When** the user updates `instance` on that Device, **Then** the `name` computed attribute is recalculated inline and the mutation response contains the updated computed value.
2. **Given** a node with a computed attribute referencing a local attribute, **When** the user updates that local attribute, **Then** no background task is created for the computed attribute update.
3. **Given** a node with a computed attribute, **When** the user updates an attribute that is NOT used by the computed attribute template, **Then** no recomputation occurs and no background task is created.

---

### User Story 2 - Immediate Computed Attribute Updates on Local Relationship Changes (Priority: P1)

A user changes a relationship on a node that has a Jinja2-based computed attribute depending on that relationship (e.g., re-assigning a Device to a different Site). The computed attribute is recalculated inline using the new peer's attributes.

**Why this priority**: Relationship changes are a common trigger for computed attribute recomputation. Handling them inline alongside attribute changes completes the "local change" coverage.

**Independent Test**: Can be tested by changing a relationship on a node with a computed attribute that references that relationship's peer attributes, and verifying the computed value updates in the mutation response.

**Acceptance Scenarios**:

1. **Given** a Device with computed `name` = `{{ instance__value }}-{{ site__name__value }}` currently assigned to SiteA, **When** the user re-assigns the Device to SiteB, **Then** the `name` is recalculated using SiteB's name and the mutation response reflects the updated value.
2. **Given** a node with a computed attribute referencing a relationship, **When** the user changes that relationship, **Then** no background task is created for the computed attribute update.

---

### User Story 3 - Remote Changes Continue Via Background Tasks (Priority: P2)

When a user updates a peer node's attribute that is referenced by computed attributes on other nodes (a "remote" change), the system continues to handle recomputation via background tasks as it does today.

**Why this priority**: Ensures backward compatibility and correctness for the remote case. This is not new functionality — it validates the existing path is preserved.

**Independent Test**: Can be tested by updating a peer node attribute (e.g., renaming a Site) and verifying that computed attributes on related nodes (e.g., Devices assigned to that Site) are updated via background tasks.

**Acceptance Scenarios**:

1. **Given** a Site referenced by multiple Device nodes with computed attributes using Site's name, **When** the user updates the Site's name, **Then** the computed attributes on related Devices are updated via background tasks (existing behavior preserved).
2. **Given** a remote change triggers a background task, **When** the task completes, **Then** the computed attribute values are correct.

---

### User Story 4 - Consolidated Events for Local Changes (Priority: P2)

When a user updates an attribute that triggers a local computed attribute recomputation, only a single event/webhook is emitted for the entire mutation — not separate events for the original change and the computed attribute update.

**Why this priority**: Reduces notification noise for integrations and webhook consumers. Important for operational clarity but secondary to core computation correctness.

**Independent Test**: Can be tested by subscribing to node change events, performing a local change that triggers computed attribute recomputation, and verifying only one consolidated event is received.

**Acceptance Scenarios**:

1. **Given** a webhook subscription on a node kind with computed attributes, **When** a user updates a local attribute that triggers computed attribute recomputation, **Then** exactly one webhook event is fired containing both the original change and the updated computed attribute.
2. **Given** a bulk import updating many nodes with computed attributes via local changes, **When** the import completes, **Then** each node produces at most one event (not two separate events per node).

---

### User Story 5 - Bulk Update Performance (Priority: P2)

When a bulk update modifies thousands of existing nodes with computed attributes, the system handles local computed attribute recomputation inline within each mutation rather than spawning thousands of separate background tasks.

**Why this priority**: This is the highest-impact performance scenario. Updating 2,000 interfaces currently triggers 2,000 background tasks, each independently querying the database.

**Independent Test**: Can be tested by bulk-updating existing nodes with computed attributes and measuring that no background tasks are spawned for local changes, and that total processing time and resource consumption are reduced.

**Acceptance Scenarios**:

1. **Given** 2,000 existing nodes with Jinja2 computed attributes that depend on local attributes, **When** a bulk update modifies local attributes on all 2,000 nodes, **Then** zero background tasks are spawned for local computed attribute updates.
2. **Given** the same bulk update, **When** the update completes, **Then** all computed attribute values are correct and immediately visible.

---

### Edge Cases

- What happens when a computed attribute template references both local and remote attributes, and only a local attribute changes? The local recomputation should use the current persisted values for remote attributes (no need to re-fetch peer data beyond what is already loaded).
- What happens when a computed attribute template references a relationship that is being set to null/empty? The computed attribute should be recalculated with the null relationship context, producing whatever the Jinja2 template renders for missing data.
- What happens when multiple computed attributes on the same node depend on the same changed attribute? All affected computed attributes must be recalculated in one pass.
- What happens when a computed attribute depends on another computed attribute on the same node (chained computation)? The system must resolve dependencies in the correct order.
- How does this behave on non-default branches? The inline computation must respect branch context, using the correct schema and data for the active branch.
- What happens for transform-based computed attributes? They are excluded from this optimization and continue using background tasks only.
- What happens when inline Jinja2 template evaluation fails (e.g., missing attribute, type error)? The error is logged, the computed attribute value is left unchanged, and the mutation succeeds. This matches existing background task error semantics.

## Clarifications

### Session 2026-03-20

- Q: What should happen if inline Jinja2 evaluation fails during a mutation? → A: Log the error, leave computed attribute unchanged, mutation succeeds.
- Q: Does this optimization apply to node creation or only updates? → A: Update path only — the creation path (including `_process_macros` for mandatory attrs) remains unchanged.
- Q: Should both optional and mandatory computed attributes recompute inline on local updates? → A: Yes, both recompute inline on local update changes regardless of optional/mandatory distinction.
- Q: Is an additional DB query acceptable to fetch new peer attributes on relationship changes? → A: No extra query needed — the existing `_collect_extra_filters` pattern in `Node._collect_extra_filters()` can be extended to include computed attribute relationship fields, loading peer data during `resolve_relationships()`.
- Q: Does this feature change the template instantiation path? → A: No, template instantiation is unchanged — out of scope like other creation paths.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST recompute Jinja2-based computed attributes inline during the mutation when the changed attribute or relationship is on the same node as the computed attribute ("local change").
- **FR-002**: System MUST NOT spawn a background task for computed attribute updates triggered by local changes.
- **FR-003**: System MUST continue to use background tasks for computed attribute updates triggered by changes on related/peer nodes ("remote changes").
- **FR-004**: System MUST emit a single consolidated event per node mutation, including both the original change and any inline-computed attribute updates.
- **FR-005**: System MUST correctly identify which computed attributes on a node are affected by a given attribute or relationship change, and only recompute those.
- **FR-006**: System MUST handle the case where a computed attribute template references both local and remote data — only local triggers cause inline recomputation.
- **FR-007**: System MUST resolve dependency order when multiple computed attributes on the same node have interdependencies.
- **FR-008**: System MUST NOT apply this optimization to transform-based computed attributes; those continue using background tasks exclusively.
- **FR-009**: System MUST support inline recomputation across all branches, respecting branch-specific schema and data.
- **FR-010**: The inline computation MUST produce identical results to the current background task computation for the same inputs.
- **FR-011**: This optimization applies to the **update mutation path only**. Node creation and template instantiation paths remain unchanged.
- **FR-012**: Both optional and mandatory Jinja2 computed attributes MUST recompute inline on local update changes.
- **FR-013**: If inline Jinja2 evaluation fails, the system MUST log the error, leave the computed attribute value unchanged, and allow the mutation to succeed.

### Key Entities

- **Computed Attribute**: An attribute on a node whose value is derived from a Jinja2 template referencing other attributes or relationships on the same or related nodes. Has a computation type (Jinja2 or transform) and a template definition.
- **Local Change**: A mutation to an attribute or relationship on the same node that owns the computed attribute. Triggers inline recomputation.
- **Remote Change**: A mutation to an attribute on a peer/related node referenced by a computed attribute template. Continues to trigger background recomputation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Local attribute or relationship changes that affect computed attributes produce updated computed values in the mutation response with zero background tasks spawned.
- **SC-002**: Bulk update of 2,000 existing nodes with local computed attributes completes without spawning background tasks for computed attribute updates, reducing total background task count to zero for local changes.
- **SC-003**: Each node mutation that triggers local computed attribute recomputation emits exactly one event/webhook, not two.
- **SC-004**: Remote changes continue to trigger background recomputation with no behavioral change from current system.
- **SC-005**: Inline-computed attribute values are identical to values that would have been produced by the existing background task path for the same inputs.
- **SC-006**: No user-facing behavioral change — users interact with computed attributes the same way, but see results faster.

## Assumptions

- INFP-441 (placeholder automation refactor) is NOT available — this work must integrate with the current automation structure as-is.
- The existing Jinja2 template evaluation logic can be reused for inline computation without modification to the template engine itself.
- Peer/relationship data needed for local recomputation is loaded via the existing `_collect_extra_filters` mechanism in `Node._collect_extra_filters()`, extended to include computed attribute relationship fields — no additional DB query beyond the existing `resolve_relationships()` call.
- The performance overhead of inline computation during mutations is acceptable and results in net improvement over the background task approach.

## Scope Exclusions

- Transform-based computed attributes are explicitly out of scope.
- Schema-change-triggered regeneration of all computed attributes for a node kind remains handled by the existing automation/background mechanism.
- No changes to the Jinja2 template syntax or capabilities.
- No changes to how users define computed attributes in schemas.
- Node creation path (including `_process_macros` for mandatory computed attrs during `Node.new()`) is unchanged.
- Template instantiation path (`handle_template_relationships` / `NodeTemplateApplier`) is unchanged.
