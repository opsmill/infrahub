# Feature Specification: Peer-derived labels for hierarchical parent/children relationships

**Feature Branch**: `parent-children-labels-ifc-2930`

**Created**: 2026-07-21

**Status**: Draft

**Input**: User description: "Show peer kind label instead of generic Parent/Children on hierarchical objects (frontend-only). The current label of `Parent` isn't helpful as to what kind of object the parent is; derive the label from the peer kind instead."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Parent/children labels reflect the peer kind (Priority: P1)

A user browsing a hierarchical object wants to know *what kind* of object its parent and children are. Today every hierarchical object shows a generic "Parent" field and a "Children" tab, which convey nothing about the kind. Instead, wherever the parent/children relationship is surfaced, the user sees the peer kind's own label (for example "Region" in a location hierarchy), so the relationship is self-describing.

**Why this priority**: This is the entire feature. It directly removes the stated pain — a generic label that hides the kind — and delivers value on its own with no dependency on any other story.

**Independent Test**: Open a hierarchical object whose parent/children peer kinds have labels and confirm every relationship-label surface shows the peer label instead of "Parent"/"Children".

**Acceptance Scenarios**:

1. **Given** a hierarchical object whose parent peer resolves to a kind with the label "Region", **When** the object detail view renders, **Then** the parent relationship is labeled "Region" instead of "Parent".
2. **Given** the same object viewed in a table, filters, the relationship tabs, and the sort picker, **When** each surface renders, **Then** the parent/children relationship is labeled with the peer's label consistently across all of them.
3. **Given** a hierarchical object whose parent/children peer has no label (or the peer kind cannot be resolved), **When** any surface renders, **Then** it falls back to the existing "Parent"/"Children" label.
4. **Given** a non-hierarchical object with a relationship an author named `parent` or `children`, **When** any surface renders, **Then** that relationship's label is unchanged.

---

### Edge Cases

- **Peer is a generic, not a concrete node kind**: the peer resolves to a generic (e.g. the hierarchy generic "Location", or IPAM's `BuiltinIPPrefix`) rather than a concrete node. A generic's label is too broad to be helpful, so the substitution is **not** applied — the generic "Parent"/"Children" label is kept.
- **Peer kind has no label**: fall back to "Parent"/"Children".
- **Peer kind cannot be resolved** (missing from the loaded schema): fall back to "Parent"/"Children".
- **Children is a many-relationship labeled with a singular peer label** (e.g. a list titled "Region"): accepted verbatim; no pluralization in v1.
- **A non-hierarchical relationship coincidentally named `parent`/`children`**: must not be affected by the substitution.
- **Self-referential hierarchy with a concrete peer** (parent and children share the same concrete peer kind): both labels would render identically, so the parent↔child *direction* would no longer be conveyed by the label text. Note that IPAM prefixes — the canonical self-referential hierarchy — resolve their peer to a **generic** (`BuiltinIPPrefix`), so per the generic rule above they keep "Parent"/"Children" and the collision does not arise. A concrete self-referential hierarchy would still collide; accepted for v1 (direction is still implied by placement — parent is a field, children is a tab).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST display the peer kind's label in place of the generic "Parent"/"Children" label for the auto-generated hierarchical parent and children relationships when the peer is a **concrete node kind** with a label.
- **FR-002**: The system MUST fall back to the existing "Parent"/"Children" label when the peer kind has no label, cannot be resolved, **or is a generic** (a generic's label is too broad to identify the related kind).
- **FR-003**: The system MUST apply the peer label verbatim for both parent and children relationships, without pluralization.
- **FR-004**: The system MUST NOT alter the label of any non-hierarchical relationship, including one whose name coincides with `parent` or `children`.
- **FR-005**: The substitution MUST appear consistently across every surface where the parent/children relationship label is shown: the object detail row, the relationship tabs, table column headers, filters, and the sort picker.
- **FR-006**: The label-resolution behavior MUST be defined in a single shared place so all surfaces render the same result.

### Key Entities *(include if feature involves data)*

- **Hierarchical object**: an object of a kind that participates in a hierarchy; it has auto-generated `parent` and `children` relationships.
- **Peer kind**: the kind (or hierarchy generic) that the parent/children relationship points to; it carries the human-friendly label that this feature surfaces.
- **Relationship label**: the human-readable name shown for a relationship in the UI; today derived from the relationship name, this feature derives it from the peer kind for hierarchical parent/children relationships.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a hierarchical object whose parent/children peer kinds have labels, 100% of the surfaces that display the relationship label (detail row, tabs, table column headers, filters, sort picker) show the peer label instead of "Parent"/"Children".
- **SC-002**: Zero regressions on non-hierarchical relationship labels — every relationship outside the hierarchical parent/children case renders exactly as it did before.
- **SC-003**: A viewer can identify the kind of a hierarchical object's parent from the relationship label alone, without opening the related object, in every case where the peer kind has a label.

## Assumptions

- **Frontend-only**: no backend, schema, or migration change. The peer kind and its label are already available client-side; the feature only changes how the label is resolved for display.
- The peer kind's label and the information needed to identify a hierarchical parent/children relationship are available at every surface that renders the label.
- Author-configurable custom labels are out of scope for v1 — that would require the backend relationship `label` field and is a separate feature.
- Per-instance dynamic labels (reflecting the actual kind of each parent when the peer is a generic and instances vary) are out of scope for v1.
- Pluralization of children labels is out of scope for v1.
- In self-referential hierarchies the peer label is applied to both parent and children even though it no longer distinguishes direction. This follows the explicit decision that a present peer label always replaces "Parent"/"Children". A directional disambiguator for the flat sort/filter surfaces is a possible fast-follow if the collision proves confusing, and is out of scope for v1.
