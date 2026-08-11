# Feature Specification: Rename the misleading `has_schema_changes` branch field

**Feature Branch**: `schema-differs-from-default-ifc-2281`

**Created**: 2026-07-30

**Status**: Draft

**Input**: User description: "Deprecate and rename Branch.has_schema_changes to schema_differs_from_default_branch (INFP-469, delivered under epic IFC-2281)"

## Overview

Every branch in Infrahub exposes a boolean that tells API consumers whether that
branch's schema is in sync with the branch it was created from. Today that
boolean is named `has_schema_changes`. The name is misleading: it reads as "this
branch has changed its schema," but what it actually reports is "this branch's
schema differs from the default/origin branch." Those are not the same thing.

Two situations make the mismatch concrete:

- A user creates a branch and uploads a new schema to it. The field is `true` -
  which matches the name by luck.
- A user creates a branch, never touches its schema, and then someone changes
  the schema on the default branch. The field becomes `true` even though the
  branch's own schema was never modified. Here the name actively misleads.

This feature introduces a clearly named field, `schema_differs_from_default_branch`,
that returns the same value, marks the old field as deprecated with a stated
removal version, and moves Infrahub's own consumers onto the new field.

**Name choice**: `has_schema_diverged` was the leading alternative raised during
discovery (favored by two reviewers). It was set aside because "diverged" still
leaves the reference point implicit - the reader must know the comparison is
against the default branch. `schema_differs_from_default_branch` names both the
comparison and its reference point, which is the exact source of today's
confusion. The verbosity is accepted as the cost of an unambiguous name.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query branch schema-divergence with an honest name (Priority: P1)

An API consumer (a person writing a GraphQL query, or a downstream tool) needs
to know whether a branch's schema has diverged from the default branch. They can
request a field, `schema_differs_from_default_branch`, whose name accurately
states what the value means, so they do not have to read source code to
understand it.

**Why this priority**: This is the core of the feature. Without the new field
there is nothing to migrate to, and the misleading name remains the only option.

**Independent Test**: Query the new field on a branch whose schema matches the
default branch (expect `false`) and on a branch whose schema differs (expect
`true`), including the case where the difference originated on the default
branch. Delivers value on its own: consumers can adopt the clearer field
immediately.

**Acceptance Scenarios**:

1. **Given** a branch whose schema is identical to the default branch, **When** a
   consumer queries `schema_differs_from_default_branch`, **Then** it returns
   `false`.
2. **Given** a branch that uploaded its own schema change, **When** a consumer
   queries `schema_differs_from_default_branch`, **Then** it returns `true`.
3. **Given** an untouched branch and a schema change made afterward on the
   default branch, **When** a consumer queries `schema_differs_from_default_branch`,
   **Then** it returns `true` (the branch now differs from the default branch).
4. **Given** the same branch state, **When** a consumer queries both
   `has_schema_changes` and `schema_differs_from_default_branch`, **Then** the two
   fields return identical values.

### User Story 2 - Existing consumers keep working during deprecation (Priority: P1)

A consumer who already queries `has_schema_changes` must not break the moment
this change ships. The old field continues to return the correct value and is
marked as deprecated, with a machine-readable notice pointing to the replacement
and stating the version in which it will be removed.

**Why this priority**: Removing or changing the old field without a grace period
would break existing queries, the frontend, the SDK, and customer-authored
GraphQL. A deprecation window is what makes this a safe, non-breaking change.

**Independent Test**: Query `has_schema_changes` after the change and confirm it
still returns the correct value and that schema-introspection tooling reports it
as deprecated with a reason that names the replacement field and the removal
version.

**Acceptance Scenarios**:

1. **Given** the change is deployed, **When** a consumer queries the old
   `has_schema_changes` field, **Then** it still returns the same correct value.
2. **Given** a consumer inspects the API schema, **When** they look at
   `has_schema_changes`, **Then** it is flagged deprecated with a reason that
   names `schema_differs_from_default_branch` as the replacement and states that
   removal is planned for Infrahub 1.14.0.

### User Story 3 - The Infrahub web UI uses the new field and clearer copy (Priority: P2)

A user viewing branches in the web UI sees the schema-divergence indicator in the
same place as before, now sourced from the new field and labeled with wording
that matches its true meaning ("schema differs from default"), so the UI no
longer depends on the deprecated field and no longer carries the same misleading
wording the field rename set out to fix.

**Why this priority**: The frontend is a first-party consumer bundled with
Infrahub; leaving it on the deprecated field would mean the product ships code
that trips its own deprecation warning and would break at 1.14.0. The UI copy
today ("schema updated" badge, "Has schema changes" detail label) misleads for
exactly the reason the field name does - it shows for a branch whose own schema
was never touched - so this migration also corrects the copy. Lower than P1
because it is a first-party migration with no change to when or where the
indicator appears.

**Independent Test**: Load the branch list and branch detail views for branches
in both states and confirm the schema-divergence indicator appears in the same
positions as before, now with the clarified wording, and that the underlying
request uses the new field.

**Acceptance Scenarios**:

1. **Given** a branch whose schema differs from the default branch, **When** the
   user views the branch list, **Then** the schema-divergence indicator is shown
   in the same position as before, with wording that conveys "schema differs from
   default" rather than "schema updated".
2. **Given** any branch, **When** the UI requests branch data, **Then** it
   requests `schema_differs_from_default_branch` and not the deprecated field.
3. **Given** a branch whose schema differs from the default branch, **When** the
   user opens the branch detail view, **Then** the attribute label reads as a
   difference from the default branch rather than "Has schema changes".

### Edge Cases

- **Default branch itself**: querying either field on the default branch returns
  `false` (it cannot differ from itself). Behavior is identical for both fields.
- **Branch with no computed schema state**: if a branch has no schema hash yet,
  both fields return `false` rather than erroring.
- **Origin branch state unavailable**: if the origin/default branch's schema
  state cannot be resolved, both fields return `false`, matching today's
  behavior.
- **Consumer requests both fields in one query**: both resolve and always agree.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The branch API MUST expose a new boolean field named
  `schema_differs_from_default_branch` that reports whether a branch's schema
  differs from the branch it was created from. The field MUST be present on every
  representation that exposes `has_schema_changes` today: both the legacy `Branch`
  query type and the `InfrahubBranch` query type, and the branch objects returned
  in mutation payloads (e.g. branch create and branch rebase).
- **FR-002**: `schema_differs_from_default_branch` MUST return exactly the same
  value as `has_schema_changes` for every branch state, for as long as both
  fields coexist.
- **FR-003**: The existing `has_schema_changes` field MUST be retained and
  continue to return its current value (no behavior change) throughout the
  deprecation window.
- **FR-004**: `has_schema_changes` MUST be marked deprecated in a
  machine-readable way, discoverable through normal API introspection, on every
  representation that exposes it (both the `Branch` and `InfrahubBranch` types).
- **FR-005**: The deprecation on `has_schema_changes` MUST carry a single,
  consumer-visible message that both (a) names `schema_differs_from_default_branch`
  as its replacement and (b) states that the field is scheduled for removal in
  Infrahub 1.14.0. The removal version MUST be part of this message, not a
  separate notice.
- **FR-006**: Infrahub's own web UI MUST query and consume
  `schema_differs_from_default_branch` instead of the deprecated field. The
  indicator MUST appear in the same positions as today (branch list badge, branch
  detail attribute), but its wording MUST be updated from the current misleading
  copy ("schema updated" badge, "Has schema changes" label) to wording that
  conveys the schema differs from the default branch. The replacement text MUST
  fit the existing badge and label layout in the same way the current text does
  (e.g. a short "schema differs from default" / "differs from default branch"),
  not force a layout change.
- **FR-009**: The backend MUST expose a `schema_differs_from_default_branch`
  property on the branch model returning the same value as the existing
  `has_schema_changes` property, and Infrahub's own internal backend consumers of
  the property MUST read it through the new name. The old property MUST be
  retained (delegating to the same computation) so it keeps working for the
  deprecation window. Renaming the GraphQL field alone is not sufficient because
  the GraphQL layer resolves the field from a same-named model property.
- **FR-010**: Existing automated tests that assert `has_schema_changes` (backend
  GraphQL branch query tests, schema-lifecycle integration tests, and frontend
  branch fixtures/tests) MUST be updated or extended so the new field is covered
  and the old field's continued parity is verified while both exist.
- **FR-007**: The change MUST be documented for users, including a changelog
  entry noting the new field, the deprecation, and the planned removal version.
- **FR-008**: The renamed field MUST be reflected in generated API schema
  artifacts so external consumers can discover it through normal introspection.

### Out of Scope

- **OOS-001**: The Python SDK is explicitly out of scope for this feature. The
  SDK must not be changed here, so that it does not start requiring the latest
  Infrahub version. SDK adoption of the new field (it consumes `has_schema_changes`
  in `infrahub_sdk/branch.py` and `infrahub_sdk/ctl/branch.py`) MUST be tracked in
  a separate follow-up ticket that exists before this feature is considered done,
  and shipped on a deliberate delay.
- **OOS-002**: No new capability to distinguish "schema changed in this branch"
  from "schema changed on the default branch" is introduced. That is a distinct
  feature; this work only renames and clarifies the existing divergence check.
- **OOS-003**: The underlying divergence computation is not changing; this is a
  naming, deprecation, and consumer-migration effort, not a logic change.
- **OOS-004**: The identically named but unrelated internal merge methods (the
  `SchemaAnalyzer.has_schema_changes()` method and its callers in the graph-merge
  and orchestration layers) are NOT part of this feature. They compare a diff, not
  a branch against the default, and MUST NOT be renamed here. Only the branch
  model property and the branch GraphQL field are in scope.
- **OOS-005**: Actually removing `has_schema_changes` is out of scope for this
  feature. The removal MUST be captured in a separate follow-up ticket pinned to
  the 1.14.0 milestone so the deprecation does not outlive its stated removal
  version; that ticket must exist before this feature is considered done.

### Key Entities

- **Branch**: a versioned line of change in Infrahub. Relevant attribute is the
  boolean that reports whether its schema differs from the branch it was created
  from. This feature adds a clearly named representation of that same attribute
  and deprecates the old one.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of branch states, `schema_differs_from_default_branch` and
  `has_schema_changes` return identical values while both exist.
- **SC-002**: A consumer inspecting the API can, without reading source code,
  determine that `has_schema_changes` is deprecated, what replaces it, and when
  it will be removed.
- **SC-003**: Zero first-party Infrahub web UI requests reference the deprecated
  `has_schema_changes` field after this feature ships.
- **SC-006**: The web UI no longer displays the misleading "schema updated" /
  "Has schema changes" wording; the schema-divergence indicator instead reads as a
  difference from the default branch, in the same badge and label positions.
- **SC-004**: Existing queries that still use `has_schema_changes` continue to
  succeed with no change in returned values (zero breakage during the deprecation
  window).
- **SC-005**: The new field name and the deprecation of the old field are
  discoverable in the published documentation and changelog for the release that
  ships this change.

## Assumptions

- The delivery vehicle is epic **IFC-2281**; INFP-469 is the originating
  discovery idea.
- The value returned by the new field is exactly today's `has_schema_changes`
  value; naming is the only thing being clarified, not semantics.
- Infrahub already supports marking an API field as deprecated with a reason (the
  same mechanism used for other deprecated branch fields), so no new deprecation
  infrastructure is required.
- "Removed in Infrahub 1.14.0" means the old field remains fully functional in
  every release up to 1.14.0 and is deleted in 1.14.0. This target is chosen
  against the current 1.11 development line, leaving roughly three minor releases
  as the deprecation window.
- The UI copy change is a first-party wording correction, not a behavior change:
  the indicator appears for the same branches, in the same places, as before. The
  existing deprecation mechanism (a graphene `deprecation_reason`, as already used
  for other deprecated branch fields such as `is_isolated`) is sufficient; no new
  deprecation infrastructure is required.
- Backend and frontend land together in this feature; the SDK follows separately
  so the SDK does not become coupled to the latest Infrahub release.
- Demo content and examples that reference the old field, if any, are treated as
  documentation follow-ups and are not required for this feature to be complete.
