# Contract: routes, query hooks and components of the body

**Spec**: [../spec.md](../spec.md) | **Data model**: [../data-model.md](../data-model.md) | **Research**: [../research.md](../research.md)

## Addresses

| Address | Shows | Spec |
|---|---|---|
| `/resource-manager/<poolId>` | Header + body with "All ranges" selected | FR-003 |
| `/resource-manager/<poolId>/ranges/<rangeId>` | Header + body with that range selected | FR-003 |
| `/resource-manager/<poolId>/resources/<id>` on a number pool | Header + body with "All ranges" selected (no redirect, the old view is gone) | FR-001, FR-003 |
| Any of the above on an IP prefix or IP address pool | Unchanged | FR-002 |

Both addresses keep the `branch` and `at` query parameters of the current address (`constructPathForIpam`).

Route change in `app/router.tsx`, as a sibling of `resources/:resourceId` under `:resourcePoolId`:

```ts
{ path: "ranges/:rangeId" }
```

The route has no element. `NumberPoolDetailsPage` reads `rangeId` with `useParams<{ rangeId?: string }>()` (research R6).

URL helper change in `entities/nodes/object/ui/routing/object-urls.ts::getObjectDetailsUrl`: the resource-manager branch appends `tabSegment`, as the other branches already do:

```ts
getObjectDetailsUrl(NUMBER_POOL_KIND, poolId)                          // /resource-manager/<poolId>
getObjectDetailsUrl(NUMBER_POOL_KIND, poolId, undefined, `ranges/${id}`) // /resource-manager/<poolId>/ranges/<id>
```

## Query hooks (`entities/resource-manager/ui/queries/`)

| Hook | File | Key (in `resource-manager.query-keys.ts`) | Returns |
|---|---|---|---|
| `useGetNumberPoolUtilization(poolId)` | `get-number-pool-utilization.query.ts` | `numberPoolUtilization({ poolId, branchName, atDate })` | `useQuery` of `NumberPoolUtilization` |
| `useGetNumberPoolAllocations({ poolId, rangeId })` | `get-number-pool-allocations.query.ts` | `numberPoolAllocations({ poolId, rangeId, branchName, atDate })` | `useInfiniteQuery` of `GetNumberPoolAllocationsResult` pages; page size `NUMBER_POOL_ALLOCATIONS_PAGE_SIZE = 100` |

Both hooks read the branch with `useCurrentBranch()` and the time with `datetimeAtom`, like `useGetNumberPool`. The header's `RefreshButton queryKey={[]}` already refreshes every query, these two included.

## Components

### `NumberPoolDetailsPage`: `pages/resource-manager/number-pool-details.tsx` (changed)

Keeps the header exactly as it is. Replaces `ResourcePoolDetailsBody` with:

```
<Content.Card>
  <NumberPoolHeader … />                       // unchanged
  <NumberPoolBodyLayout>                       // two columns: ranges card | table card
    <NumberPoolRangesCard … />
    <table area: state per data-model "States the page derives">
  </NumberPoolBodyLayout>
</Content.Card>
```

The page owns the utilization query's loading and error states, reads `rangeId`, finds the selected range, and chooses the table area's content. Composition stays in `pages/`; each piece is an entity UI component.

### `NumberPoolRangesCard`: `entities/resource-manager/ui/number-pool/number-pool-ranges-card.tsx` (new)

```ts
interface NumberPoolRangesCardProps {
  poolId: string;
  poolType: NumberPoolType;
  utilization: NumberPoolUtilization;
  selectedRangeId: string | null; // null = "All ranges"; an unknown ID selects nothing
}
```

- Title "Ranges".
- `ListBox` (`@infrahub/ui`) with `aria-label="Ranges"`, `selectionMode="single"`, `selectionIndicator="highlight"`, `selectedKeys`.
- First item: `id="all"`, links to the pool's address. It shows "All ranges", "N ranges" (or "1 range") and the pool's usage bar.
- Next items: one per range in `utilization.ranges` order. Each links to the range address and shows "<start> – <end>", "Weight N" and its usage bar.
- With no ranges: "No ranges", followed by "Edit the pool to add one" (`User`) or "Add one in the schema" (`Schema`).

### `NumberPoolUsageBar`: `entities/resource-manager/ui/number-pool/number-pool-usage-bar.tsx` (new)

```ts
interface NumberPoolUsageBarProps {
  usage: NumberPoolUsage;
}
```

`MultipleProgressBar` with two segments (default branch, other branches only), then the percentage. Tooltips are listed in research R10.

### `NumberPoolAllocationsTable`: `entities/resource-manager/ui/number-pool/number-pool-allocations-table.tsx` (new)

```ts
interface NumberPoolAllocationsTableProps {
  poolId: string;
  ranges: NumberPoolRange[];
  selectedRange: NumberPoolRange | null; // null = "All ranges"
}
```

- Calls `useGetNumberPoolAllocations({ poolId, rangeId: selectedRange?.id })`.
- Title "Allocations" with the total `count`.
- `Virtualizer` + `TableLayout` + react-aria `Table` with `aria-label="Allocations"`. The columns are Number, Object, Kind, Branch, Range (only when `selectedRange` is null and `ranges.length > 1`) and Source.
- `TableLoadMoreItem` calls `fetchNextPage` while `hasNextPage`.
- The empty state reads "No allocations yet" (no `selectedRange`) or "No allocations in <start> – <end>".
- A query error shows `ErrorScreen`.
- The page renders it with `key={selectedRange?.id ?? "all"}`, so a new selection starts at the top (FR-013).

### `NumberPoolUnknownRange`: inline in the page, or a small entity component

"This range is not part of the pool", with a `Link` to `getObjectDetailsUrl(NUMBER_POOL_KIND, poolId)` labelled "All ranges".

## Accessible names used by tests

| Element | Role and name |
|---|---|
| Ranges list | `listbox` "Ranges" |
| A range | `option` whose name starts with "1 – 50" (match the start of the name, never the whole name) |
| "All ranges" | `option` whose name starts with "All ranges" |
| Numbers table | `grid` "Allocations" |
| Holder link | `link` with the holder's label |
| Unknown-range link | `link` "All ranges" |
