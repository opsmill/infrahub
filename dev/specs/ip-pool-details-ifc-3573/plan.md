# Implementation Plan: Redesign the IP prefix pool and IP address pool details page

**Branch**: `ple-ip-pool-details-ifc-3573` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

## Summary

Rebuild the IP pool details page on the number pool page's layout, from the approved "Dots" prototype (commit `8827d389b5`). Frontend only. The page gets its own entity chain (api, domain, ui) beside the number pool chain, reuses the number pool pieces that are identical, and keeps the `/resource-manager/:resourcePoolId/resources/:resourceId` route so the breadcrumb keeps working.

Three plans were compared (minimal change, refactor-friendly, test-first). The synthesis takes the typed entity chain and the shared pieces from the refactor-friendly plan, the single-query allocations count from the minimal plan, and the test list and e2e data answer from the test-first plan.

## Technical Context

- **Language**: TypeScript, React 19, TanStack Query, react-aria-components, gql.tada.
- **Backend**: unchanged. Queries used: `CoreIPPrefixPool` / `CoreIPAddressPool` node, `InfrahubResourcePoolUtilization`, `InfrahubResourcePoolAllocated`, and `CoreWeightedPoolResource(ids)` for the allocation weight.
- **Testing**: Vitest browser mode (component tests next to each component), unit tests for rules and mappers, pytest-playwright e2e under `tests/e2e/resource-manager/`.
- **Constraints**: the number pool page's behaviour must not change (FR-021), apart from keeping loaded allocations when a refresh fails, and keeping them and offering a Retry button when loading more rows fails; every other number pool change is a verbatim move of JSX into `ui/pool/`.

## Decisions

1. **Typed pool fetch, not `useGetObject`.** `api/get-ip-pool-from-api.ts` selects both kinds in one document. The typed node gives the defaults and the namespace's `default` flag, which the namespace link needs (the default namespace is the absence of the `namespace` query parameter).
2. **Allocation weight comes from the weighted pool resource generic.** The utilization query's `weight` is the prefix size. The hook derives `weightedKinds` (node schemas that inherit both `BuiltinIPPrefix` and `CoreWeightedPoolResource`) from `nodeSchemasAtom`. When every resource prefix kind is weighted, the use case runs one typed `CoreWeightedPoolResource(ids)` query; otherwise it skips the query, because the backend then ignores weights. If the query throws, the list shows no weights instead of an error. `weightedKinds` is part of the query key.
3. **One use case for utilization.** `getIpPoolUtilization` fetches utilization and weights, maps and sorts: weight descending with a missing weight as 0, which is the server's fill order, then, as the page's own choice, by prefix (IP version, address, prefix length). The page starts this query alongside the pool query; the page body and the breadcrumb read the same sorted list from the same cache key.
4. **Allocations: one infinite query, count from the first page.** `InfrahubResourcePoolAllocated` returns `count` with every page, so there is no separate count query. Page size 100, like the number pool.
5. **Shared pieces in `entities/resource-manager/ui/pool/`.** `PoolId`, `SchemaReference`, `UtilizationTooltipMessage`, `KindLabel`, `formatUsagePercent` and `PoolItemNotFound` move verbatim from the number pool files, and `PoolLoadMoreError` is new; `PoolActionsMenu` takes the common menu with `poolKind` and the update and delete decisions, and `NumberPoolActionsMenu` keeps the schema-lock rule and renders it. The usage bar, the list card, the table and the not-found state stay per pool kind: their inputs differ.
6. **Selection in the path.** `getIpPoolResourceUrl(poolId, resourceId?)` builds `/resource-manager/{poolId}/resources/{resourceId}`; `ListBoxItem href` navigates. Without a resource id the page selects the first resource prefix in list order without redirecting.
7. **Member type without a value reads "Member type has no default".** The backend has no fallback at allocation time.
8. **No Branch column.** The backend returns the viewing branch for every row.
9. **Delete the old page files.** `resource-pool-details-body.tsx`, `resource-allocation-details.tsx`, `resource-selector.tsx`, `ResourcePoolUtilization.tsx`, `get-pool-utilization.*`, `get-resource-allocated.*`, `shared/components/form/object-edit-slide-over-trigger.tsx`, `roundNumber` in `shared/utils/number.ts` and the `utilization`/`allocated` query keys go; `knip` confirms nothing dangles.
10. **Schema extension fields in the header.** `getIpPoolExtraFields` keeps the pool schema's attributes and single relationships that the page does not already show; the header reads them with `useGetObject` only when there is at least one.

## Constitution Check

- Schema-driven: the page reads kinds and labels from the loaded schema; nothing is hard-coded except the three pool kind constants and the IP prefix generic constant that already exist, the `CoreWeightedPoolResource` generic name, and the list of pool fields the header already shows (`get-ip-pool-extra-fields.ts`).
- Branch-safe: every query carries the current branch and date, which the old IP pool queries did not.
- Type safety: gql.tada documents and mapped domain types.
- Tests: unit tests for rules and mappers, a component test per component, an e2e file for both pool kinds on the default branch and on another branch.
- Simplicity: no new dependency; no IP parsing library (the sort rule parses the prefix itself to order ties by IP version, address and prefix length).

## Project Structure

```text
frontend/app/src/entities/resource-manager/
├── api/get-ip-pool-from-api.ts, ip-pool.mappers.ts (+test)
├── api/get-ip-pool-utilization-from-api.ts (renamed from get-pool-utilization-from-api.ts, + context)
├── api/get-ip-pool-resource-weights-from-api.ts (`CoreWeightedPoolResource`)
├── api/ip-pool-utilization.mappers.ts (+test)
├── api/get-ip-pool-allocations-from-api.ts (renamed from get-resource-allocated-from-api.ts, + context), ip-pool-allocation.mappers.ts (+test)
├── domain/model/ip-pool.ts
├── domain/rules/get-ip-pool-default-entries.ts, sort-ip-pool-resources-by-fill-order.ts, get-weighted-prefix-kinds.ts, get-ip-pool-extra-fields.ts (+tests)
├── domain/use-cases/get-ip-pool.ts, get-ip-pool-utilization.ts, get-ip-pool-allocations.ts (+tests)
├── ui/queries/get-ip-pool.query.ts, get-ip-pool-utilization.query.ts, get-ip-pool-allocations.query.ts, resource-manager.query-keys.ts
├── ui/routing/ip-pool-urls.ts (+test)
├── ui/pool/pool-id.tsx, schema-reference.tsx, utilization-tooltip-message.tsx, kind-label.tsx, pool-actions-menu.tsx,
│   format-usage-percent.ts (+test), pool-item-not-found.tsx, pool-load-more-error.tsx
└── ui/ip-pool/details/ip-pool-header.tsx, ip-pool-defaults-line.tsx, ip-pool-actions-menu.tsx, ip-pool-usage-bar.tsx,
    ip-pool-resources-card.tsx, ip-pool-allocations-card.tsx, ip-pool-allocations-table.tsx, ip-pool-extra-fields.tsx (+tests)
frontend/app/src/pages/resource-manager/ip-pool-details.tsx (+test), resource-pool-details.tsx
frontend/app/src/entities/ipam/ip-namespaces/ui/routing/ipam-urls.ts (+test)
frontend/app/src/entities/navigation/ui/breadcrumbs/breadcrumb-resource-manager.tsx (+test)
frontend/app/src/app/router.tsx
frontend/app/src/shared/utils/number.ts (`roundNumber` removed)
frontend/app/src/shared/components/form/object-edit-slide-over-trigger.tsx (deleted)
frontend/app/tests/fake/ip-pool.ts
tests/e2e/resource-manager/test_ip_pool_details.py, test_resource_pool.py; tests/e2e/test_breadcrumb.py
docs/docs/tutorials/getting-started/resource-manager.mdx
dev/specs/e2e-pytest-sharding.md
changelog/+ifc-3573-ip-pool-details.changed.md, +number-pool-allocations-next-page-error.fixed.md
```

## Complexity Tracking

| Choice | Why | Simpler option rejected because |
|---|---|---|
| Shared `PoolActionsMenu` | Two menus that differ in two props | Copying 120 lines into the IP menu doubles the surface for the next change |
