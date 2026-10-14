# Feature Specification: Allocation scope table for scoped number pools

**Feature Branch**: `bab-allocation-scope-table-ifc-3366`

**Created**: 2026-10-14

**Status**: Draft

**Input**: Idea brief from the grilling session on the `/proto/number-pool` prototype: build the details page of a number pool that has an allocation scope, starting with the table of its allocation scopes and the page of one allocation scope.

## Background

A number pool can have an allocation scope: an ordered list of attributes or relationships of the node it allocates to, for example Site + Role. Each combination of values of those fields has its own set of numbers. In this specification, one such combination, for example "par1 · leaf", is called **an allocation scope**, the same word the interface uses.

Today an operator can create and edit a scoped pool, but its details page shows an error, because the page requests usage for the whole pool and Infrahub refuses that request for a scoped pool.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View every allocation scope of a pool and open one (Priority: P1)

A network operator who allocates numbers per site or per device opens a scoped number pool. They view one row per allocation scope, the fullest first, find the one they care about with search, and open it to view its ranges and the numbers allocated in it.

**Why this priority**: the details page of a scoped pool cannot be used at all today. This story replaces the error with the information the operator needs to plan capacity: which allocation scope is closest to full, and which numbers it holds.

**Independent Test**: create a pool scoped by Site, allocate numbers in three sites, open the pool, check the table, search it, open one row and check that only that site's numbers are listed.

**Acceptance Scenarios**:

1. **Given** a pool scoped by Site, with numbers allocated in `par1`, `ams2` and `fra1`, **When** the operator opens the pool, **Then** they view the header sentence ending with "scoped by Site" and a table with one row per allocation scope, the fullest first, each row with a usage bar.
2. **Given** the same pool, **When** the operator types `ams` in the search field, **Then** the table shows only the `ams2` row.
3. **Given** the same pool, **When** the operator selects the `par1` row, **Then** the URL identifies `par1`, and the operator views the ranges card and the allocations card of `par1` only.
4. **Given** the URL of the `par1` allocation scope, **When** the operator opens it in a new tab or shares it with a colleague who opens it, **Then** the same `par1` page appears.
5. **Given** the `par1` page, **When** the operator selects "All allocation scopes", **Then** they return to the table.
6. **Given** the `par1` page, **When** the operator selects one range in the ranges card, **Then** the allocations card lists only the numbers of `par1` within that range.

---

### User Story 2 - Switch allocation scope from the allocation scope page (Priority: P2)

From the page of one allocation scope, the operator picks another allocation scope from a searchable list in the left column, without returning to the table.

**Why this priority**: it saves a step when the operator compares several allocation scopes. Without it, the operator returns to the table, which still works.

**Independent Test**: open the `par1` page, pick `ams2` in the list, and check that the page shows `ams2`.

**Acceptance Scenarios**:

1. **Given** the `par1` page, **When** the operator picks `ams2` in the allocation scope list, **Then** the URL identifies `ams2` and the page shows the ranges and allocations of `ams2`.

This story is not delivered by IFC-3366. It is recorded so that the P1 page leaves room for it.

---

### Edge Cases

- **A scoped pool with no allocated numbers**: the table is empty and shows "No numbers allocated yet. An allocation scope appears here once an object in it holds a number from this pool."
- **An allocation scope that holds no numbers**, for example a site where nothing was allocated yet: it is not listed in the table and cannot be opened from it.
- **A URL to an allocation scope whose numbers were all released**: the page opens with 0 used in every range and an empty allocations table.
- **A URL that does not match the pool's allocation scope**, because someone edited it by hand or it is malformed: the page shows "This link does not match the pool's allocation scope (…)", naming the pool's fields, and the "All allocation scopes" link. The operator never views a raw error.
- **An empty value**: the cell shows "No value".
- **A peer that the operator cannot read**: the cell shows the peer's ID.
- **A pool with exactly one allocation scope**: the table is still shown, with one row.
- **A search that matches nothing**: the table shows "No allocation scope matches".
- **A pool with a very large number of allocation scopes**: every row is reachable by scrolling; no row cap hides any of them. The page draws every row, so it can be slow to appear and to filter on such a pool until the table draws only the visible rows (Out of Scope).
- **An allocation scope with many fields**: the table scrolls horizontally, and the usage column stays visible on the right.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For a scoped pool, the details page MUST show a table with one row per allocation scope that holds at least one number, instead of an error.
- **FR-002**: The table MUST show one column per field of the pool's allocation scope, in the pool's order, and a usage column. Each usage cell MUST split numbers used on the default branch from numbers used only on other branches, as the details page of an unscoped pool does.
- **FR-003**: The table MUST show the number of allocation scopes it lists.
- **FR-004**: The table MUST list every allocation scope, with no row cap.
- **FR-014**: When the columns do not fit the width of the card, the table MUST scroll horizontally, and the usage column MUST stay pinned on the right edge while it scrolls.
- **FR-005**: Users MUST be able to search the table; a row matches when any of its values contains the search text, ignoring case.
- **FR-006**: The table MUST be sorted by usage, highest first, by default. Users MUST be able to sort it by any column.
- **FR-007**: Each row MUST be a link to a URL that identifies the allocation scope, so that the browser's own actions work: open in a new tab, copy the link, share it.
- **FR-008**: The page of one allocation scope MUST have the same layout as the details page of an unscoped pool: the ranges card on the left and the allocations card on the right.
- **FR-009**: On the page of one allocation scope, the usage of the pool and of each range MUST count only the numbers held in that allocation scope, and the allocations card MUST list only those numbers. The existing range, branch and source filters MUST keep working within the allocation scope.
- **FR-010**: The page of one allocation scope MUST show its values, for example "Site: par1", and an "All allocation scopes" link that returns to the table.
- **FR-011**: The header sentence of a scoped pool MUST name the fields of its allocation scope, for example "scoped by Site + Role".
- **FR-012**: The interface MUST use the term "allocation scope" for one row and "allocation scopes" for the table, never "scope" alone.
- **FR-013**: The details page of an unscoped pool MUST keep working as it does today.

### Key Entities

- **Number pool**: hands out numbers to one attribute of one kind of node. It may have an allocation scope.
- **Allocation scope (the fields)**: the ordered list of attributes or relationships that splits the pool, for example Site + Role. Set when the pool is created and read-only afterwards.
- **Allocation scope (one row)**: one combination of values of those fields, for example "par1 · leaf". It has its own usage figures. It exists for display only while it holds at least one number.
- **Range**: a span of numbers of the pool, with an optional weight. Its usage is counted within one allocation scope.
- **Allocation**: one number held by one object on one branch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can open the details page of every scoped pool without an error.
- **SC-002**: The fullest allocation scope is the first row of the table without any search or sort, and the operator reaches the numbers allocated in it with one click.
- **SC-003**: Once the page has received the allocation scopes of a pool that has 1,000 of them, the operator views the first rows with no visible delay, and search results update while they type with no visible delay. Larger pools are covered by the later work that draws only the visible rows.
- **SC-004**: The usage of an allocation scope shown in the table equals the usage of the pool shown after opening that allocation scope.

## Assumptions

- **Primary user**: a network operator who allocates numbers per allocation scope, for example VLAN IDs per site or sub-interface unit IDs per parent interface.
- **Infrahub already provides the data**: the list of allocation scopes with their usage, the usage of each range within one allocation scope, and the allocations within one allocation scope. This feature does not change the backend or the GraphQL schema.
- **Different words in the interface and the API**: the API calls one row a "division", and uses "allocation scope" for the list of fields. The public documentation must say that both words name the same thing.
- **Operators cannot change a pool's allocation scope after creation**: the edit form shows it as read-only, and Infrahub refuses schema changes that break a field a scoped pool depends on.
- **Number of allocation scopes**: the largest real figure is not known and can be large. The table draws every row in this feature; drawing only the visible rows comes later, by decision of the feature owner. 1,000 is the figure SC-003 is checked at.
- **Backend response time is outside this feature**: the page shows a loading state until the data arrives, as the details page of an unscoped pool does.
- **Branches and time**: usage counts numbers on every live branch, as the details page of an unscoped pool does. The figures do not follow the time-machine date.
- **Tests and documentation**: the existing end-to-end test of number pools is extended with a scoped pool; the resource manager guide for number allocation gets a section on viewing a scoped pool; a changelog fragment is added.

### Out of Scope

- The allocation scope list on the allocation scope page (User Story 2).
- Drawing only the visible rows of the allocation scopes table. Until it is added, the table draws every row, so a very large pool is slow to show and to filter.
- Opening the allocation scope directly when the pool has only one.
- Listing allocation scopes that hold no numbers.
- Backend pagination or search of allocation scopes, and backend response time.
- Usage figures that follow the time-machine date.
