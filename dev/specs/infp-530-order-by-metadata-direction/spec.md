# Feature Specification: Schema-level `order_by` for node metadata and direction

**Feature Branch**: `infp-530-schema-order-by-metadata`
**Created**: 2026-05-08
**Status**: Implemented
**Input**: User description: "Enable order_by schema attribute to support node metadata fields with explicit sort direction"
**Source ticket**: [INFP-530](https://opsmill.atlassian.net/browse/INFP-530)
**Customer**: University of Melbourne

## Clarifications

### Session 2026-05-11

- Q: When two items share the same value on the schema-level `order_by` field (e.g., two documentation notes created in the same millisecond), what is their relative order? → A: Always append `node.uuid` ascending as an implicit final tiebreaker on all three list paths (top-level, relationship-peer, hierarchy) whenever `order_by` is in effect; this also standardizes today's inconsistency where only the top-level path appends UUID.
- Q: Should the hierarchy listing path have an explicit acceptance scenario locking in FR-008's hierarchy claim? → A: Yes — add a hierarchy acceptance scenario to Story 1 alongside the existing top-level and relationship-target scenarios.
- Q: How should generic inheritance of `order_by` (including the new metadata + direction syntax) behave? → A: Lock in existing behavior — a generic's `order_by` is inherited by a concrete kind only when the concrete doesn't define its own; the new syntax inherits identically.
- Q: What is the literal author-facing string form for metadata and direction in `order_by`? → A: `node_metadata__<field>__<direction>` where `<field> ∈ {created_at, updated_at}` and `<direction> ∈ {asc, desc}` (direction optional, defaults to `asc`). Regular-attribute direction uses the same `__` separator: `<attr>__value__<direction>`.
- Q: How should the running example schema be named to make it clear it is user-defined and namespaced? → A: Rename `Notes` to `DocumentationNote` throughout the spec (namespace `Documentation`, kind `Note`). Prose references to instances use lowercase "documentation note(s)".
- Q: The example currently says "ordering by creation timestamp", which is ambiguous — could be read as a user-defined attribute. Should the spec be explicit that the customer scenario orders on the **node-level metadata** Infrahub already tracks on every node? → A: Yes — make explicit throughout that the ordering target is the node-level `created_at` / `updated_at` metadata (not a user-defined attribute on `DocumentationNote`), and show the literal `node_metadata__created_at__desc` form in the Story 1 Independent Test. This is what unlocks ordering of related (peer) nodes by node-level metadata for the customer's relationship-list scenario.
- Q: Should Story 1 explicitly own the introduction of the full syntax — `node_metadata__{field}__{asc|desc}` and `{attribute}__value__{asc|desc}` — including the default-ascending rule when no direction suffix is provided, even though Story 2 motivates the descending-on-attributes use case? → A: Yes — Story 1 introduces the complete syntax (metadata entries and regular-attribute entries, optional direction suffix, default `asc`). Story 2 keeps the motivating descending-on-attributes example. Story 1 acceptance scenarios cover (a) default-ascending behavior when direction is omitted and (b) that the same direction syntax applies to regular attributes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Default newest-first ordering on a relationship list (Priority: P1)

A schema designer maintains a user-defined `DocumentationNote` schema that is attached to many parent objects through a many-cardinality relationship. The `DocumentationNote` schema itself has no user-defined timestamp attribute; the customer wants to sort on the **node-level `created_at` metadata** that Infrahub automatically tracks on every node. They want every list view of `DocumentationNote` — whether on the parent's detail page, in the API, or in any UI tab — to default to "newest first" without each query having to specify the order. Today they must pass the node-metadata-based ordering at query time on every read; the UI does not, so the documentation notes appear in an unhelpful order.

**Syntax introduced by this story (foundational deliverable)**:

- Node-metadata entry: `node_metadata__<field>__<direction>` where `<field> ∈ {created_at, updated_at}` and `<direction> ∈ {asc, desc}`.
- Regular-attribute entry: `<attribute>__value__<direction>` (the existing `__value` attribute-path convention, now optionally suffixed with direction).
- The `<direction>` suffix is OPTIONAL on both metadata and regular-attribute entries. When omitted, the direction defaults to **ascending** (`asc`). All `order_by` entries already in the wild (no direction suffix) therefore continue to behave as ascending without any schema change.
- Story 1 delivers this complete syntax surface. Story 2 motivates a P2 use case (descending on regular attributes) that consumes the same syntax.

**Why this priority**: This is the customer's real, blocking pain. Users cannot tell at a glance which documentation note is most recent, which makes the feature unusable for its intended purpose. The fix lives entirely at the schema-definition level, so it's a single edit that propagates to every consumer.

**Independent Test**: Define a `DocumentationNote` schema with no user-defined timestamp attribute, whose `order_by` is exactly `["node_metadata__created_at__desc"]` — referencing the node-level `created_at` metadata that Infrahub already tracks on every node, not a user-defined attribute on the schema. Attach two documentation notes to a parent object at different times. Open the parent's detail page; verify the most-recent documentation note appears first. Verify the same ordering holds when fetching the parent's documentation notes through the API without any per-query ordering argument. Then verify the default-ascending behavior by reloading the same schema with `order_by: ["node_metadata__created_at"]` (no direction suffix) — the oldest documentation note must now appear first. Finally, on any schema with a regular text attribute, verify that `<attribute>__value__desc` returns reverse-alphabetical order and `<attribute>__value` returns alphabetical order — confirming the direction suffix is optional, applies identically to regular attributes, and defaults to ascending. This also confirms that ordering of related (peer) nodes uses the peer schema's `order_by` and therefore honors the new node-metadata syntax.

**Acceptance Scenarios**:

1. **Given** a schema declares `order_by: ["node_metadata__created_at__desc"]` (newest-first on the node-level `created_at` metadata), **When** the API or UI lists items of that schema (top-level or as a relationship target), **Then** the most recently created item appears first.
2. **Given** a schema declares `order_by: ["node_metadata__updated_at__desc"]` (newest-first on the node-level `updated_at` metadata), **When** an existing item is modified, **Then** that item moves to the top of subsequent listings.
3. **Given** a schema with no explicit `order_by`, **When** items are listed, **Then** the default ordering remains identical to today (no regression).
4. **Given** a hierarchical schema (parent/child) declares `order_by: ["node_metadata__created_at__desc"]`, **When** children are listed by traversing the hierarchy, **Then** the most recently created child appears first — identically to the top-level and relationship-peer paths.
5. **Given** a schema declares `order_by: ["node_metadata__created_at"]` with no direction suffix, **When** items are listed, **Then** they are returned in ascending order of `created_at` (oldest first) — confirming the implicit-ascending default for metadata entries.
6. **Given** a schema declares `order_by: ["name__value__desc"]` on a regular text attribute, **When** items are listed, **Then** they are returned in reverse-alphabetical order — confirming the same direction syntax applies to regular attributes as to node-metadata entries.
7. **Given** a schema declares `order_by: ["name__value"]` on a regular text attribute with no direction suffix, **When** items are listed, **Then** they are returned in ascending alphabetical order — confirming the implicit-ascending default for regular-attribute entries and preserving the behavior of every `order_by` already in the wild.

---

### User Story 2 - Schema designer chooses ascending or descending order (Priority: P2)

A schema designer wants to declare descending order on regular attributes — for example, listing devices alphabetically reverse, or invoices by largest amount first — directly in the schema, not in every individual query.

**Why this priority**: The customer flagged this as a "nice to have" companion to story 1, but it's the same syntactic surface and only marginal additional cost. Without it, descending ordering remains a per-query concern even for fields where the schema author already knows the natural sort order. The customer also explicitly proposed direction syntax for both metadata and regular attributes, so excluding regular attributes would be inconsistent.

**Independent Test**: Define a schema where `order_by` declares descending order on a regular text attribute. Create three items with names "alpha", "bravo", "charlie". Verify a list query returns them in reverse-alphabetical order without any per-query ordering argument.

**Acceptance Scenarios**:

1. **Given** a schema declares descending order on a regular attribute, **When** items are listed, **Then** results are returned in descending order of that attribute.
2. **Given** a schema declares ascending order explicitly, **When** items are listed, **Then** results match the implicit-ascending behavior.
3. **Given** a schema declares ordering by multiple fields with mixed directions, **When** items are listed, **Then** the primary sort uses the first entry's direction and the secondary sort uses the second entry's direction.

---

### User Story 3 - Strict validation surfaces schema mistakes early (Priority: P3)

A schema author makes a typo in their `order_by` declaration — for example, references a metadata field that doesn't exist, or uses a malformed direction suffix. They want the schema load to fail fast with a clear, actionable error message that names the offending node and field.

**Why this priority**: Without strict validation, malformed entries silently degrade to default ordering at runtime, leaving authors confused about why their declared ordering "doesn't work". Catching the error at schema load is cheap and prevents production confusion.

**Independent Test**: Attempt to load a schema with each of the rejection cases below; verify each one raises a descriptive error at schema-load time citing the offending node and entry.

**Acceptance Scenarios**:

1. **Given** an `order_by` entry references an unsupported metadata field, **When** the schema is loaded, **Then** loading fails with an error naming the entry and listing supported fields.
2. **Given** an `order_by` entry uses a malformed direction token (e.g., `__descending`), **When** the schema is loaded, **Then** loading fails with an error stating only `asc` and `desc` are valid.
3. **Given** a schema defines an attribute or relationship literally named `node_metadata`, **When** the schema is loaded, **Then** loading fails with an error stating the name is reserved.
4. **Given** an `order_by` list contains the same field twice with conflicting directions, **When** the schema is loaded, **Then** loading fails with an error pointing to the conflict.

---

### Edge Cases

- **Reserved name conflict on existing data**: If an existing deployed schema already has an attribute or relationship literally named `node_metadata`, the upgrade will fail at schema load. The release notes must call this out and instruct authors to rename.
- **Query-time ordering combined with schema default**: When the API caller passes an explicit ordering argument, the schema's declared `order_by` is ignored entirely (not stacked as a tiebreaker). This is a behavior change from today, where the two stacked. It must be documented in the changelog and the ordering-argument description.
- **Backward compatibility**: All existing `order_by` entries (without direction suffix) continue to behave as ascending — no schema in the wild needs to change syntax to keep working.
- **Empty list**: An empty `order_by` list is treated identically to an absent `order_by` (no schema-level ordering applied), unchanged from today.
- **Relationship-peer ordering**: When listing the targets of a many-cardinality relationship, the peer schema's `order_by` is the source of truth. There is no per-relationship override syntax; if two relationships should sort differently, the difference must be expressed via separate target schemas or via per-query ordering.
- **Tie behavior on equal sort values**: Whenever schema-level `order_by` is in effect, the node UUID is appended as an implicit final ascending tiebreaker so pagination is deterministic. This also corrects an existing inconsistency: today the top-level node-list path appends UUID, but the relationship-peer and hierarchy paths do not, which can cause the customer's "newest-first" `DocumentationNote` list to shuffle on millisecond-equal timestamps.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The schema definition MUST accept entries in `order_by` that reference the node-level `created_at` and `updated_at` metadata fields (automatically tracked by Infrahub on every node, distinct from any user-defined attribute) using the literal form `node_metadata__<field>` where `<field>` is one of `created_at` or `updated_at`. The `node_metadata` prefix is reserved and distinguishes metadata fields from attribute names.
- **FR-002**: The schema definition MUST accept an optional `__asc` or `__desc` suffix on any `order_by` entry, applicable identically to metadata entries (e.g., `node_metadata__created_at__desc`) and regular-attribute entries (e.g., `name__value__desc`). The `__` separator matches the existing `order_by` convention.
- **FR-003**: When no direction marker is specified, the default direction MUST be ascending. This MUST be true for all existing `order_by` entries to preserve current behavior.
- **FR-004**: The schema validator MUST reject `order_by` entries that reference metadata fields other than the supported set, with an error message naming the entry and listing the supported fields.
- **FR-005**: The schema validator MUST reject any schema where an attribute or relationship is literally named `node_metadata`, with an error message identifying the offending node and instructing the author to rename.
- **FR-006**: The schema validator MUST reject `order_by` lists containing duplicate entries for the same field (whether direction is implicit or explicit) and entries that conflict on direction for the same field.
- **FR-007**: The schema validator MUST reject malformed direction markers, accepting only the two reserved direction tokens.
- **FR-008**: Schema-level `order_by` MUST be honored consistently across all three places where node lists are returned to a caller: top-level node listings, relationship-peer listings, and hierarchy listings.
- **FR-009**: When a query specifies an explicit ordering argument, the schema-level `order_by` MUST be ignored entirely for that query (no stacking, no tiebreaker fallback).
- **FR-010**: The set of metadata fields supported in schema `order_by` MUST be the same as the set supported by the existing query-time ordering input — the node-level `created_at` and `updated_at` metadata fields automatically tracked by Infrahub on every node (not user-defined attributes).
- **FR-011**: All schema-load-time validation errors raised by this feature MUST cite the offending node, the offending entry, and provide a remediation hint specific to the violation.
- **FR-012**: Existing schemas that load and behave correctly today MUST continue to load and behave identically after this change, with the single exception of schemas that use the now-reserved `node_metadata` name.
- **FR-013**: Whenever schema-level `order_by` is in effect, all three list paths (top-level, relationship-peer, hierarchy) MUST append the node UUID as an implicit final ascending tiebreaker, so listings are deterministic and pagination is stable across requests.

### Key Entities

- **Schema `order_by` entry**: A string declared by schema authors that names a sortable target — either an attribute property path, a relationship-attribute path, or a node-metadata reference — optionally suffixed with a direction marker. Multiple entries form an ordered list where each subsequent entry acts as a secondary sort.
- **Node metadata reference**: A reserved-namespace path of the literal form `node_metadata__<field>` where `<field>` is one of `created_at` or `updated_at`. Distinct from attribute paths via the reserved `node_metadata` prefix to avoid name collisions. The field set matches the existing query-time `order: { node_metadata: { ... } }` GraphQL input.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A schema author can configure newest-first default ordering on a node by adding a single line to the schema definition, without modifying any query code or UI code.
- **SC-002**: For the customer's primary use case (`DocumentationNote` instances attached to parent objects via a many-cardinality relationship), the parent's documentation notes list renders in newest-first order through every consumer (UI, API, SDK) once the schema is updated, with zero per-query ordering arguments.
- **SC-003**: 100% of malformed `order_by` entries (unsupported metadata field, invalid direction token, duplicate or conflicting entries, reserved-name attribute) produce an actionable schema-load-time error that names the offending node and entry.
- **SC-004**: 100% of existing schemas that load successfully today continue to load successfully and produce identical query results after the change, with the only exception being schemas that use the reserved `node_metadata` name.
- **SC-005**: A new descending-order requirement on a regular attribute can be expressed at the schema level instead of in every consumer, eliminating the per-query ordering argument from at least the top-level listing path, the relationship-peer path, and the hierarchy path.

## Assumptions

- Only the node-level `created_at` and `updated_at` metadata fields (automatically tracked by Infrahub on every node) are in scope for metadata-based ordering. Ordering by user-reference metadata (creator, last modifier) is explicitly out of scope: the data is a UUID reference whose ordering is not human-meaningful, and the customer did not request it. Ordering by user-defined attributes on the schema (e.g., a custom `published_at` field added by the author) is already supported today and is not the subject of this feature.
- The reserved tokens (`node_metadata`, `asc`, `desc`) carry near-zero collision risk in practice. The hard-fail-at-load approach is acceptable because the probability of an existing schema using these as attribute or relationship names is empirically negligible. Should a real conflict surface, the remediation is a one-time rename that the validator's error message will clearly direct.
- Per-relationship ordering overrides (declaring different sort orders per relationship even when both target the same node type) are out of scope. The peer schema's `order_by` remains the single declarative knob; per-query ordering is the escape hatch for divergent needs.
- Cross-relationship metadata ordering (e.g., ordering peers by attributes of the relationship itself, or by metadata of a chained relationship) is out of scope.
- Frontend list rendering inherits the new behavior automatically because all list views consume backend-ordered results. No frontend logic changes are required for this feature.
- The query-time ordering input shape exposed to API callers does not change. Only its precedence relative to the schema-level default changes — and only in cases where both are present and reference the same field.
- This is a backend-and-schema feature. The Python SDK and frontend code do not interpret `order_by` strings; they pass the string list through and consume backend-ordered results. No SDK or frontend code changes are part of this spec.
- Generic inheritance of `order_by` follows existing behavior: a generic's `order_by` is inherited by a concrete kind only when the concrete does not define its own. The new metadata + direction syntax inherits identically. No new inheritance logic is introduced.
