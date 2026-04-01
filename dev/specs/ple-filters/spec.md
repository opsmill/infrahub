# Feature Specification: Unified Filter Menu with Metadata Filters

**Feature Branch**: `infp-518-frontend-filter-refactor`  
**Created**: 2026-04-01  
**Status**: Draft  
**Input**: User description: "Add unified filter menu with metadata filters (created_at, created_by, updated_at, updated_by) for table list views. Filters opened via a single button next to the search bar, with hover-to-preview and active filter display."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open filter menu and apply an attribute filter (Priority: P1)

A user viewing a list of objects wants to narrow results by a specific attribute. They click a "Filter" button next to the search bar, which opens a menu listing all available filters (attributes and relationships from the schema). Hovering over a filter item reveals the existing attribute or relationship filter form inline. The user fills in the filter criteria and applies it.

**Why this priority**: This is the core interaction pattern that replaces the current filter UX. All other stories build on top of this menu-based approach.

**Independent Test**: Can be fully tested by opening the filter menu, hovering over an attribute filter, filling in a value, and verifying the table updates with filtered results.

**Acceptance Scenarios**:

1. **Given** a user is on a list view with objects, **When** they click the filter button next to the search bar, **Then** a menu appears listing all available filters grouped by type (attributes, relationships).
2. **Given** the filter menu is open, **When** the user hovers over an attribute filter item, **Then** the corresponding attribute filter form appears (reusing the existing component).
3. **Given** the filter form is displayed for an attribute, **When** the user fills in filter criteria and submits, **Then** the filter is applied, the table updates, and the menu closes.

---

### User Story 2 - View and manage active filters (Priority: P1)

After applying one or more filters, the user sees active filters displayed below the filter button/search bar area (consistent with current behavior). Each active filter shows the field name and current value. Clicking an active filter opens the filter form to update it. Each active filter has a remove icon to clear it.

**Why this priority**: Active filter management is essential for usability — users need to see, modify, and remove filters without starting over.

**Independent Test**: Can be tested by applying a filter, verifying it appears as an active tag below the toolbar, clicking it to modify, and clicking the remove icon to clear it.

**Acceptance Scenarios**:

1. **Given** one or more filters are active, **When** the user looks below the filter button area, **Then** each active filter is displayed as a tag showing the field name and value.
2. **Given** an active filter tag is displayed, **When** the user clicks on it, **Then** the filter form for that field opens with the current value pre-filled.
3. **Given** an active filter tag is displayed, **When** the user clicks the remove icon on the tag, **Then** that filter is removed and the table updates.
4. **Given** multiple filters are active, **When** the user removes one filter, **Then** the remaining filters stay active and the table updates accordingly.

---

### User Story 3 - Filter by node metadata (Priority: P2)

A user wants to find objects based on when or by whom they were created or last modified. The filter menu includes metadata fields: created_at, created_by, updated_at, updated_by. These metadata filters use the same filter form patterns as regular attributes (date picker for timestamps, relationship selector for user references).

**Why this priority**: Metadata filtering is the new capability being added. It depends on the unified filter menu (P1) being in place.

**Independent Test**: Can be tested by opening the filter menu, selecting "Created At", using the date picker to set a date range, and verifying the table shows only objects matching that criteria.

**Acceptance Scenarios**:

1. **Given** a user opens the filter menu, **When** they look at available filters, **Then** metadata filters (created_at, created_by, updated_at, updated_by) are listed alongside schema-defined filters.
2. **Given** the user hovers over "Created At" or "Updated At", **When** the filter form appears, **Then** it provides a date range picker (reusing the existing date filter form).
3. **Given** the user hovers over "Created By" or "Updated By", **When** the filter form appears, **Then** it provides a user/account selector (reusing the existing relationship filter form).
4. **Given** the user applies a metadata filter, **When** the filter is active, **Then** it appears as an active filter tag alongside any other active filters.

---

### User Story 4 - Apply relationship filter from menu (Priority: P2)

A user wants to filter objects by a relationship field. They open the filter menu, hover over a relationship filter, and the existing relationship filter form appears. They select one or more related objects and apply the filter.

**Why this priority**: Relationship filters already work today but need to be accessible through the new unified menu.

**Independent Test**: Can be tested by opening the filter menu, hovering over a relationship filter, selecting related objects, and verifying filtered results.

**Acceptance Scenarios**:

1. **Given** the filter menu is open, **When** the user hovers over a relationship filter, **Then** the relationship filter form appears with a searchable combobox.
2. **Given** the user selects related objects and applies the filter, **When** the filter is active, **Then** the table shows only objects matching that relationship and the filter appears as an active tag.

---

### Edge Cases

- What happens when the schema has no filterable attributes or relationships? The filter menu should still show metadata filters (created_at, created_by, updated_at, updated_by) and any applicable suggested filters.
- What happens when the user applies a filter that returns zero results? The table should show an empty state with the active filters still visible so the user can modify or remove them.
- What happens when the user navigates away and comes back? Filters are persisted in query string parameters and should be restored.
- What happens on schemas with a very large number of attributes/relationships? The filter menu should be scrollable.
- What happens when the user applies both a search term and filters simultaneously? Both should be applied together (AND logic), consistent with current behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a single filter button next to the search bar in list view toolbars. This is the sole entry point for adding and editing filters.
- **FR-001b**: Table column headers MUST no longer be clickable filter triggers. They remain as display-only headers showing a filter icon when a filter is active on that column.
- **FR-002**: System MUST open a menu listing all available filters when the filter button is clicked. Filters MUST be grouped by type in this order: suggested filters (if applicable), metadata filters, attributes, relationships.
- **FR-003**: The filter menu MUST list all filterable attribute and relationship fields as determined by existing visibility/kind logic (attributes visible in list view by kind, relationships by kind/cardinality).
- **FR-004**: The filter menu MUST include metadata filters: created_at, created_by, updated_at, updated_by.
- **FR-004b**: The filter menu MUST include suggested filters (e.g., IPAM availability) as menu items. Clicking a suggested filter directly applies it (same as current suggested filter tag behavior).
- **FR-005**: When a user hovers over a filter menu item, the system MUST display the appropriate filter form (attribute filter form for attributes, relationship filter form for relationships) inline or as a submenu.
- **FR-006**: The filter forms displayed on hover MUST reuse the existing attribute filter and relationship filter components.
- **FR-007**: When a filter is applied, the system MUST display it as an active filter tag below the search bar / filter button area.
- **FR-008**: When a user clicks an active filter tag, the system MUST display the filter form with the current value pre-filled so the user can update it.
- **FR-009**: Each active filter tag MUST have a remove icon that clears that specific filter.
- **FR-010**: Filters MUST continue to be persisted in URL query string parameters.
- **FR-011**: The filter menu MUST be scrollable when the number of available filters exceeds the visible area.
- **FR-012**: Metadata timestamp filters (created_at, updated_at) MUST use the existing date range filter form.
- **FR-013**: Metadata user filters (created_by, updated_by) MUST use the existing relationship filter form targeting account/user entities.

### Key Entities

- **Filter**: A name-value pair representing a single filter condition (e.g., `{name: "status__value", value: "active"}`). Stored in URL query string parameters.
- **Filter Menu**: A new UI component that lists all available filters for the current schema, including metadata filters, organized in a browsable menu.
- **Metadata Filter Fields**: Virtual filter fields (created_at, created_by, updated_at, updated_by) that are not part of the schema definition but are available on all nodes.
- **Suggested Filters**: Special toggle filters (e.g., IPAM availability) that apply a predefined filter condition when clicked. These are context-dependent (only shown for applicable schemas).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can access all available filters for a list view within 2 clicks (click filter button, hover/click filter).
- **SC-002**: Users can apply a metadata filter (created_at, created_by, updated_at, updated_by) from any list view.
- **SC-003**: Users can modify an active filter by clicking on its tag without needing to remove and re-add it.
- **SC-004**: All existing filter functionality (attribute filters, relationship filters, search, filter persistence in URL) continues to work after the refactor.
- **SC-005**: The filter menu correctly displays all filterable fields for schemas with up to 50+ attributes and relationships without layout issues.

## Clarifications

### Session 2026-04-01

- Q: Which attributes/relationships should appear in the filter menu? → A: Use the same existing logic that determines filterable fields (attributes visible in list view by kind + display, relationships by kind/cardinality). No new computation needed.
- Q: Should suggested filters (e.g., IPAM availability) be in the menu? → A: Yes, suggested filters must also be available in the filter menu, not only as standalone tags.
- Q: Which metadata fields? → A: All four: created_at, created_by, updated_at, updated_by.
- Q: What happens to existing column header filter popovers? → A: Remove clickable filter trigger from column headers. Headers remain visible (with filter icon indicator when active) but are no longer interactive. The filter menu is the sole entry point for adding/editing filters.
- Q: How should filter menu items be grouped/ordered? → A: Grouped by type: suggested filters first, then metadata, then attributes, then relationships.

## Assumptions

- The backend already supports filtering by metadata fields (created_at, created_by, updated_at, updated_by) in GraphQL queries. If not, backend support will need to be added separately.
- Metadata user fields (created_by, updated_by) reference account/user entities that can be queried via the existing relationship filter pattern.
- The existing `AttributeFilterForm` and `RelationshipFilterForm` components can be rendered inside a menu/popover context without modification to their core logic.
- The "hover to show filter form" interaction will use a submenu or flyout pattern (hover on menu item reveals the form to the side), not a tooltip.
