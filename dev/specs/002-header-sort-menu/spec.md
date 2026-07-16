# Feature Specification: Column-Header Sort & Filter Menu

**Feature Branch**: `header-sort-menu-ifc-2794`

**Created**: 2026-07-16

**Status**: Draft

**Source ticket**: [IFC-2794](https://opsmill.atlassian.net/browse/IFC-2794)

**Input**: User description: "We want to sort using columns of data table. When clicking on column headers, it displays a menu to select between filtering and sorting."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sort a list from a column header (Priority: P1)

A user viewing a list of objects wants to reorder it by one of the visible columns. They click the column header, which opens a menu offering "Sort ascending", "Sort descending", and "Filter…". Selecting a sort direction reorders the whole list by that column, shows a direction indicator on the header, and is reflected in the page URL so the view survives reload and link-sharing. Selecting the already-active direction again clears the custom sort and returns the list to its default order. The "Filter…" item opens the same per-column filter form users get from the header today, so no existing capability is lost.

**Why this priority**: Sorting is the new capability and the core of the idea. Today sorting is only reachable through a separate toolbar control that users don't associate with the column they are looking at. This story alone delivers the full value for the most common case (sorting by a regular column) while preserving the existing header filtering entry point.

**Independent Test**: On any object list, click a text column's header, choose "Sort descending", and verify the list reorders newest-value-first with a ↓ indicator on the header and the sort captured in the URL. Reload the page and verify the order persists. Click the header again, choose "Sort descending" a second time, and verify the list returns to its default order and the indicator disappears. Open the menu and choose "Filter…", apply a value, and verify the list narrows exactly as header filtering does today.

**Acceptance Scenarios**:

1. **Given** an object list with a sortable column, **When** the user clicks the column header and selects "Sort descending", **Then** the list reorders by that column descending, the header shows a ↓ indicator, and the sort is captured in the URL.
2. **Given** a custom sort is active on a column, **When** the user opens that column's header menu, **Then** the active direction is visibly marked as selected.
3. **Given** a custom sort is active on a column, **When** the user selects the already-active direction again, **Then** the custom sort is cleared, the list returns to its default order, and the header indicator disappears.
4. **Given** a multi-field sort was previously built in the toolbar sort control, **When** the user selects a sort direction from any column header, **Then** the entire sort is replaced by a single-field sort on that column.
5. **Given** a sort was applied from a column header, **When** the user opens the toolbar sort control, **Then** it displays exactly that sort — both controls always reflect the same state.
6. **Given** a column header menu is open, **When** the user selects "Filter…" and applies a value, **Then** the list is filtered and the applied filter appears in the active-filter tags identically to a filter applied from the toolbar.
7. **Given** a sorted view's URL is opened in a new session, **When** the page loads, **Then** the list is ordered by the shared sort and the header indicator is shown.

---

### User Story 2 - Sort by a related object's attribute (Priority: P2)

A user viewing a list where a column shows a related object (for example a device list with a "Site" column) wants to order the list by a property of that related object. Clicking the header of a to-one relationship column opens a menu with a "Sort by" submenu listing the related object's sortable attributes; picking one with a direction orders the list by that related attribute (for example, devices ordered by their site's name).

**Why this priority**: Relationship columns are common in Infrahub lists, and ordering "through" them is already supported by the platform's sorting model — but a relationship has no single obvious sort value, so the user must choose which related attribute to sort on. This builds directly on the menu introduced in Story 1.

**Independent Test**: On a device list with a Site column, click the Site header, open "Sort by", choose "Name ↑", and verify devices are ordered by their site's name ascending with the indicator on the Site header. Verify a to-many relationship column offers no sort entries in its menu, only "Filter…".

**Acceptance Scenarios**:

1. **Given** a list with a to-one relationship column, **When** the user opens its header menu, **Then** a "Sort by" submenu lists the related object's sortable attributes, each selectable with ascending or descending direction.
2. **Given** the user selects a related attribute and direction, **When** the list refreshes, **Then** items are ordered by that related attribute in the chosen direction and the relationship column header shows the direction indicator.
3. **Given** a list with a to-many relationship column, **When** the user opens its header menu, **Then** no sort entries are offered — only "Filter…".

---

### User Story 3 - Header filtering stays fully consistent with the unified filter experience (Priority: P3)

A user who starts filtering from a column header gets exactly the same experience as filtering from the toolbar: the same filter form, the same active-filter tags below the toolbar, the same URL persistence, and the same ability to edit or remove the filter afterwards from either place. The header is a second door into the one filtering system — never a parallel one.

**Why this priority**: Filtering already works from headers today; the risk of this feature is divergence, not absence. This story locks in behavioral parity so the header menu refactor cannot fork the filtering experience.

**Independent Test**: Apply a filter from a column header menu, then remove it from the toolbar's active-filter tag; apply a filter from the toolbar, then verify the corresponding column header shows its active-filter indication. Confirm both paths produce identical URL state.

**Acceptance Scenarios**:

1. **Given** a filter applied from a column header menu, **When** the user inspects the active-filter tags and the URL, **Then** they are indistinguishable from the same filter applied via the toolbar filter control.
2. **Given** a filter is active on a column, **When** the user opens that column's header menu and selects "Filter…", **Then** the filter form opens pre-filled with the current value for editing.
3. **Given** a filter applied from a header, **When** the user removes it from the toolbar's active-filter tag, **Then** the column header no longer shows an active-filter indication.

---

### Edge Cases

- A column that is neither sortable nor filterable (e.g., a JSON attribute) renders a plain, non-interactive header — no menu, no empty menu.
- A sortable column whose values cannot be meaningfully ordered (list, JSON, password kinds) offers "Filter…" only, no sort entries.
- The URL contains a sort referencing a field that is not sortable for the schema (hand-edited or stale link): the invalid sort is ignored and the default order applies — matching how sorts from the URL are validated today.
- The related object's definition for a relationship column cannot be resolved: that column offers no "Sort by" submenu.
- A column both drives the active sort and has an active filter: the header shows both the sort direction indicator and the active-filter indication.
- The list sits on a page other than the first when the user changes the sort: the page offset is kept unchanged (consistent with how filter changes behave today).
- The list is ordered by its schema-defined default: no direction indicator is shown on any header (the indicator marks user-applied sorts only, since the default order may combine several fields or metadata not shown as columns).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Clicking a column header in list views that have interactive headers today (object lists, IP address lists, IP prefix lists) MUST open a menu for that column.
- **FR-002**: For sortable regular columns, the header menu MUST offer "Sort ascending" and "Sort descending". Selecting one MUST replace the entire active sort with a single-field sort on that column and direction.
- **FR-003**: To-one relationship columns MUST offer a "Sort by" submenu listing the related object's sortable attributes with a direction choice. To-many relationship columns MUST offer no sort entries.
- **FR-004**: The header menu MUST visibly mark the active sort direction for that column. Selecting the already-active direction MUST clear the user-applied sort and restore the schema's default order.
- **FR-005**: A column header MUST display an ascending/descending indicator when that column drives the active user-applied sort. No indicator is shown for the schema default order.
- **FR-006**: The header menu MUST offer "Filter…", which opens the existing per-column filter form. Filters applied this way MUST be identical in state, active-filter tags, and URL persistence to filters applied from the toolbar filter control.
- **FR-007**: Header sorting and the toolbar sort control MUST share a single sort state: a sort applied in one MUST be immediately reflected in the other, and the sort MUST be persisted in the page URL as it is today.
- **FR-008**: Columns that are neither sortable nor filterable MUST render as plain, non-interactive headers.
- **FR-009**: Sort selections originating from headers MUST pass the same validation applied to sorts read from the URL, so only fields sortable for the schema ever reach the data layer.
- **FR-010**: Changing the sort MUST NOT change the current pagination offset.
- **FR-011**: The toolbar sort control MUST remain available for building multi-field sorts; this feature adds an entry point and MUST NOT remove or reduce existing sorting or filtering capabilities.

### Key Entities

- **Sort**: An ordered list of (field, direction) pairs, persisted in the page URL. Already exists; this feature adds a new way to set it, not a new shape.
- **Filter**: A per-field condition, persisted in the page URL and shown as active-filter tags. Already exists; unchanged by this feature.
- **Column header menu**: A new interaction surface on column headers, replacing today's header filter popover. It owns no state of its own — it reads and writes the existing sort and filter state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can sort any list by any sortable visible column in at most 2 interactions from the list view (open header menu, pick direction).
- **SC-002**: A sorted view survives page reload and link-sharing: opening the URL restores the identical order and indicators in 100% of cases.
- **SC-003**: All filtering behavior available before this feature (per-column forms, active-filter tags, editing, removal, URL persistence, search) works identically after it — zero regressions in existing end-to-end coverage.
- **SC-004**: Reordering completes within the same time as the list's normal refresh today — the feature introduces no additional wait beyond one list reload per sort change.
- **SC-005**: Users can undo a header-applied sort and return to the default order from the same header menu, without visiting the toolbar, in 100% of cases.

## Assumptions

- The existing unified-filter-menu specification (`specs/ifc-2428-filters`, still Draft) is softened, not contradicted: its FR-001b ("column headers are no longer clickable filter triggers") becomes "column headers reuse the unified filter flow as a second entry point". That Draft spec should be amended when it is next worked on; this spec is the current source of truth for header behavior.
- Sorting scope is exactly the list views wired to the sorting state: object lists and the IPAM IP address / IP prefix lists. Other lists sharing the interactive header (role-manager lists, the branches list's filterable columns) render the menu with "Filter…" only — filtering outcome unchanged, the interaction moves under the menu like everywhere else. Simple read-only tables are untouched.
- The IPAM lists do **not** currently pass any ordering to their data queries (verified during planning). Because the header menu is shared, shipping it without that wiring would show sort actions on IPAM tables that silently do nothing. IPAM sort wiring is therefore **in scope and release-blocking**: it may be implemented after Story 1, but the feature does not ship to IPAM tables without it.
- Multi-field sort management stays in the toolbar sort control; headers intentionally offer single-field sorting only.
- Resetting pagination on sort or filter change is explicitly out of scope (current behavior keeps the offset); revisiting that is a separate improvement.
- The platform's existing server-side ordering capability (multi-field, per-direction, including ordering through to-one relationships by a related attribute) is sufficient; no data-layer or API changes are required.
