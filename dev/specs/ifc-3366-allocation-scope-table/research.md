# Research: Allocation scope table for scoped number pools

All paths are relative to `frontend/app/src` unless they start with `tests/`, `docs/` or `changelog/`.

## R1. Where the data comes from

**Decision**: Use the three backend queries as they are:

- `InfrahubNumberPoolDivisions(pool_id)` lists the allocation scopes of the table.
- `InfrahubNumberPoolUtilization(pool_id, division)` returns the usage on the page of one allocation scope.
- `InfrahubNumberPoolAllocations(pool_id, division, …)` returns the allocations on that page.

**Rationale**: the checked-in `schema/schema.graphql` and the gql.tada introspection in `shared/api/graphql/generated/graphql-env.d.ts` already declare these queries, the `division` argument and every type they return. The frontend needs no codegen step and no GraphQL schema change.

**Alternatives considered**: a new query that lists every possible combination of values, including those that hold no numbers. The feature owner rejected it because it crosses the GraphQL gate (spec, Out of Scope).

## R2. How a URL identifies one allocation scope

**Decision**: One query string parameter, `allocation_scope`. Its value is a JSON array that holds one value per field of the pool's allocation scope, in the pool's order. For example, `?allocation_scope=["18a2…","leaf"]` for Device + Role.

- A relationship stores the peer's ID.
- An attribute stores the value with its JSON type: a number for a Number attribute, a boolean for a Boolean attribute and a string otherwise. This is the type the backend returns in `NumberPoolDivisionEntry.value` and expects in `NumberPoolDivisionEntryInput.value`.
- The `path` of each entry comes from the pool's `allocation_scope` names (`api/number-pool.mappers.ts::mapToNumberPoolData`), so the URL does not repeat field names.

**Rationale**:

- **Composes with ranges.** Ranges are already a path segment (`/resource-manager/:resourcePoolId/ranges/:rangeId`). A query parameter adds the allocation scope to that URL without a new route tree, and `ui/routing/number-pool-urls.ts::getNumberPoolRangeUrl` keeps it when it is in `NUMBER_POOL_PRESERVED_QSP`.
- **Keeps types.** JSON preserves the difference between `100` and `"100"`, which the backend needs.
- **Keeps working after a rename.** The values are positional, so the URL keeps working if a field is renamed.
- **Follows the existing pattern.** nuqs `parseAsJson` with a validator is the existing way to read a typed parameter (`entities/nodes/sort/ui/hooks/use-sort.ts::useSort` uses `createParser`).

**Alternatives considered**:

- **One parameter per field** (`?device=…&role=…`). The keys depend on the pool, nuqs cannot declare them statically, and they can collide with other parameters.
- **A path segment** (`/allocation-scopes/:key`). It needs new routes and a key encoding, and it nests awkwardly with `ranges/:rangeId`.
- **The display label** (`?allocation_scope=par1 · leaf`). Labels are not unique and cannot be turned back into peer IDs.

## R3. A URL that does not match the pool

**Decision**: The parser rejects a value that is not a JSON array of strings, numbers and booleans. The page then compares the array length with the number of fields in the pool's allocation scope. When the value cannot be parsed or the lengths differ, the page shows the message from the spec and the "All allocation scopes" link, without calling the backend. If the backend still refuses the request, for example because a number was hand-edited into a string, the existing `ErrorScreen` shows the backend message.

**Rationale**: the frontend can detect the cases the spec names (edited by hand, malformed) without parsing backend error text. Matching on the backend message would be fragile.

## R4. The label of the open allocation scope

**Decision**: The page of one allocation scope reads the labels ("Device: atl1-core1") from the allocation scope list, which is fetched with the same query key as the table, and finds the matching allocation scope in the summary component (R7). When the operator arrives from the table, the list is already cached. When no row of the list matches the URL, because all its numbers were released, the page shows the raw values from the URL.

**Rationale**: no backend query returns the labels of an allocation scope that holds no numbers. Fetching each peer separately would add one request per relationship for a rare case.

**Alternatives considered**: fetching each peer's display label with the object query. This adds requests and couples this entity to the node entity's API, which `entities-structure.md` forbids.

## R5. The table component

**Decision**: A plain `<table>`, as in the prototype (`pages/proto/number-pool/scope-table.tsx::ScopeTable`), that draws every row:

- **Header**: a sticky `<thead>`.
- **Columns**: one per field of the allocation scope. Each cell shows the value and, for a relationship, the peer kind below it in small mono text.
- **Usage column**: the last column, pinned with `position: sticky; right: 0`. It draws its own left edge and has an opaque background, as the prototype's `PINNED_EDGE` and `PINNED_SURFACE` do.
- **Horizontal scrolling**: the scroll container scrolls horizontally when the columns are wider than the card (FR-014).
- **Sorting**: each header is a button. The sorted header carries `aria-sort`.
- **Opening a row**: the first cell is the shared `Link`, so the browser's link actions work: open in a new tab, copy the link address. A click elsewhere on the row navigates to the same URL; a click with a modifier key is left to the link.
- **Empty states**: rendered under the table.

**Rationale**:

- **Pinning on the right.** The react-aria virtualizer positions every cell with inline `left` styles and only makes a column sticky at its left offset (`react-stately` `TableLayout::isStickyColumn`, `react-aria` `VirtualizerItem`). A usage column pinned on the right while the table scrolls horizontally would mean overriding react-aria's internal inline styles.
- **No virtualization for now.** The feature owner decided that the table draws every row now and gets virtualization later, so a plain table with CSS pinning meets every requirement without a new dependency.
- **`DataTable` does not fit.** `shared/components/table/data-table.tsx::DataTable` sorts only on the server, requires `NodeCore` rows and pins only on the left.

**Known limit**: on a very large pool, drawing every row is slow (spec, Out of Scope). Each usage bar wraps its segments in tooltips, so the row keeps its markup small and reuses `NumberPoolUsageBar` as it is.

**Alternatives considered**:

- **The react-aria virtualized table with CSS overrides of its inline positioning.** Fragile across upgrades.
- **Adding `@tanstack/react-virtual`.** It is a new dependency, and the feature owner deferred virtualization.
- **The prototype's 100-row cap.** The feature owner chose to show every row.

## R6. Search and sort state

**Decision**: Both are kept in the URL with nuqs, in one hook `ui/hooks/use-number-pool-division-table-state.ts`:

- **Search**: `allocation_scope_search`.
- **Sort**: `allocation_scope_sort`, written as `<field>:<asc|desc>`, where `<field>` is a scope field name or `usage`.
- **URL updates**: the URL is updated through `limitUrlUpdates: debounce(300)`, while React state updates on every key stroke.
- **Filtering**: the list is filtered with `React.useDeferredValue` on the search text, so the input stays responsive while the table redraws (SC-003).

The default sort is usage, highest first, which is also the backend order. The backend order is therefore used as it is when no sort is set (page-architecture: the backend owns defaults).

**Rationale**: the browser's Back button from an allocation scope page returns to the same search and sort, which matters when the table has thousands of rows. Two dedicated keys avoid `QSP.SORT`, whose format `useSort` parses differently.

**Alternatives considered**: local `useState`. It is simpler, but the operator loses the search when they come back from an allocation scope.

## R7. Where the helper functions live

**Decision**: This feature adds no `domain/rules` file. Every helper lives in the one `ui/` file that uses it, and is tested through that file's component or hook tests:

| Helper | Lives in | Does |
|---|---|---|
| Search filter | `number-pool-divisions-card.tsx` | Keeps the allocation scopes with any entry label that contains the search text, ignoring case |
| Sort | `number-pool-divisions-card.tsx` | Sorts by one entry's label with `localeCompare` and `numeric: true`, or by usage; ties keep the backend order |
| Selector from the URL | `ui/hooks/use-number-pool-division.ts` | Turns the URL values and the pool's field names into the request input, or reports a mismatch |
| Lookup of the open allocation scope | `number-pool-division-summary.tsx` | Finds the allocation scope whose values equal the URL values, for its labels |

**Rationale**: `domain/rules` holds business rules only, and none of these is one. Search, sort, URL parsing and label lookup serve the display. A function with one caller stays in its caller's file. This decision by the feature owner takes precedence over the general guideline in `page-architecture.md` to put pure helpers in `domain/rules`.

**Alternatives considered**: four `domain/rules` files with their own tests (the first version of this plan).

## R8. How the page branches

**Decision**: `pages/resource-manager/number-pool-details.tsx::NumberPoolBody` branches on two conditions:

- **Unscoped pool**: the current body, unchanged (FR-013).
- **Scoped pool, no `allocation_scope` parameter**: the allocation scopes card, full width.
- **Scoped pool with the parameter**: one of two outcomes.
  - If the parameter does not match the pool's allocation scope: the mismatch message.
  - Otherwise: the current ranges card and allocations card, with the division passed to their queries and an allocation scope summary above the ranges card.

The test "is this pool scoped" is `pool.allocation_scope.value.length > 0`. It is written inline, because it has a single caller.

**Rationale**: reuse the existing cards (spec, Assumptions; constitution VII). The page stays within its size budget by moving the scoped body into `entities/resource-manager/ui/number-pool/details/`.

## R9. End-to-end test data

**Decision**: Add one self-contained test to `tests/e2e/resource-manager/test_number_pool.py::TestNumberPool`. On the class's `number_pool_branch`, the test uses the SDK to:

- create a `CoreNumberPool` on `InfraInterfaceL3.speed` scoped by `device`, with the relationship's schema ID read from the branch schema
- create L3 interfaces on two devices from `data_sites` with `speed` taken from the pool

It then drives the UI:

- open the pool and check two rows, the fullest first
- search to one row
- open it and check its numbers
- reload the URL and check the same numbers

**Rationale**: `writing-e2e-tests.md` requires self-contained tests. The existing scoped pool is created by an earlier test in the chain, and no test allocates numbers into it.

**To verify during implementation**: that the SDK accepts `allocation_scope` as a list of `{id, name}` and allocates with `from_pool` on a Number attribute. If it does not, create the interfaces through a GraphQL mutation with `from_pool`, using the SDK client.

## R10. Documentation and changelog

**Decision**:

- **Documentation**: add a section on viewing a scoped pool to `docs/docs/resource-manager/overview.mdx`, under "Number pools". It explains the allocation scope, the table, opening an allocation scope, and that the API calls one row a "division".
- **Changelog**: add `changelog/+ifc-3366-number-pool-allocation-scopes.added.md`.

**Rationale**: the tutorial `allocate-number.mdx` uses VLANs scoped by nothing. `site` on a VLAN is optional, so the rule `domain/rules/can-number-pool-be-scoped-by.ts` excludes it and the tutorial cannot show a scoped pool. The overview is where the number pool features are described.

## R11. The prototype

**Decision**: The last task deletes `pages/proto/number-pool/` and its route in `app/router.tsx`, after the production page covers the table and the allocation scope page.

**Rationale**: every prototype file says "Delete with the prototype". `knip` reports its exports once nothing references them.
