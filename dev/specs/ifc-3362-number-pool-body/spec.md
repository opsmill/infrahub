# Feature Specification: Number pool body for pools without an allocation scope

**Feature Branch**: `number-pool-body-ifc-3362`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Add the number pool body below the existing header, for pools without an allocation scope: a ranges card to select a range, and a table of the allocated numbers without filters. The header stays unchanged. Allocation scopes come later. Prototype: `/proto/number-pool?d=asn`."

**Sources**:

- Jira: [IFC-3362](https://opsmill.atlassian.net/browse/IFC-3362) (this work), [IFC-3347](https://opsmill.atlassian.net/browse/IFC-3347) (the number pool queries)
- The number pool queries and their contract: [PR #10932](https://github.com/opsmill/infrahub/pull/10932)
- The number pool header this body sits under: [PR #10963](https://github.com/opsmill/infrahub/pull/10963)
- The prototype: `frontend/app/src/pages/proto/number-pool/` (route `/proto/number-pool?d=asn`)

## User Scenarios & Testing *(mandatory)*

A network engineer or operator who manages a number pool (ASNs, VLAN IDs and similar) opens the pool's page. Today, for a number pool, the page shows each range's usage as a percentage only. Every range's "View" link opens the same list of all the pool's numbers, and each row shows the number but not the node that holds it. The user cannot answer "what is using this range?".

### User Story 1 - Find what uses a range (Priority: P1)

The user opens a number pool. They view which range the pool fills next and how full each range is. They select one range, scroll through the numbers in it, and open the node that holds one of them.

**Why this priority**: this is the question the page exists to answer. Without it, the body shows the same list for every range, and the user cannot tell which node holds which number.

**Independent Test**: open a pool with two ranges and numbers held on two branches, select one range, and check that the table lists only the numbers in that range, each with its holder node, kind, branch and source.

**Acceptance Scenarios**:

1. **Given** a pool without an allocation scope, with ranges 1–50 (weight 10) and 51–100 (weight 0), and 30 numbers held on `main` and on `b1`, **When** the user opens the pool, **Then** the ranges card lists "All ranges" first, then 1–50, then 51–100, and "All ranges" is selected.
2. **Given** the same pool, **When** the user selects 1–50, **Then** the address becomes `/resource-manager/<pool>/ranges/<range_id>`, 1–50 is selected, and the table lists only the numbers inside 1–50, without a Range column.
3. **Given** a number held only on `b1`, **When** the user opens the node in the Object column, **Then** the node opens on `b1`.
4. **Given** "All ranges" is selected and the pool has two ranges, **When** the user views the table, **Then** the table lists the numbers of every range, with a Range column.

---

### User Story 2 - Share a range (Priority: P2)

A user who has one range selected sends the page's address to a colleague. The colleague opens it and views the same range and the same numbers.

**Why this priority**: teams investigate number usage together. A shared address saves the colleague from finding the range again, but the main page works without it.

**Independent Test**: open `/resource-manager/<pool>/ranges/<range_id>` directly in a new tab and check that the same range is selected and the table lists the same numbers.

**Acceptance Scenarios**:

1. **Given** a user has range 51–100 selected, **When** a colleague opens the same address, **Then** 51–100 is selected and the table lists the same numbers.
2. **Given** an address that names a range that is not in the pool, **When** the user opens it, **Then** the table area shows "This range is not part of the pool" with a link to "All ranges", and the ranges card lists every range with none selected.

---

### User Story 3 - Use the page with the keyboard only (Priority: P3)

A user who works with the keyboard selects a range, moves through the table and opens a holder node without using a mouse.

**Why this priority**: the page is usable with a mouse without it, but keyboard users and screen reader users cannot complete Story 1 without it.

**Independent Test**: from the page's first focusable element, press Tab to reach the ranges card, use arrow keys to move to a range, press Enter, then move into the table and open a holder node, all with the keyboard.

**Acceptance Scenarios**:

1. **Given** focus is on the ranges card, **When** the user presses the down arrow and then Enter, **Then** the next range is selected and the address changes to that range.
2. **Given** focus is in the table, **When** the user presses the down arrow past the last loaded row, **Then** the next page of numbers loads and focus continues onto it.

---

### Edge Cases

- **The pool has no ranges**: the ranges card shows "No ranges", followed by "Edit the pool to add one" for a user-created pool or "Add one in the schema" for a schema-defined pool. The table area shows only that message. The body has no button to add a range.
- **The pool has ranges but no numbers**: the table area shows "No allocations yet".
- **The selected range has no numbers**: the table area shows "No allocations in <range>", for example "No allocations in 64,512 – 65,000".
- **The address names a range that is not in the pool** (deleted, mistyped or from another pool): the table area shows "This range is not part of the pool" with a link to "All ranges". The ranges card lists every range with none selected. The page detects this by comparing the address with the pool's ranges, and does not request the numbers. If the range is deleted between the two requests, the backend returns an error, and the page shows the same message.
- **A number is held only on a branch other than the default branch**: the row shows that branch, and the holder link opens the node on that branch.
- **The pool holds tens of thousands of numbers**: the table loads more rows as the user scrolls, and every number appears exactly once.
- **The user selects another range while the table is scrolled down**: the table goes back to its first page and to the top.
- **A range declares no weight**: it shows "Weight 0", because the backend returns 0 both for no weight and for a weight of 0.

## Requirements *(mandatory)*

### Functional Requirements

**Page**

- **FR-001**: On a number pool's page, the system MUST replace the whole previous body with the new body. The previous body is the properties card, the Resources card and the per-range view under `resources/<id>`. The header above the body MUST stay unchanged.
- **FR-002**: IP prefix pools and IP address pools MUST keep their current body and their `resources/<id>` view unchanged.
- **FR-003**: "All ranges" MUST be at `/resource-manager/<pool>`, and one range MUST be at `/resource-manager/<pool>/ranges/<range_id>`. Old `/resource-manager/<pool>/resources/<id>` addresses for number pools get no redirect.
- **FR-004**: The body MUST show numbers and usage from every branch, whatever branch the user has selected. Switching branches MUST NOT change what the body shows.

**Ranges card**

- **FR-005**: The ranges card MUST list an "All ranges" row first, then each range in fill order: highest weight first, then lowest start. This is the order in which the pool allocates.
- **FR-006**: Each range row MUST show:
  - the range, with thousands separators, for example "64,512 – 65,000"
  - "Weight N" on the right
  - a usage bar that shows the share used on the default branch and the share used only on other branches, with the percentage used
  - a tooltip on the usage that shows "<used> of <size>"
- **FR-007**: The "All ranges" row MUST show "N ranges" on the right and the pool's total usage, with the same bar and tooltip.
- **FR-008**: Users MUST be able to select "All ranges" or one range. The selected row MUST be visibly marked.

**Allocated numbers table**

- **FR-009**: The table MUST list only the numbers in the selected range, or in every range when "All ranges" is selected.
- **FR-010**: The table MUST show these columns, in this order:
  - **Number**: right-aligned, with thousands separators
  - **Object**: the holder node's label, linked to the node on the row's branch
  - **Kind**: the holder node's kind
  - **Branch**: the branch name, with a branch icon when it is not the default branch
  - **Range**: shown only when "All ranges" is selected and the pool has more than one range
  - **Source**: "Allocated" when the pool picked the number, "Provided" when a user gave it
- **FR-011**: Above the table, the body MUST show the title "Allocations" and the total count of numbers in the current selection.
- **FR-012**: The table MUST load more rows as the user scrolls, keep the column headers visible while scrolling, and show a loading row while the next rows load.
- **FR-013**: Selecting another range MUST reset the table to its first rows and scroll it back to the top.
- **FR-014**: The table MUST NOT offer search or filters in this work.

**Keyboard**

- **FR-015**: Users MUST be able to use the ranges card and the table with the keyboard only:
  - Tab moves focus into and out of the ranges card and the table.
  - The arrow keys move between rows.
  - Enter selects a range, or opens the holder node from the table.

**Empty and error states**

- **FR-016**: The body MUST show the messages listed under Edge Cases for a pool with no ranges, a pool with no numbers, a range with no numbers and a range that is not in the pool.

### Key Entities *(include if feature involves data)*

- **Number pool**: hands out unique numbers for one attribute of one kind of node, for example the ASN of a device. It is branch-agnostic: the same pool exists on every branch. In this work, the pool has no allocation scope.
- **Number pool range**: a span of numbers the pool hands out from, with a start, an end and a weight. A pool fills its ranges by highest weight first, then lowest start. Ranges are branch-agnostic.
- **Allocation**: one number held by one node on one branch. It records the number, the branch, the holder node (label, kind, ID), how the number got there (allocated by the pool or provided by a user) and the range that holds it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every range, the page shows the same used and size figures as the backend returns, and the "All ranges" figures equal the pool's figures. Checked on a pool with at least two ranges.
- **SC-002**: A user who opens a shared `/ranges/<range_id>` address views the same range selected and the same numbers as the person who shared it, in 100% of attempts.
- **SC-003**: A user can select a range, scroll the whole table and open a holder node using only the keyboard, with no step that requires a mouse.
- **SC-004**: In a pool holding 50,000 numbers, a user can scroll from the first row to the last without the page freezing, and every number appears exactly once, with none missing.
- **SC-005**: Everything a user could do with the previous body can still be done on a number pool's page:
  - view each range's usage
  - list the numbers in one range
  - open the node that holds a number

  The properties card is the exception, because the header shows the same information.

## Assumptions

- **Users**: network engineers and operators who manage number pools. Their main question is "which numbers are taken, where, and by which node?".
- **Scope of v1**: only pools without an allocation scope. The following are not part of this work:
  - allocation scopes: the scope picker, the scope table and choosing a division
  - search and filters on the table: number search, source filter, branch filter
  - any change to the header, including a button to add a range
  - a redirect from old `resources/<id>` addresses
- **Pools with an allocation scope**: this work adds nothing for them; another PR handles them. Until it lands, their body shows the error the backend returns when asked for a scoped pool's usage without a division.
- **Data source**: the body reads the pool's ranges, their usage and the allocated numbers from the number pool queries described in [PR #10932](https://github.com/opsmill/infrahub/pull/10932) ([IFC-3347](https://opsmill.atlassian.net/browse/IFC-3347)). Those queries currently answer from a fixed set of fake data, and they will read the database later. When that happens is not known.
- **Usage figures**: the backend counts a number as used if it is held on any live branch, and it returns used and size counts for each range and for the pool.
- **Range order**: the backend returns ranges ordered by start. The frontend re-sorts them into fill order, using the same rule as the backend.
- **Weight**: the backend returns 0 for a range that declares no weight, so the page cannot tell "no weight" apart from "weight 0".
- **Unknown range**: the backend returns an error when asked for the numbers of a range that is not in the pool.
- **Testing**: until the queries read the database, every real pool returns the fake data for a pool with an allocation scope, so the page can only be checked through component tests on fake responses that follow the contract. The end-to-end test against real data is written once the queries read the database. It is tracked in its own ticket, linked to IFC-3347, and must pass before `feature-number-pools-1.12` merges into `stable`. This follows the constitution's principle IV, which states that a feature is not complete until its end-to-end tests pass.
- **Changelog**: the body is a user-visible change and needs a changelog fragment.

## Planning Inputs

Decisions taken before this specification. They belong to planning rather than to the requirements above, and are recorded here so `/speckit-plan` starts from them.

- **Queries**: the body uses only `InfrahubNumberPoolUtilization` (without `division`) and `InfrahubNumberPoolAllocations` from PR #10932. It does not use `InfrahubResourcePoolUtilization` or `InfrahubResourcePoolAllocated`. Selecting a range sets `range_id`.
- **Keyboard support**: the ranges card and the table are built on react-aria, so keyboard navigation comes from react-aria rather than from custom key handling. The table uses react-aria's `Table`, with its load-more and virtualized rendering for infinite scroll.
- **Where the table lives**: no react-aria table exists in the codebase. It is built inside the resource-manager entity UI, next to the header (`entities/resource-manager/ui/number-pool/`). It moves to a shared location only once a second table needs it, as the constitution's principle VII requires.
- **Branches**:
  - The body branch starts from `number-pool-header-ifc-3364`, the header PR (#10963).
  - It needs the GraphQL schema and generated frontend types from PR #10932 to type-check. It gets them by merging #10932's branch and running `pnpm codegen`. The only file that conflicts is the generated `graphql-cache.d.ts`.
  - #10932's stack is still changing, so the merge happens when implementation starts.
  - The body PR stays a draft until the header PR and #10932 are in `feature-number-pools-1.12`. It is then rebased onto that branch.
- **Test data**: the fake data in PR #10932 for a pool without an allocation scope (`pool_id: "mock-unscoped"`) holds two ranges and three numbers. It is too small for infinite scroll, and the full page cannot load it because the header reads the pool from the database. The body adds its own fake responses, shaped like the contract, in `frontend/app/tests/fake/`, covering:
  - a pool with more than 100 numbers
  - a pool with no ranges
  - a range with no numbers
  - a range that is not in the pool
