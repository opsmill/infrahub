# Feature Specification: Search Anywhere Display Label Enrichment

**Feature Branch**: `005-search-display-label`
**Created**: 2026-04-16
**Status**: Draft
**Input**: User description: "Enrich search anywhere with display_label for Schema/Internal nodes, linking to schema page"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Look up Schema Node from pipeline error (Priority: P1)

A platform operator sees a uniqueness constraint error in a CI pipeline check. The error message contains a SchemaNode UUID. The operator copies this UUID and pastes it into the "search anywhere" bar to understand which schema entity is involved. The search returns a result showing the schema node's human-readable name (e.g., "InfraDevice") and kind ("SchemaNode"). Clicking the result navigates to the schema page with that schema entry selected.

**Why this priority**: This is the primary use case driving the feature. Without it, operators cannot trace pipeline errors involving schema UUIDs back to the schema definition.

**Independent Test**: Can be fully tested by searching for a known SchemaNode UUID and verifying that a meaningful result appears and links to the correct schema page entry.

**Acceptance Scenarios**:

1. **Given** a SchemaNode exists with a known UUID, **When** the user searches for that UUID in "search anywhere", **Then** the search returns a result showing the node's display label and kind.
2. **Given** a search result for a SchemaNode is displayed, **When** the user clicks the result, **Then** the browser navigates to `/schema?kind={kind}` with the matching schema entry selected.
3. **Given** a SchemaNode UUID is searched, **When** the result is rendered, **Then** the result shows a simplified view (display label + kind badge) without attempting to fetch full object details.

---

### User Story 2 - Regular node search remains unchanged (Priority: P1)

A user searches for a regular node (e.g., InfraDevice, CoreInterface) by UUID or text. The search results render with full object details exactly as they do today: label, attributes, relationships, and a link to the object detail page.

**Why this priority**: Equal to P1 because any regression in the existing search behavior would break the most common workflow.

**Independent Test**: Can be tested by searching for a regular node UUID and verifying the result still shows full details and links to the object detail page.

**Acceptance Scenarios**:

1. **Given** a regular node exists, **When** the user searches by UUID, **Then** the result renders with full object details (display label, attributes, relationships) and links to the object detail page.
2. **Given** a regular node exists, **When** the user searches by text (name, attribute value), **Then** results render identically to the current behavior.

---

### User Story 3 - Internal namespace node search (Priority: P2)

A user searches for an Internal namespace node UUID (e.g., InternalWidget). The search returns a result with a display label and kind, similar to Schema nodes. Clicking navigates to the schema page.

**Why this priority**: Lower than P1 because Internal namespace UUIDs appear in error messages less frequently, but the same mechanism should handle both Schema and Internal namespaces consistently.

**Independent Test**: Can be tested by searching for a known Internal namespace node UUID and verifying behavior matches SchemaNode handling.

**Acceptance Scenarios**:

1. **Given** an Internal namespace node exists with a known UUID, **When** the user searches for that UUID, **Then** the search returns a result with the node's display label and kind.
2. **Given** the search result is for an Internal namespace node, **When** the user clicks the result, **Then** the browser navigates to the schema page.

---

### Edge Cases

- What happens when a SchemaNode UUID is searched but the node has been deleted (e.g., after a schema migration)? The search should return no results, same as any deleted node.
- What happens when the search returns a mix of regular nodes and Schema/Internal nodes? Both types should render in the same results list, each with their appropriate presentation and link target.
- What happens when a Schema/Internal node has no display_label? The result should fall back to showing the kind and UUID.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The search API MUST return Schema and Internal namespace nodes when searching by UUID, instead of filtering them out.
- **FR-002**: The search API MUST include a `display_label` field in search results for UUID-based matches.
- **FR-003**: The `display_label` field MUST contain the human-readable name of the node as defined by the node's display label configuration.
- **FR-004**: The `display_label` field MUST be nullable — text-based search results may omit it.
- **FR-005**: The search UI MUST render Schema and Internal namespace nodes with a simplified presentation showing the display label and kind.
- **FR-006**: The search UI MUST link Schema and Internal namespace nodes to the schema page with the kind pre-selected via query parameter.
- **FR-007**: The search UI MUST NOT attempt to fetch full object details for nodes whose kind is not in the frontend schema registry.
- **FR-008**: Existing search behavior for regular nodes (text search, UUID search, rendering, navigation) MUST remain unchanged.

### Key Entities

- **Search Result**: Represents a matched node in search. Attributes: id (UUID), kind (string), display_label (nullable string).
- **Schema/Internal Node**: A node belonging to the "Schema" or "Internal" namespace. Not present in the frontend schema registry. Must be rendered with simplified presentation and linked to the schema page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Searching for a SchemaNode UUID returns a visible, clickable result with a human-readable label (currently returns nothing or crashes).
- **SC-002**: Clicking a SchemaNode search result navigates to the schema page with the correct entry selected.
- **SC-003**: Searching for a regular node by UUID continues to show full object details and link to the object detail page (zero regressions).
- **SC-004**: The search result for Schema/Internal nodes renders without additional network requests beyond the initial search query.

## Assumptions

- The `display_label` enrichment only applies to UUID-based searches. Text-based searches already filter to `InfrahubKind.NODE` and `InfrahubKind.GENERICGROUP`, so Schema/Internal nodes are not returned by that path.
- The schema page's existing `kind` query parameter support is sufficient for deep-linking to a specific schema entry.
- Schema and Internal namespace nodes both use the same simplified rendering and navigation target (the schema page).
