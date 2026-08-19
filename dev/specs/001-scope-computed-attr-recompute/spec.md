# Feature Specification: Scope Computed-Attribute Recompute to Actual Schema Changes

**Feature Branch**: `001-scope-computed-attr-recompute`
**Created**: 2026-06-01
**Status**: Draft
**Input**: User description: "Using docs/superpowers/plans/2026-06-01-scope-computed-attribute-recompute.md — during a schema change, all computed attributes recalculate even when there is no schema change for the node that owns the computed attribute."

## Clarifications

### Session 2026-06-01

- Q: When is an impacted computed attribute's new value expected relative to the schema change completing? → A: Asynchronous / eventually consistent — the schema change completes immediately and impacted attributes are recomputed shortly afterward via background jobs.
- Q: Should the recompute/skip scoping decision be observable to operators? → A: Summary signal — record which computed attributes were selected for recompute per schema change (count + identities); skipped attributes available at a more verbose/diagnostic level.

### Session 2026-06-03

- Q: Through what medium should the selected-vs-skipped scoping signal surface? → A: Task/worker logs — an info-level summary (count + identities selected) and a debug-level skipped list, via the existing computed-attribute task logging.
- Q: How deep must the dependency set follow relationships? → A: Full depth where derivable (e.g. `device.site.region.name`); when depth or the precise read set cannot be determined, conservatively recompute (never skip a needed recompute).
- Q: When a single attribute's dependency set cannot be precisely determined (e.g. an unanalyzable transform query), what happens? → A: Recompute that one attribute on every schema change (treat it as depending on everything); other attributes remain normally scoped — no branch-wide full recompute.
- Q: Which schema edits to a read element count as "changed" for recompute? → A: Any schema edit to the element (name, kind, removal, and cosmetic edits such as label/description/order), not only value-affecting edits.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unrelated schema change does not recompute everything (Priority: P1)

An operator edits the schema of one object type (for example, adds an attribute to a `Location` model). Computed attributes that belong to other, unrelated object types — and whose values do not read anything that changed — are left untouched. The schema change settles quickly without a flood of background recomputation jobs across the whole dataset.

**Why this priority**: This is the reported defect. Today every transform-based computed attribute on the branch is recomputed on any schema change, generating one recompute job per object of every affected type regardless of relevance. On large datasets this is slow, wasteful, and obscures the work that actually matters.

**Independent Test**: On a branch with several computed attributes, apply a schema change that touches only a model none of them read. Verify that zero recompute jobs are produced for those computed attributes.

**Acceptance Scenarios**:

1. **Given** a branch with a computed attribute whose value reads only fields of type A, **When** a schema change modifies only type B (and nothing the attribute reads), **Then** the computed attribute is not recomputed and no recompute work is queued for it.
2. **Given** a model containing one computed attribute plus many ordinary attributes, **When** an ordinary attribute the computed value does not read is changed, **Then** the computed attribute is not recomputed.

---

### User Story 2 - Recompute when a depended-on field changes, including across relationships (Priority: P1)

A computed attribute's value is derived from data that may live on the owning object or on related objects reached "further away" through relationships. When a schema change affects any field or related object type that the value reads, that computed attribute is recomputed so its stored value stays correct.

**Why this priority**: Scoping must not sacrifice correctness. A computed value that reads `device.site.name` must recompute when `site.name` changes, even though the change is on a different object type than the one that owns the attribute. Missing this would leave stale values, which is worse than over-recomputing.

**Independent Test**: Define a computed attribute that reads a field on a related object type. Apply a schema change to that related field. Verify the computed attribute is recomputed.

**Acceptance Scenarios**:

1. **Given** a computed attribute on type A whose value reads a field on related type B, **When** a schema change modifies that field on type B, **Then** the computed attribute on type A is recomputed.
2. **Given** a computed attribute whose own definition (its template or transform reference) is edited in the schema, **When** the schema change is applied, **Then** the computed attribute is recomputed.
3. **Given** a computed attribute that reads an object type that is removed or newly added by the schema change, **When** the change is applied, **Then** the computed attribute is recomputed.
4. **Given** a computed attribute whose value depends on a related object's display label (whose backing fields cannot be determined precisely), **When** any change is made to that related type, **Then** the computed attribute is recomputed (conservative correctness).

---

### User Story 3 - Template-based attributes recompute on data-affecting field changes (Priority: P2)

Operators use both template-based and transform-based computed attributes. A schema migration that changes a field a template reads (without changing the template itself) causes the template-based computed attribute to be recomputed, so its value does not silently go stale. Scoping behaves consistently across both kinds of computed attribute.

**Why this priority**: Template-based computed attributes currently recompute only when their template definition changes, so a migration that alters a field they read is missed. Unifying the scoping rule fixes this gap while keeping the same "only what's impacted" behavior for both kinds.

**Independent Test**: Define a template-based computed attribute that reads a field. Apply a schema migration that changes that field but not the template. Verify the attribute is recomputed.

**Acceptance Scenarios**:

1. **Given** a template-based computed attribute reading field X, **When** a schema migration changes field X but not the template, **Then** the attribute is recomputed.
2. **Given** the same attribute, **When** a schema change touches only fields the template does not read, **Then** the attribute is not recomputed.

---

### Edge Cases

- **Change details unavailable**: When a schema-update path cannot report which schema elements changed, the system recomputes all computed attributes (the current behavior). Correctness is never traded for the optimization.
- **Branch deletion**: A branch-deletion event carries no schema diff; recompute scoping does not apply and existing behavior is preserved.
- **Transform source-code change**: Recompute triggered by a change to a transform's source code (delivered through repository synchronization, not a schema change) is out of scope and keeps its current behavior.
- **Branch rebase / merge applying schema changes**: Merge and rebase emit branch and node events, not a schema-update event, so this recompute scoping does not run on that path (unchanged from before the feature). Computed values for merged object-data changes are recomputed by the existing data-change path; a merge that applies only a schema change, with no data change, does not recompute.
- **Whole object type added or removed**: Treated as impacting every computed attribute that reads that type, since field-level detail is unavailable.
- **Attribute dependency indeterminate**: When the changed-element set is known but one attribute's reads cannot be precisely derived, that single attribute is always recomputed (conservative); other attributes remain scoped, and no branch-wide full recompute is triggered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a schema change is applied, the system MUST recompute a computed attribute only if the change affects a schema element (object type, attribute, or relationship) that the attribute's value depends on.
- **FR-002**: The dependency set of a computed attribute MUST include schema elements reached indirectly through relationships at any depth (not only the object type that owns the attribute). Where the traversal depth or the precise set of read elements cannot be determined, the system MUST conservatively recompute rather than risk skipping a needed recompute.
- **FR-003**: A computed attribute whose own definition is modified by the schema change MUST be recomputed.
- **FR-004**: A computed attribute MUST be recomputed when a schema element its value reads is changed or removed, even if the attribute's own definition is unchanged. Any schema edit to that element counts as a change — including cosmetic edits such as label, description, or ordering — not only edits that alter the stored value.
- **FR-005**: A computed attribute MUST be recomputed when an object type its value reads is added or removed by the schema change.
- **FR-006**: When a computed attribute's value depends on a related object's display label, the system MUST treat any change to that related object type as impacting the attribute (conservative correctness, because the fields backing a display label cannot be determined precisely).
- **FR-007**: A schema change that does not affect any schema element a computed attribute depends on MUST NOT cause that attribute to be recomputed.
- **FR-008**: When the set of changed schema elements cannot be determined for a given schema-update path, the system MUST fall back to recomputing all computed attributes, never skipping a recompute that may be needed.
- **FR-009**: Recompute scoping MUST behave consistently for both template-based and transform-based computed attributes.
- **FR-010**: Recompute scoping MUST remain branch-aware — a schema change on one branch MUST NOT broaden recomputation of attributes on other branches beyond existing behavior.
- **FR-011**: Recomputation triggered by a schema change MUST be performed asynchronously — applying the schema change MUST NOT wait for recompute to finish, and the values of impacted computed attributes MUST be eventually consistent once the background recompute completes.
- **FR-012**: The scoping decision MUST be observable through the recompute task logs — for each schema change the system MUST log, at the normal/info level, a summary of which computed attributes were selected for recompute (count and identities); the set of attributes that were intentionally skipped MUST be logged at a verbose/diagnostic (debug) level.
- **FR-013**: When the changed-element set IS known but a single computed attribute's own dependency set cannot be precisely determined (e.g. its transform query is not statically analyzable), the system MUST recompute that attribute on every schema change (treating it as depending on everything) while keeping all other attributes normally scoped. This per-attribute conservatism MUST NOT escalate to a full recompute of unrelated attributes.

### Key Entities *(include if feature involves data)*

- **Computed attribute**: An attribute whose value is derived rather than entered directly. Two kinds exist: template-based (value rendered from a template) and transform-based (value produced by running a transform over a query). Each has a definition and a value stored per object.
- **Schema change**: The set of object types, attributes, and relationships that were added, changed, or removed when a schema update is applied to a branch.
- **Dependency set**: For a single computed attribute, the object types and fields its value reads — including those reached through relationships at any depth — used to decide whether a given schema change should trigger recompute.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A schema change that touches only object types and fields unrelated to a given computed attribute produces zero recompute jobs for that attribute.
- **SC-002**: For a schema change that affects the dependencies of N out of M computed attributes on a branch, exactly those N attributes are recomputed and no more.
- **SC-003**: The amount of recompute work after a schema change scales with the number of impacted computed attributes, not with the total number of computed attributes defined on the branch — changing one field in a model that has many unrelated computed attributes recomputes only the attributes that read that field.
- **SC-004**: Every computed attribute whose dependency is affected by a schema change is recomputed and converges to the correct value (no permanently stale values): correctness is preserved across all scenarios in User Stories 2 and 3, verified after background recompute completes.
- **SC-005**: On schema-update paths where the changed-element set is unavailable, recomputation behavior is identical to the pre-change behavior (full recompute), confirming no regression.
- **SC-006**: For any schema change, an operator can determine from the recompute task logs which computed attributes were recomputed — and, at a diagnostic (debug) level, which were intentionally skipped — without inspecting source code.

## Assumptions

- The set of schema elements changed by an update is available, or can be made available, at the point where recompute is decided for the primary schema-update paths (interactive schema edits and schema loads).
- "Computed attribute" covers both template-based and transform-based kinds; both are in scope for this feature.
- Recompute caused by a transform's source-code change (delivered via repository synchronization rather than a schema change) is out of scope and retains its current full-recompute behavior.
- Branch rebase/merge does not emit a schema-update event, so this scoping does not apply to the merge/rebase path; recompute of merged object-data changes is handled by the existing data-change path. This is unchanged from before the feature.
- The existing per-object recompute mechanism and the per-branch isolation of computed attributes are reused unchanged; this feature only changes which attributes are selected for recompute after a schema change.
