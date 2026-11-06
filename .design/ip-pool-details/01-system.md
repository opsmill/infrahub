# System inventory

## Covered by `@infrahub/ui` and the app

- `Card`, `ListBox`, `ListBoxItem` with `selectionIndicator="highlight"` and `href` navigation: the resource prefix list, like the number pool ranges card (`frontend/app/src/entities/resource-manager/ui/number-pool/details/number-pool-ranges-card.tsx`).
- `Button`, `Menu`, `MenuItem`, `MenuSection`, `MenuTrigger`, `Popover`, `Sheet`, `Tooltip`: the Actions menu, like `number-pool-actions-menu.tsx`.
- `MultipleProgressBar` (`frontend/app/src/shared/components/stats/multiple-progress-bar.tsx`) and the tooltip layout of `number-pool-usage-bar.tsx`: the usage bar.
- `Table`, `Virtualizer`, `TableLayout`, `TableLoadMoreItem` from `react-aria-components`, as in `number-pool-allocations-table.tsx`: the allocated table that loads on scroll.
- `Content.Card`, `Row`, `Col`, `Link`, `CopyToClipboardButton`, `RefreshButton`, `NodeMetadataPopover`, `SchemaViewerModal`, `Skeleton`, `ErrorScreen`, `LoadingIndicator`.
- Tokens: `text-foreground-muted`, `bg-content-muted`, `border-border/50`, `--accent-strong`, `tabular-nums`.
- Routing: `constructPath`, `constructPathForIpam`, `getObjectDetailsUrl`, `ReactAriaRouterProvider`.
- Forms: `ObjectEdit` opens `IpPrefixPoolForm` or `IpAddressPoolForm` by kind.

## Close

- `ResourcePoolUtilization.tsx` draws the old 3-px bar with a cyan percentage and generic tooltips. The number pool usage bar is the closer match (1.5-px bar, figures in the tooltip), so the IP page uses that layout and the old component goes.
- `resource-selector.tsx` lists resource prefixes with a "View" link each. It lacks selection state, usage split and weight, and opens a side panel. Replaced.
- `number-pool-usage-bar.tsx` takes `NumberPoolUsage` (counts with a size). IP utilization is percentages only, so the IP page needs its own small bar over the same `MultipleProgressBar`, with the same tooltip layout.

## Missing

- An IP pool entity chain (`api/get-ip-pool-from-api.ts`, `domain/model/ip-pool.ts`, `ui/queries/get-ip-pool.query.ts`): the old page used the generic `useGetObject`. One file per layer, like the number pool chain.
- A query for the allocation weight of resource prefixes: the utilization query's `weight` is the prefix size. A dynamic query per weighted prefix kind, built with `jsonToGraphQLQuery`, fills the gap.
- An infinite query over `InfrahubResourcePoolAllocated`: the old page paged with `usePagination`.
- A deterministic order for resource prefixes: the backend returns them in set order.
