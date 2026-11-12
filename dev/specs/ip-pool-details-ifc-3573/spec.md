# Feature Specification: Redesign the IP prefix pool and IP address pool details page

**Feature Branch**: `ple-ip-pool-details-ifc-3573`

**Created**: 2026-11-04

**Status**: Draft

**Jira**: [INFP-759](https://opsmill.atlassian.net/browse/INFP-759) (idea), [IFC-3573](https://opsmill.atlassian.net/browse/IFC-3573) (epic), [IFC-3582](https://opsmill.atlassian.net/browse/IFC-3582) (delivery ticket), with tasks IFC-3574 (header, list, Actions menu), IFC-3575 (allocated table), IFC-3576 (end-to-end tests), IFC-3577 (documentation)

**Input**: User description: *"Take the prototype on branch `bab-proto-ip-pool-design` (its Dots variant) and build it with what the backend already provides."* The prototype is commit `8827d389b5`, files under `frontend/app/src/proto/ip-pool-defaults/`.

## Background

A network engineer who manages pools in the Resource Manager opens a pool's page to check how full it is, which resource prefix is close to full, what each resource prefix already holds, and what a new allocation gets when the request sets no value of its own.

The number pool page already answers these questions with a header, a list of ranges with usage bars, and a table of allocations in the main area. The IP prefix pool and IP address pool page still uses an earlier, generic layout:

- The pool's settings appear in a card that lists every attribute with its raw value.
- What a resource prefix holds opens in a narrow side panel beside the list, and the engineer pages through it.
- The page is laid out differently from the number pool page, so an engineer who manages both kinds of pool works with two layouts.

This feature rebuilds the IP pool page on the number pool page's layout. The backend does not change. The page reads what the backend already provides:

- the pool node
- the per-resource utilization query
- the paginated allocations query
- the allocation weights, through the `CoreWeightedPoolResource` generic
- the pool's extra fields, when a schema extension adds fields to the pool

## Design Principles

**Follow the number pool page.** Anything this spec does not state explicitly (header layout, list layout, table layout, Actions menu, loading states) follows the number pool page.

**Say what the backend does.** A default is worded as what happens when an allocation request leaves the value out. When the backend has no fallback, the page says the request must set the value; it does not invent a default.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the pool's namespace and defaults at a glance (Priority: P1)

The engineer opens an IP prefix pool or an IP address pool. The header shows the pool's name, description, metadata, ID, a refresh button and an Actions menu, laid out like the number pool header. Under the title, one line names the pool type, the namespace and the pool's defaults, separated by dots, for example: "IP Prefix Pool in namespace default · Prefix kind defaults to IpamIPPrefix · Prefix length defaults to /31 · Member type defaults to Address".

**Why this priority**: This is the information the engineer reads first, and the current page hides it in a card of raw attribute values.

**Independent Test**: Open a seeded IP prefix pool and a seeded IP address pool and read the header line.

**Acceptance Scenarios**:

1. **Given** an IP prefix pool in namespace `default` with a default prefix type of `IpamIPPrefix`, a default prefix length of 31 and a default member type of `address`, **When** the engineer opens the pool, **Then** the line reads "IP Prefix Pool in namespace default · Prefix kind defaults to IpamIPPrefix · Prefix length defaults to /31 · Member type defaults to Address".
2. **Given** an IP address pool with a default address type of `IpamIPAddress` and a default prefix length of 32, **When** the engineer opens the pool, **Then** the line reads "IP Address Pool in namespace default · Address kind defaults to IpamIPAddress · Prefix length defaults to /32".
3. **Given** an IP prefix pool whose default prefix type and default prefix length are not set, **When** the engineer opens the pool, **Then** the line reads "Prefix kind has no default · Prefix length has no default" for those two entries, because an allocation request has to set them.
4. **Given** an IP address pool whose default prefix length is not set, **When** the engineer opens the pool, **Then** the entry reads "Prefix length follows the resource prefix", because the backend gives the address the prefix length of the resource prefix it comes from.
5. **Given** the kind named in the line exists in the schema, **When** the engineer selects it, **Then** the schema viewer opens on that kind.
6. **Given** the pool's namespace, **When** the engineer selects it, **Then** the IPAM page opens filtered on that namespace.

---

### User Story 2 - Find the resource prefix closest to full (Priority: P1)

The engineer scans the resource prefix list on the left. Each resource prefix shows a usage bar split into the default branch and the branch the engineer is viewing, with the usage percentage, and the allocation weight when one is set.

**Why this priority**: Finding the resource prefix that is about to run out is the main reason to open the page.

**Independent Test**: Open a pool with several resource prefixes, including one with allocations on another branch, and read the list.

**Acceptance Scenarios**:

1. **Given** a pool with three resource prefixes, **When** the engineer opens the pool on the default branch, **Then** each resource prefix shows its prefix, a usage bar and the usage percentage, and the tooltip of the bar reads the default-branch share.
2. **Given** a resource prefix that received an allocation on branch `b1`, **When** the engineer views the pool on `b1`, **Then** the bar shows the extra usage of `b1` as a second, lighter segment, and the tooltip names it as usage on this branch only.
3. **Given** resource prefixes whose kind has an allocation weight and whose weights are 100, 100 and 50, **When** the engineer reads the list, **Then** the list shows "Weight 100", "Weight 100", "Weight 50" in that order, which is the order in which the backend fills them, and the two resource prefixes with weight 100 are ordered by prefix: IP version, then address, then prefix length.
4. **Given** resource prefixes whose kind has no allocation weight, **When** the engineer reads the list, **Then** no weight is shown and the list is ordered by prefix: IP version, then address, then prefix length.
5. **Given** a pool with no resource prefix, **When** the engineer opens it, **Then** the list is replaced by a card that says the pool cannot allocate until it has a resource prefix, and no allocated table is shown.

---

### User Story 3 - Review what a resource prefix holds and share a link to it (Priority: P1)

The engineer selects a resource prefix. The main area shows a table of what it holds, with the columns Prefix (or Address on an IP address pool), Identifier, Kind and ID. More rows load as the engineer scrolls. The selected resource prefix is part of the page link, so a colleague who opens the same link sees the same resource prefix.

**Why this priority**: This replaces the paged side panel, which is the pain the ticket describes.

**Independent Test**: Open a seeded pool, select a resource prefix with more than one page of allocations, scroll to the end, then open the page link in a new tab.

**Acceptance Scenarios**:

1. **Given** a pool with resource prefixes, **When** the engineer opens the pool without naming a resource prefix in the link, **Then** the first resource prefix in list order is selected and its allocations are shown.
2. **Given** the selected resource prefix holds 130 allocations, **When** the engineer scrolls to the end of the table, **Then** the next rows load, until all 130 are shown, and the table header shows the count 130.
3. **Given** an allocation that a Generator reserved with the identifier `par1-spine-01__par1-leaf-003__underlay`, **When** the engineer reads its row, **Then** the Identifier column shows that identifier; an allocation without an identifier shows "None".
4. **Given** a row, **When** the engineer selects the prefix or address, **Then** its IPAM details page opens on the branch the engineer is viewing.
5. **Given** the engineer selected a resource prefix, **When** they copy the page link and open it in a new tab, **Then** the same resource prefix is selected.
6. **Given** a link that names a resource prefix the pool does not have, **When** the engineer opens it, **Then** the main area says the resource prefix was not found and offers a link back to the pool.
7. **Given** a resource prefix that holds nothing, **When** the engineer selects it, **Then** the main area says there is nothing in that resource prefix yet.

---

### User Story 4 - Manage the pool from one Actions menu (Priority: P2)

The engineer opens the Actions menu in the header. It offers Copy ID, Copy HFID, Tasks, View schema, GraphQL sandbox, Documentation, Edit, Groups and Delete, like the number pool menu. Edit opens the existing IP pool form.

**Why this priority**: The current page scatters these actions (an edit button in a card, a help button in the title) and has no delete or groups action.

**Independent Test**: Open a pool, open the Actions menu, choose Edit, change the description and save.

**Acceptance Scenarios**:

1. **Given** an engineer with update permission on the pool, **When** they choose Edit and save a new description, **Then** the header shows the new description and the message "IPPrefixPool updated" (or "IPAddressPool updated") appears.
2. **Given** an engineer without update permission, **When** they open the Actions menu, **Then** Edit, Groups and Delete are disabled and their tooltip gives the reason.
3. **Given** the engineer chooses Delete and confirms, **When** the pool is deleted, **Then** the Resource Manager list opens and the pool is gone.

---

### Edge Cases

- A pool whose resource kind has an allocation weight on some resource prefixes and not on others: resource prefixes without a weight count as weight 0 and sort last, which is how the backend allocates.
- An allocation whose kind is not in the schema the engineer can read: the Kind column shows the kind name.
- The pool node loads but the utilization query fails: the header stays and the body shows the error.
- Viewing the pool at a past date or on a branch: the pool node, the utilization and the allocations are all read on that branch and at that date.
- The page is open while the engineer edits the pool: after saving, the header and the resource prefix list refresh.
- A refresh fails after the page loaded: the header, the resource prefixes, the allocations and the breadcrumb already loaded stay.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The IP prefix pool page and the IP address pool page MUST use the number pool page's layout: a header, a resource prefix list on the left and the allocated table in the main area.
- **FR-002**: The header MUST show the pool's name, description, metadata popover, ID with a copy button, a refresh button and an Actions menu. Below the defaults line, it MUST show each attribute and each single relationship that a schema extension adds to the pool, and MUST show nothing more when the pool schema has none.
- **FR-003**: The header MUST show one line with the pool type, the namespace and the defaults, separated by dots, in this order: pool type and namespace, then for a prefix pool the prefix kind, the prefix length and the member type, and for an address pool the address kind and the prefix length.
- **FR-004**: Each default MUST be worded as "<Label> defaults to <value>" when set. When not set, a prefix pool's prefix kind and prefix length MUST read "has no default", an address pool's prefix length MUST read "follows the resource prefix", and a prefix pool's member type MUST read "has no default".
- **FR-005**: The kind in the defaults line MUST open the schema viewer when its schema is loaded, and MUST be plain text otherwise.
- **FR-006**: The namespace in the defaults line MUST link to the IPAM page filtered on that namespace.
- **FR-007**: The resource prefix list MUST show, for each resource prefix, its prefix, a usage bar with the default-branch share and the viewing-branch share, and the usage percentage. Above the list, it MUST show the whole pool's usage the same way, under "All resource prefixes" with the number of resource prefixes.
- **FR-008**: When every resource prefix kind in the pool inherits the weighted pool resource generic, the resource prefix list MUST show "Weight N" for each resource prefix whose weight is set. When one kind has none, the list MUST show no weight, because the backend then ignores weights.
- **FR-009**: The resource prefix list MUST be ordered by allocation weight, highest first, with a missing weight counting as 0, which is the order in which the backend fills resource prefixes. Resource prefixes with the same weight MUST be ordered by prefix: IP version, then address, then prefix length. This tie order is the page's choice, not the backend's.
- **FR-010**: Selecting a resource prefix MUST change the page link so that it names the resource prefix, and opening such a link MUST select that resource prefix.
- **FR-011**: When the link names no resource prefix, the first resource prefix in list order MUST be selected.
- **FR-012**: The allocated table MUST show the columns Prefix (Address on an IP address pool), Identifier, Kind and ID, and MUST load more rows as the engineer scrolls to the end. When loading more rows fails, the table MUST keep the rows already loaded, stop requesting more rows and offer a Retry button.
- **FR-013**: The allocated table header MUST show the number of allocations and the selected resource prefix, which MUST link to the resource prefix's IPAM details page.
- **FR-014**: Each prefix or address in the table MUST link to its IPAM details page on the branch the engineer is viewing.
- **FR-015**: The Kind column MUST show the schema label of the kind when the schema is loaded, and the kind name otherwise.
- **FR-016**: The page MUST show an empty state for a pool without resource prefixes, an empty state for a resource prefix that holds nothing, and a not-found state for a link that names a resource prefix the pool does not have.
- **FR-017**: The Actions menu MUST offer Copy ID, Copy HFID, Tasks, View schema, GraphQL sandbox, Documentation (when the schema has a documentation link), Edit, Groups and Delete, with Edit, Groups and Delete disabled when the engineer lacks the permission.
- **FR-018**: Edit MUST open the existing IP prefix pool form or IP address pool form, and saving MUST refresh the page.
- **FR-019**: The page MUST read the pool, the utilization and the allocations on the branch and at the date the engineer is viewing.
- **FR-020**: The breadcrumb's resource selector MUST keep working with the new page, and MUST read the pool usage itself so that it does not depend on the page having loaded it.
- **FR-021**: The number pool page MUST not change, except that its allocations table MUST keep the rows already loaded when a refresh fails, and MUST keep them, stop requesting more rows and offer a Retry button when loading more rows fails.

### Key Entities

- **IP pool**: an IP prefix pool or an IP address pool. Has a name, a description, an IP namespace, resource prefixes, and defaults: for a prefix pool the prefix type, the prefix length and the member type; for an address pool the address type and the prefix length.
- **Resource prefix**: an IP prefix the pool allocates from. Has a usage on the default branch and on the viewing branch, and an allocation weight when its kind inherits the weighted pool resource generic.
- **Allocation**: an IP prefix or IP address inside a resource prefix, as visible on the viewing branch. Has a kind, a value and, when the pool reserved it, an identifier.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An engineer can read the namespace and every default of a pool without opening a card or a form.
- **SC-002**: An engineer can tell which resource prefix is closest to full from the list alone.
- **SC-003**: An engineer can reach every allocation of a resource prefix by scrolling, without a pager.
- **SC-004**: A link copied from the page opens the same resource prefix for another engineer.
- **SC-005**: The existing end-to-end tests of the Resource Manager pass once updated to the new layout, and new tests cover both pool kinds on the default branch and on another branch.

## Assumptions

- The backend does not change. The resource prefix order and the allocation weight are computed in the frontend from data the backend already returns.
- The allocation weight is read through the weighted pool resource generic when every resource prefix kind inherits it. When that read fails, the list shows no weight instead of an error. The utilization query's `weight` field is the size of the prefix and is not shown.
- The usage split on the bar is the default-branch share and the extra share on the viewing branch, which is what the utilization query returns. On the default branch, the second segment is empty.
- The allocated table has no Branch column, because the backend returns the viewing branch for every row.
- The table lists every prefix or address inside the resource prefix that is visible on the viewing branch, including ones created by hand, because that is what the allocations query returns. An entry the pool did not reserve has no identifier.
- A prefix pool whose member type is not set reads "Member type has no default" rather than the prototype's "defaults to Prefix", because the backend has no fallback at allocation time.
- The existing route shape, `/resource-manager/:resourcePoolId/resources/:resourceId`, is kept for the selected resource prefix, so the breadcrumb's resource selector keeps working.
