# Research: Number pool body for pools without an allocation scope

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-08

Each entry gives the decision, why it was chosen, and what else was considered. Sources are the frontend guidelines under `dev/guidelines/frontend/` and `dev/knowledge/frontend/`, the installed `react-aria-components` 1.20.0, and the contract in [PR #10932](https://github.com/opsmill/infrahub/pull/10932).

## R1. Data source: the dedicated number pool queries

- **Decision**: read ranges and usage with `InfrahubNumberPoolUtilization(pool_id)` (no `division`), and numbers with `InfrahubNumberPoolAllocations(pool_id, range_id?, offset, limit)`.
- **Rationale**:
  - They return the used and size counts (`figures.size`, `used`, `used_default_branch`, `used_branches`) that the tooltip "<used> of <size>" needs.
  - `range_id` limits the numbers to one range.
  - Each row carries the holder node (`id`, `kind`, `display_label`) and the `provenance`.
- **Alternatives considered**: `InfrahubResourcePoolUtilization` and `InfrahubResourcePoolAllocated`. They return percentages only, they ignore `resource_id` for number pools, and they return neither the holder node's label nor the provenance.
- **Constraint**: until [IFC-3347](https://opsmill.atlassian.net/browse/IFC-3347) reads the database, both queries answer from fake data. Any real pool ID gets the scoped fake pool, which `InfrahubNumberPoolUtilization` refuses without `division`.

## R2. Scalar types from gql.tada

- **Decision**: the mappers convert every `BigInt` field (`size`, `used`, `used_default_branch`, `used_branches`, `start`, `end`, `weight`, `value`, `count`) with `Number(...)`.
- **Rationale**: the app's gql.tada setup declares no custom scalars, so `BigInt` fields are typed `unknown`. The existing `getResourceAllocated` already casts `count as number`. Values stay below `Number.MAX_SAFE_INTEGER`; the largest common pool is the 32-bit ASN space.
- **Alternatives considered**: declaring a `BigInt` scalar in the gql.tada config. That changes every existing query's types, which is outside this work.

## R3. Ranges list: `@infrahub/ui` `ListBox` with link items

- **Decision**: build the ranges card with `ListBox` and `ListBoxItem` from `@infrahub/ui`:
  - `selectionMode="single"`
  - `selectedKeys` set from the URL
  - `selectionIndicator="highlight"`
  - each `ListBoxItem` has `href` set to the range's URL
- **Rationale**:
  - In 1.20.0, the default `selectionBehavior="toggle"` forces `linkBehavior="override"`, so pressing or Enter-ing an item navigates and never changes the selection (`useListBox`). The URL alone decides which item is selected.
  - The controlled `selectedKeys` still marks the current item with `aria-selected="true"` and the highlight styles.
  - Arrow keys and type-ahead come from react-aria.
  - The app mounts react-aria's `RouterProvider` (`app/providers/react-aria-router-provider.tsx`), so `href` navigates on the client.
  - The `highlight` indicator applies the same `bg-selected` classes as the IPAM, hierarchy and diff trees.
- **Alternatives considered**:
  - `RadioGroup`: it has no `href`, so navigation needs `onChange` and `navigate`.
  - `GridList`: its default `linkBehavior="action"` conflicts with selection.
  - The prototype's hand-written `role="radio"` buttons: they need custom key handling, which FR-015 rules out.
- **Not virtualized**: a pool has few ranges, and the `virtualized` row height (30px) is too short for a row with a bar.

## R4. Allocated numbers table: react-aria `Table` in a `Virtualizer`

- **Decision**: `Virtualizer` with `TableLayout` around a react-aria `Table`, built as follows:
  - `TableBody` holds a `Collection` of rows, followed by a `TableLoadMoreItem` with `onLoadMore` and `isLoading`.
  - The Object cell holds a `Link`. Rows have no `href`.
- **Rationale**:
  - In 1.20.0, `TableLayout` keeps the header sticky (`isSticky`) and renders only the visible rows (SC-004).
  - `TableLoadMoreItem` loads the next page when the user scrolls within one viewport of the end.
  - In the default `keyboardNavigationBehavior="arrow"`, Up and Down move between rows, and moving into a cell focuses its first focusable child. So the Object link is reachable by keyboard (FR-015).
  - `scrollPaddingTop` set to the header height keeps a focused row out from under the sticky header.
- **Constraints**:
  - The `Table` element is the scroll container: `overflow-auto` with a bounded height.
  - Rows have a fixed `rowHeight`, because the layout positions rows absolutely.
- **Alternatives considered**:
  - `shared/components/table/data-table.tsx` (TanStack) and the hand-written `<table>` of the prototype: neither provides react-aria keyboard navigation.
  - Page buttons (`Pagination`): rejected by the user in favour of infinite scroll.
- **Location**: `entities/resource-manager/ui/number-pool/`. It is the only react-aria table in the app, and constitution principle VII asks for two callers before a shared component is extracted.

## R5. Infinite query

- **Decision**: `infiniteQueryOptions` in `ui/queries/get-number-pool-allocations.query.ts`, built as follows:
  - Page size: `NUMBER_POOL_ALLOCATIONS_PAGE_SIZE = 100`, declared in `ui/queries`.
  - Offsets: `initialPageParam: 0` and `getNextPageParam`, which stops once the loaded rows reach `count`.
  - Rows: the table flattens `data.pages`.
- **Rationale**:
  - This follows the pattern in `entities-structure.md` § "queryOptions Live in ui/queries/" and in `get-branches.query.ts`.
  - The page size is a UI concern, so the domain receives `limit` and never sets a default (`entities-structure.md` § "`shared/` vs entities").
  - Stopping on `count` avoids one extra request when the last page is exactly full.
- **Alternatives considered**: `infiniteQueryOptionsWithOptimizedPageSize`. It needs a separate count query and changes the page size as the total grows, which this table does not need.
- **Range change (FR-013)**: `rangeId` is part of the query key, so selecting another range starts a new query from offset 0. The table also gets `key={rangeId}`, so its scroll position resets to the top.

## R6. Routes and the selected range

- **Decision**: add a child route `ranges/:rangeId` under `/resource-manager/:resourcePoolId`, with no element. `NumberPoolDetailsPage` reads the optional `rangeId` with `useParams<{ rangeId?: string }>()`.
- **Rationale**:
  - `route-architecture.md` § "Reading route params" allows `useParams<T>()` for optional params.
  - React Router gives every match the merged params, so the parent reads `rangeId`.
  - "All ranges" is the pool's own address, so no index route is needed.
  - An index child under `:resourcePoolId` would also render inside the IP pools' `Outlet`, which FR-002 forbids.
- **Alternatives considered**: separate index and `ranges/:rangeId` child shims with outlet context (`route-architecture.md` § "Detail-page route shape"). Rejected because of the index-route clash with IP pools, and because the ranges card and the table share one state (the selected range), so a shim would add no separation.
- **URL helper**: `getObjectDetailsUrl(kind, id, overrideParams, tabSegment)` is the helper for resource-manager addresses (`url-construction.md`). Its resource-manager branch ignores `tabSegment` today. The plan adds it, so `getObjectDetailsUrl(NUMBER_POOL_KIND, poolId, undefined, "ranges/<id>")` returns `/resource-manager/<pool>/ranges/<id>`, carrying `branch` and `at` from the current address.
- **Breadcrumb**: `BreadcrumbResourceManager` adds a crumb only for `resourceId`. It shows "Resource manager > <pool>" on a range address. A range crumb is not part of this work.

## R7. Default branch in the Branch column and the holder link

- **Decision**: find the default branch with `useGetBranches()` and `is_default`. For a row on the default branch:
  - the Branch cell shows the name without the branch icon
  - the holder link passes `{ name: QSP.BRANCH, exclude: true }`

  For any other row:
  - the Branch cell shows the branch icon (lucide `GitBranchIcon`)
  - the holder link passes `{ name: QSP.BRANCH, value: row.branch }`
- **Rationale**: `dev/knowledge/frontend/branches.md` forbids comparing a branch name with `"main"`, because a deployment can rename the default branch. The prototype's `a.branch === "main"` is not reused. A link that does not name the branch would inherit the user's current branch, which breaks the "holder opens on the row's branch" scenario.

## R8. Fill order sorted in the frontend

- **Decision**: a pure rule `sortRangesByFillOrder` in `domain/rules/`: highest `weight` first, then lowest `start`, then lowest `end`. This is the backend's order in `backend/infrahub/pools/number_ranges.py` (sorted by `-weight, start, end`).
- **Rationale**: the user chose to show ranges in fill order, and the backend returns them by start.
- **Deviation**: `entities-structure.md` and `page-architecture.md` § "Backend is authoritative" say not to mirror server sort order on the client. The deviation is recorded in the plan's Complexity Tracking. The rule has a unit test, so a change in the backend order is a one-file change here.

## R9. Number and percentage display

- **Decision**:
  - Numbers and range bounds use `formatNumberDisplay` from `shared/utils/number.ts`. A range reads "<start> – <end>", built from `start` and `end`, not from `display_label` ("1 - 50").
  - The percentage uses the API's `utilization` with a local formatter. It shows "0%" for zero, "<0.1%" below 0.1, one decimal below 10, and whole numbers above.
- **Rationale**: the prototype's display was approved. `formatNumberDisplay` already wraps `Intl.NumberFormat`.

## R10. Usage bar

- **Decision**: a `NumberPoolUsageBar` built on `MultipleProgressBar` (`shared/components/stats/multiple-progress-bar.tsx`), configured as follows:
  - Two segments: `used_default_branch / size` and `used_branches / size`.
  - Segment tooltips: "Default branch: <used> of <size>" and "Other branches only: <used> of <size>".
  - A percentage label follows the bar, with the tooltip "<used> of <size>".
- **Rationale**: this is the prototype's `UsageBar`, driven by counts instead of fake data. `ResourcePoolUtilization` takes percentages only and has no "of" tooltip, so it is not reused.

## R11. Empty, error and unknown-range states

- **Decision**:
  - **Utilization query is pending:** the body shows a loading state. **It fails:** the body shows `ErrorScreen` with the message. On a scoped pool this is the backend's refusal, which is accepted until the scope work lands.
  - **No ranges:** the ranges card shows "No ranges" with a hint chosen by `pool_type` ("Edit the pool to add one" for `User`, "Add one in the schema" for `Schema`). The table area shows nothing more.
  - **Unknown range:** `rangeId` is set but not in `utilization.ranges`. The table area shows "This range is not part of the pool" with a `Link` to "All ranges", and the allocations query is not called.
  - **Allocations query fails:** the table area shows `ErrorScreen`. This also covers a range deleted between the two requests, which the backend refuses with an error.
  - **No numbers:** `count === 0` shows "No allocations yet" for "All ranges", or "No allocations in <range>" for one range. It is rendered through `TableBody`'s `renderEmptyState`.

## R12. The existing end-to-end test on the old properties card

- **Decision**: delete `tests/e2e/resource-manager/test_number_pool.py::TestNumberPool::test_displays_correct_details_for_created_number_pool`.
- **Rationale**:
  - It asserts cells of the old properties card ("speed", "1", "10"), which this work removes.
  - Its pool name and attribute are already covered by `test_header_for_user_created_pool`.
  - Its range bounds cannot be checked on the new body until IFC-3347 reads the database, because a real pool gets the scoped fake data and the body shows the refusal.
  - The end-to-end test tracked for the body (linked to IFC-3347) adds range and number checks back.
- **Alternatives considered**: rewriting it to assert the new body. That is not possible while the queries return fake data.

## R13. Agent context update

- **Finding**: `CLAUDE.md` contains only `@AGENTS.md`, and neither file has `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` markers, so the plan step that updates the plan reference between them has nothing to update. No markers are added, because `AGENTS.md` is shared project guidance.
