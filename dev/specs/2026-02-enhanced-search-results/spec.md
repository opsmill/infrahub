# Feature Specification: Enhanced Search Results

**Feature Branch**: `2026-02-enhanced-search-results`
**Created**: 2026-02-19
**Updated**: 2026-02-23
**Status**: Draft
**Input**: User description: "Enhance the search anywhere UI to show scrollable results, display total match count, and provide a full results page with table view per node type. Fix broken backend pagination for case-insensitive search and add permission-aware filtering so search results respect model-level read permissions."

## Clarifications

### Session 2026-02-19

- Q: Should the dropdown load results lazily as the user scrolls, eagerly fetch a capped batch, or use a two-tier approach? → A: Eager fetch with cap — fetch up to 50 results at once; rely on "View all" for the rest.
- Q: Should the full results page tables support sorting, filtering, or be read-only? → A: Sort only — users can click column headers to sort within each node type group; no additional filtering.
- Q: Can users refine their search query directly on the full results page, or must they go back? → A: Editable search bar — the full results page includes a search input pre-filled with the query, allowing in-place refinement.
- Q: How should node type groups be ordered on the full results page? → A: By result count descending — groups with the most matches appear first.

### Session 2026-02-23

- Context: The case-insensitive search path (default) used a separate code path that looped over two kinds calling NodeManager.query() per kind with a Python-side limit, breaking pagination (unstable counts, duplicate/shifted results across pages). The case-sensitive path used NodeGetListByAttributeValueQuery with native Cypher SKIP/LIMIT which worked correctly.
- Decision: Unify both paths to use NodeGetListByAttributeValueQuery with a new `case_insensitive` flag, eliminating the two-kind loop. Use `query.count()` for true total count.
- Context: Patrick Ogenstad noted that search results currently bypass model-level read permissions. Users with restricted access can see search results for models they should not be able to read. This is a security gap that should be addressed as part of the search enhancement work.
- Q: Where should permission filtering happen to maintain pagination correctness? → A: Hybrid — pre-query for model-level kind filtering (compute allowed schema kinds from PermissionManager, pass as Cypher filter so SKIP/LIMIT and count are automatically correct), post-query for any finer-grained object-level permissions in the future.
- Q: How should admin/unrestricted users bypass the permission kind filter for performance? → A: Skip kind filter entirely — if user has global allow-all permission, omit the allowed_kinds Cypher clause. Zero overhead for admins.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scrollable Search Results Dropdown (Priority: P1)

As a user, when I type a search query in the "search anywhere" input, I want the results dropdown to display more than the current 4-5 results and allow me to scroll through all matching items without leaving my current page. This is similar to how Apple Finder search shows results in a scrollable list.

**Why this priority**: This is the core improvement to the existing search experience. Users currently have no way to discover or access results beyond the initial 4-5 shown, making the search feel incomplete and unreliable.

**Independent Test**: Can be fully tested by typing a search query that returns more than 5 results and verifying the dropdown displays a scrollable list. Delivers immediate value by surfacing previously hidden results.

**Acceptance Scenarios**:

1. **Given** a user has typed a search query that matches more than 5 items, **When** the results dropdown appears, **Then** the dropdown displays results in a scrollable container with a visible scrollbar.
2. **Given** a user is viewing the scrollable results dropdown, **When** they scroll through the list, **Then** all fetched results (up to 50) are immediately available and scroll smoothly without additional loading.
3. **Given** a user is viewing the results dropdown, **When** results are displayed, **Then** each result shows the same information as the current search (name, type, description/summary).
4. **Given** a user is viewing the scrollable results dropdown, **When** they click on any result, **Then** they are navigated to that item's detail page.

---

### User Story 2 - Total Match Count and "View All Results" Link (Priority: P1)

As a user, when I perform a search, I want to see the total number of matching results at the bottom of the dropdown and have a link to view all results on a dedicated page. This tells me at a glance whether I've found what I need or should explore further.

**Why this priority**: Without knowing the total count, users cannot make informed decisions about whether to refine their search or browse all results. This is essential context for an effective search experience.

**Independent Test**: Can be fully tested by performing a search and verifying the dropdown footer shows "View all X results" with the correct count, and that clicking it navigates to the full results page.

**Acceptance Scenarios**:

1. **Given** a user has typed a search query, **When** the results dropdown appears, **Then** the bottom of the dropdown displays the total number of matching results (e.g., "View all 42 results").
2. **Given** a user sees the total count at the bottom of the dropdown, **When** they click the "View all results" link, **Then** they are navigated to a dedicated full search results page.
3. **Given** a user has typed a search query that returns 0 results, **When** the dropdown appears, **Then** a "No results found" message is displayed without a "View all" link.
4. **Given** a user has typed a search query that returns 5 or fewer results, **When** the dropdown appears, **Then** the total count is still displayed but the "View all results" link is still available for consistency.

---

### User Story 3 - Full Search Results Page with Table View (Priority: P2)

As a user, when I click "View all results" from the search dropdown, I want to see a dedicated page that displays all matching results organized by node type in a table format, similar to how NetBox presents search results. This allows me to efficiently browse, sort, and compare results across different types.

**Why this priority**: While the dropdown improvements (P1) address the immediate search experience, the full results page provides the deep-dive capability needed for thorough data exploration. It depends on the "View all results" link from Story 2.

**Independent Test**: Can be fully tested by navigating to the full results page (via link or direct URL) and verifying results are grouped by node type in table format with proper columns.

**Acceptance Scenarios**:

1. **Given** a user has navigated to the full search results page, **When** the page loads, **Then** results are grouped by node type, each group displayed as a separate table.
2. **Given** a user is viewing the full search results page, **When** results are grouped by node type, **Then** each group heading shows the node type name and the count of matching results for that type (e.g., "Devices (12)").
3. **Given** a user is viewing a node type group table, **When** they look at the table columns, **Then** columns include relevant attributes for that node type (at minimum: name/label, description, and a link to the detail page).
4. **Given** a user is viewing the full search results page, **When** they look at the page header, **Then** it displays an editable search input pre-filled with the current query and the total result count.
5. **Given** a user is on the full search results page, **When** they modify the search query in the search input and submit, **Then** the page refreshes with new results matching the updated query and the URL updates accordingly.
6. **Given** a user is viewing the full search results page with many results in one group, **When** the group has more results than fit on screen, **Then** the table supports pagination or infinite scroll within each group.
7. **Given** a user is viewing a node type group table, **When** they click a column header, **Then** the results within that group are sorted by that column (toggling ascending/descending).

---

### User Story 4 - Reliable Backend Pagination for Search (Priority: P1)

As a user paginating through search results (via the full results page or any API consumer), I want each page to show the correct slice of results with a stable total count, so that I can trust pagination controls and navigate through results without seeing duplicates or missing items.

**Why this priority**: Without correct backend pagination, all frontend pagination features (US2 total count, US3 full results page) display incorrect data. This is a foundational correctness fix that blocks reliable use of all other search enhancements.

**Independent Test**: Can be fully tested by making API calls with different offset/limit combinations and verifying: page 1 + page 2 results cover all matches without duplicates, total count is stable across pages, and results are consistent regardless of page size.

**Acceptance Scenarios**:

1. **Given** a search query matches N results, **When** a user requests page 1 (offset=0, limit=L), **Then** the response contains exactly min(L, N) results and a total count of N.
2. **Given** a search query matches N results, **When** a user requests sequential pages (offset=0 then offset=L then offset=2L), **Then** the combined results contain no duplicates and cover all N matches.
3. **Given** a search query matches N results, **When** a user requests any page, **Then** the total count is always N regardless of the offset or limit values.
4. **Given** a case-insensitive search (default), **When** a user paginates through results, **Then** the behavior is identical to case-sensitive pagination — same stability, same count accuracy, same ordering guarantees.
5. **Given** a search query matches results across multiple node types (e.g., nodes and groups), **When** a user paginates, **Then** results from all matching types are interleaved in a single stable ordering (not queried separately per type).

---

### User Story 5 - Permission-Aware Search Results (Priority: P2)

As an administrator who has configured model-level read permissions, I want the search results to respect those permissions so that users only see results for node types they are authorized to view. A user with restricted access should never discover the existence of nodes they cannot read, even through search.

**Why this priority**: This is a security requirement. While the system functions without it (users see results they can't actually open), it leaks information about the existence of restricted data. It should be addressed alongside the search enhancements but can be delivered after the pagination and UI improvements.

**Independent Test**: Can be fully tested by configuring a user account with restricted model-level read permissions, performing a search, and verifying that results only include node types the user is authorized to view.

**Acceptance Scenarios**:

1. **Given** a user has read permission for only specific node types, **When** they perform a search, **Then** results only include nodes of types they are authorized to view.
2. **Given** a user has read permission for only specific node types, **When** they view the total count, **Then** the count reflects only the results they are authorized to see (not the total across all types).
3. **Given** a user has full read permissions (default/admin), **When** they perform a search, **Then** the behavior is identical to the current search with no performance degradation.
4. **Given** a user's permissions change (e.g., admin grants access to a new model), **When** the user performs a new search, **Then** the results immediately reflect the updated permissions without requiring a session restart.
5. **Given** a user without permission to view a node type, **When** they search for a term that matches nodes of that type, **Then** those nodes do not appear in results, in the count, or in any node type group on the full results page.

---

### Edge Cases

- What happens when a search returns hundreds or thousands of results? The dropdown should cap at a reasonable number of visible items (e.g., 50) with the scrollbar, while the full page handles the complete set with pagination.
- How does the system handle a search with special characters or very long queries? The same behavior as today, with proper input sanitization.
- What happens if the search results change while the user is viewing the dropdown (e.g., another user modifies data)? Results remain static until the user modifies their query or manually refreshes.
- What happens when the user navigates to the full results page and then uses the browser back button? They return to their previous page with the search dropdown closed.
- How does the search behave on slow connections? A loading indicator is shown in the dropdown while results are being fetched.
- What happens when a node type group on the full results page has zero remaining results after filtering? The group heading is hidden if it has no matching results.
- What happens when a user with no read permissions for any node type performs a search? The search returns 0 results with a "No results found" message — the same as a search with no matches.
- What happens when permissions are configured at a granular level (e.g., user can view DeviceType but not Device)? The search correctly filters at the node type level, showing only results for permitted types.

## Requirements *(mandatory)*

### Functional Requirements

#### Search Dropdown (US1, US2)

- **FR-001**: The search dropdown MUST eagerly fetch and display up to 10 results in a scrollable container when more than 5 results match the query.
- **FR-002**: The search dropdown MUST show a visible scrollbar when the results exceed the visible area.
- **FR-003**: The search dropdown MUST have a maximum height that keeps it within the viewport and does not obscure critical UI elements.
- **FR-004**: The search dropdown MUST display the total number of matching results at the bottom of the dropdown.
- **FR-005**: The search dropdown MUST include a "View all X results" link at the bottom that navigates to the full search results page.
- **FR-013**: The search dropdown MUST continue to support keyboard navigation (arrow keys to move between results, Enter to select).

#### Full Results Page (US3)

- **FR-006**: The full search results page MUST display all matching results grouped by node type, ordered by result count descending (groups with the most matches appear first).
- **FR-007**: Each node type group on the full results page MUST be displayed as a table with relevant columns for that type.
- **FR-008**: Each node type group heading MUST display the node type name and the count of matching results for that type.
- **FR-009**: The full search results page MUST display an editable search input pre-filled with the current query and the total result count in the page header.
- **FR-010**: The full search results page MUST support pagination when a node type group contains many results.
- **FR-011**: Each result row on the full search results page MUST link to the corresponding item's detail page.
- **FR-012**: The full search results page MUST be accessible via a direct URL containing the search query, allowing users to bookmark or share search results.
- **FR-014**: Each node type group table on the full results page MUST support column-header sorting (ascending/descending toggle) without additional filtering capabilities.
- **FR-015**: The full search results page MUST update results and URL when the user modifies and submits a new query from the page search input.

#### Backend Pagination (US4)

- **FR-016**: The search backend MUST use a single database query for both case-sensitive and case-insensitive search paths, eliminating the per-kind loop that causes pagination instability.
- **FR-017**: The search backend MUST support `offset` and `limit` parameters for native database-level pagination (Cypher SKIP/LIMIT), not Python-side slicing of over-fetched results.
- **FR-018**: The search backend MUST return a true total count of all matching results, independent of the current page's offset and limit values.
- **FR-019**: The search backend MUST return results in a stable, deterministic order across pages so that sequential page requests produce non-overlapping, complete coverage of all results.
- **FR-020**: Case-insensitive search (default) MUST use `toLower(toString(...))` matching in the database query rather than pre-computing case variations, ensuring all case combinations are matched (not just original, lower, upper, and title case).

#### Permission-Aware Filtering (US5)

- **FR-021**: The search resolver MUST compute the set of allowed schema kinds from the user's model-level read permissions and pass them as a pre-query filter, so that the database query only returns nodes of types the user is authorized to view.
- **FR-022**: The total count returned by the search MUST reflect only results the user is authorized to see. Because permission filtering is applied pre-query, the database count is inherently correct.
- **FR-023**: Permission filtering MUST NOT degrade search performance for users with full read access (default/admin users). When the user has a global allow-all permission, the kind filter MUST be skipped entirely (no Cypher clause added).
- **FR-024**: Permission filtering MUST use the existing permission infrastructure (PermissionManager available in GraphQL context) rather than introducing a new authorization mechanism.

### Key Entities

- **Search Query**: The text input from the user used to find matching nodes across the system.
- **Search Result**: A matched node returned by the search, containing at minimum: node name/label, node type, and a reference to the detail page.
- **Node Type Group**: A logical grouping of search results by their node type on the full results page, containing a type name, result count, and a table of matching results.
- **Permission Scope**: The set of node types a user is authorized to read, determined by their assigned roles and object-level permissions. Expressed as namespace/name pairs (e.g., "Infra/Device") with a "view" action.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can browse all matching search results without leaving the current page, with the dropdown supporting at least 50 visible results via scrolling.
- **SC-002**: Users can see the total number of matching results within 1 second of typing their search query.
- **SC-003**: Users can navigate from the search dropdown to a full results page in a single click.
- **SC-004**: The full search results page loads and displays grouped results within 2 seconds for queries returning up to 500 results.
- **SC-005**: Users can identify the node type and count for each group of results on the full page at a glance.
- **SC-006**: 90% of users can find a specific item using the enhanced search within 3 interactions (type query, scroll/scan, click result or view all).
- **SC-007**: Paginating through search results produces complete, non-overlapping coverage of all matching items — no duplicates or missing results across sequential pages.
- **SC-008**: Total count remains stable across all pages for the same search query (same value returned regardless of offset/limit).
- **SC-009**: Users with restricted model-level read permissions see only results for node types they are authorized to view, with the total count reflecting only their permitted results.
- **SC-010**: Search performance for unrestricted users (admin/default) shows no measurable degradation after permission filtering is added.

## Assumptions

- The existing search backend already supports returning more than 5 results and can provide a total count; this feature primarily involves changes to how results are presented.
- The current search ranking/relevance algorithm remains unchanged; this feature focuses on result display, not search quality.
- The table columns on the full results page will be determined by the node type's schema (using existing attribute metadata).
- Pagination on the full results page will default to 20 results per group, consistent with existing list views in the application.
- The dropdown will fetch up to 50 results initially; the full results page will fetch all results with pagination.
- Keyboard accessibility patterns follow existing application conventions.
- The PermissionManager in the GraphQL context already resolves model-level read permissions and can be queried to determine which node types a user can view. No new permission infrastructure is needed.
- Permission filtering uses a hybrid approach: model-level kind filtering is applied pre-query by computing allowed schema kinds from PermissionManager and passing them as a Cypher-level filter (`n.kind IN $allowed_kinds`), ensuring SKIP/LIMIT and count remain correct. Any future finer-grained object-level permissions would be applied post-query.
- A future iteration of NodeManager may support querying across all node types natively, but for this feature we use NodeGetListByAttributeValueQuery with explicit `kinds` filtering as the more targeted solution.
