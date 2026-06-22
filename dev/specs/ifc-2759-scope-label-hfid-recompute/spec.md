# Feature Specification: Scope display label and HFID recompute on schema updates

**Feature Branch**: `scope-label-hfid-recompute-ifc-2759`
**Created**: 2026-06-19
**Status**: Draft
**Jira**: [IFC-2759](https://opsmill.atlassian.net/browse/IFC-2759) (epic [IFC-2705](https://opsmill.atlassian.net/browse/IFC-2705))
**Input**: Scope display label and HFID recompute on schema updates to only the changed schema elements, mirroring the computed-attribute scoping landed in PR #9467.

## Overview

When a schema update is applied to a branch, Infrahub refreshes the stored derived values of affected nodes. For computed attributes this refresh is now *scoped*: only attributes whose declared dependencies intersect the elements that actually changed are recomputed (PR #9467). Display labels and human-friendly IDs (HFIDs) were left out of that work. Today, on any schema change, they re-sweep every node of every kind whose definition differs from the default branch, with no dependency check. On large instances this produces the same over-recompute the computed-attribute work eliminated: a one-field schema edit can trigger a recompute pass across unrelated kinds, costing minutes of degraded instance time.

This feature brings display labels and HFIDs to parity with computed attributes: a schema update recomputes a kind's display label or HFID only when the change touches something that label or HFID actually reads.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unrelated schema change does not trigger label/HFID recompute (Priority: P1)

An operator updates the schema on an instance that defines display labels and HFIDs across many kinds. The change touches one attribute on one kind that no other kind's display label or HFID reads. After the update, the system must not recompute display labels or HFIDs for the unrelated kinds.

**Why this priority**: This is the performance win the epic exists for. Without it, every schema edit pays a full label/HFID sweep proportional to the total number of kinds, regardless of relevance.

**Independent Test**: Apply a schema update that changes only an element no display label or HFID depends on, and confirm that zero label/HFID recompute work is submitted for the kinds whose dependency sets do not intersect the change.

**Acceptance Scenarios**:

1. **Given** a schema with display labels and HFIDs on multiple kinds, **When** a schema update changes an attribute that no kind's display label or HFID reads, **Then** no display-label or HFID recompute is submitted for any kind.
2. **Given** a schema update touching only kind A's internal field, **When** kind B's display label and HFID read nothing from kind A, **Then** kind B's display label and HFID are not recomputed.

---

### User Story 2 - A change to a read element still refreshes the affected label/HFID (Priority: P1)

An operator changes an element that a display label or HFID does read — either directly on the owning kind, or on a related kind reachable through a relationship the label/HFID traverses. The affected derived values must still be recomputed. Correctness must not regress in the name of scoping.

**Why this priority**: Scoping that skips a value it should have refreshed produces silent stale data, which is worse than over-recompute. This is the correctness guardrail that makes Story 1 safe to ship.

**Independent Test**: For each dependency kind (direct attribute, relationship, peer field across a relationship, the definition itself), apply a schema change to that element and confirm the affected kind's display label / HFID is recomputed.

**Acceptance Scenarios**:

1. **Given** a kind whose display label reads attribute `name`, **When** a schema update changes `name`, **Then** that kind's display label is recomputed.
2. **Given** a kind whose HFID reads a peer attribute across a relationship, **When** a schema update changes that peer attribute, **Then** the kind's HFID is recomputed.
3. **Given** a kind whose display-label template or HFID path list is itself edited in the schema update, **When** the update is applied, **Then** that kind's display label / HFID is recomputed (the definition's own change counts as a dependency).
4. **Given** a kind whose display label or HFID reads another derived value (a peer's display label/HFID, or a computed attribute), **When** any schema element changes, **Then** that kind's display label / HFID is recomputed (conservative, because the dependency cannot be mapped precisely).

---

### User Story 3 - Recompute falls back to full behavior when the change set is unavailable (Priority: P2)

Some paths apply schema changes without producing a precise set of changed elements (for example branch merge and rebase, which are addressed by separate tickets). When the change set is unavailable, the system must fall back to the existing full recompute behavior rather than skipping work and risking stale data.

**Why this priority**: Preserves correctness on paths not yet emitting a change set, and keeps this feature's blast radius limited to the scoped, change-set-bearing path.

**Independent Test**: Drive a label/HFID setup with no change set provided and confirm every candidate kind is recomputed exactly as today.

**Acceptance Scenarios**:

1. **Given** a schema-update flow invoked without a change set, **When** the label/HFID setup runs, **Then** every kind that would recompute today still recomputes (no behavior change on the fallback path).

---

### Edge Cases

- A schema element is read by more than one kind's display label/HFID (directly and via relationship): all readers must be recomputed.
- A relationship a display label/HFID traverses is itself changed (added, removed, renamed): the traversing kinds must be recomputed.
- The change set is present but empty (a no-op schema update): no label/HFID recompute is submitted.
- A kind defines both a display label and an HFID with different dependency sets: each is scoped independently; a change touching only the HFID's dependencies must not force a display-label recompute and vice versa.
- A display label/HFID definition is newly added on the branch (not present on the default branch): the change set includes the definition property, so the kind recomputes via its own-definition dependency.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On a schema update that carries a set of changed elements, the system MUST recompute a kind's display label only if the changed elements intersect that display label's declared dependency set.
- **FR-002**: On a schema update that carries a set of changed elements, the system MUST recompute a kind's HFID only if the changed elements intersect that HFID's declared dependency set.
- **FR-003**: A display label's / HFID's dependency set MUST include every schema element it reads: attributes on the owning kind, relationships it traverses, and peer fields reached through those relationships.
- **FR-004**: A display label's / HFID's dependency set MUST include the owning kind's own definition property, so an edit to the display-label template or HFID path list itself triggers recompute of that kind.
- **FR-005**: When a display label or HFID reads a value that cannot be mapped to a precise set of backing schema elements (a peer's display label or HFID, or a computed attribute's value), the system MUST treat it as depending on everything and recompute it on any schema change.
- **FR-006**: When a schema update does not carry a set of changed elements, the system MUST fall back to the existing full recompute behavior for display labels and HFIDs.
- **FR-007**: The system MUST scope each kind's display label and HFID independently, so a change touching only one of them does not force recompute of the other.
- **FR-008**: The scoping decision for display labels and HFIDs MUST reuse the same dependency-intersection logic used for computed attributes, so the three cannot diverge in how a change set is interpreted.
- **FR-009**: The system MUST record an observability signal for each scoped label/HFID setup that distinguishes a precise scoping decision from a full-recompute fallback, including how many candidates were selected out of the total.
- **FR-010**: Existing display-label and HFID recompute behavior on the fallback (no change set) path MUST remain unchanged, verified by the current optimization tests continuing to pass.

### Key Entities *(include if feature involves data)*

- **Display label definition**: A per-kind Jinja2 template producing a node's human-readable label. Declares the attributes, relationships, and peer fields it reads.
- **HFID definition**: A per-kind ordered list of schema paths producing a node's human-friendly identifier. Declares the attributes, relationships, and peer fields it reads.
- **Changed-element set**: The added kinds, removed kinds, and per-kind changed field names carried by a schema-update event, describing exactly what the update altered.
- **Dependency set**: The schema elements a single derived value reads, used to decide whether a change is relevant to it; may be marked imprecise ("depends on everything") when it cannot be determined exactly.
- **Recompute candidate**: A derived value eligible for recompute on a given branch (here, a kind's display label or HFID), evaluated against the changed-element set.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A schema update that changes only elements unrelated to a kind's display label and HFID submits zero recompute work for that kind (today it submits a full node sweep).
- **SC-002**: The number of kinds whose display labels/HFIDs are recomputed after a scoped schema update scales with the number of kinds whose dependency sets intersect the change, not with the total number of kinds defining a display label or HFID.
- **SC-003**: Every node whose display label or HFID value would change as a result of the schema update is still refreshed; no value that should change is left stale (correctness preserved across direct, relationship, and definition-change cases).
- **SC-004**: A single-field schema change on a large instance no longer scales display-label/HFID recompute with the total kind count, removing that contribution to the post-update degraded-instance window.
- **SC-005**: Behavior on the no-change-set fallback path is byte-for-byte equivalent to today, demonstrated by the existing optimization tests passing unchanged.

## Assumptions

- The scoping mechanism, change-set payload, and dependency-intersection logic introduced by PR #9467 for computed attributes are present on the base branch and are the foundation this feature generalizes.
- Display-label and HFID dependency metadata (attributes, relationships, relationship_fields, inverse relationship triggers) is already populated by the schema layer and is sufficient to derive precise dependency sets except where a derived value is read.
- The change-set payload already records a kind's node-level definition properties (display-label template, HFID path list) when they change, so an edit to a definition is visible as a changed element. This is verified during planning before relying on it.
- Per-node short-circuiting within a selected kind (skipping nodes whose inputs did not change) is out of scope and tracked separately (IFC-2762); this feature scopes which kinds recompute, not which nodes within a kind.
- Branch merge and rebase paths emitting a change set (IFC-2758/IFC-2761), performance benchmarks (IFC-2746), and transform computed attributes on Git import (IFC-2760) are out of scope and handled by sibling tickets; this feature operates on the schema-update path that already carries a change set, and falls back to full behavior elsewhere.
- Display labels and HFIDs are delivered together in a single change because they share structure; the only expected divergence is detecting an HFID path that resolves to a derived value, which is handled conservatively.
