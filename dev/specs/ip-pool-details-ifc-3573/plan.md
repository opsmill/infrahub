# Implementation Plan: Redesign the IP prefix pool and IP address pool details page

**Branch**: `ple-ip-pool-details-ifc-3573` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

## Summary

Rebuild the IP pool details page on the number pool page's layout, from the approved "Dots" prototype (commit `8827d389b5`). Frontend only. The page gets its own entity chain (api, domain, ui) beside the number pool chain, reuses the number pool pieces that are identical, and keeps the `/resource-manager/:resourcePoolId/resources/:resourceId` route so the breadcrumb keeps working.

Three plans were compared (minimal change, refactor-friendly, test-first). The synthesis takes the typed entity chain and the shared pieces from the refactor-friendly plan, the single-query allocations count from the minimal plan, and the test list and e2e data answer from the test-first plan.

## Technical Context

- **Language**: TypeScript, React 19, TanStack Query, react-aria-components, gql.tada, `json-to-graphql-query` for the one dynamic query.
- **Backend**: unchanged. Queries used: `CoreIPPrefixPool` / `CoreIPAddressPool` node, `InfrahubResourcePoolUtilization`, `InfrahubResourcePoolAllocated`, and `BuiltinIPPrefix(ids)` with inline fragments for the allocation weight.
- **Testing**: Vitest browser mode (component tests next to each component), unit tests for rules and mappers, pytest-playwright e2e under `tests/e2e/resource-manager/`.
- **Constraints**: the number pool page's behaviour must not change (FR-021); every number pool file touched gets only a verbatim move of JSX into `ui/pool/`.

## Decisions

1. **Typed pool fetch, not `useGetObject`.** `api/get-ip-pool-from-api.ts` selects both kinds in one document. The typed node gives the defaults and the namespace's `default` flag, which the namespace link needs (the default namespace is the absence of the `namespace` query parameter).
2. **Allocation weight comes from the resource prefix node.** The utilization query's `weight` is the prefix size. The hook derives `weightedKinds` (node schemas that inherit `BuiltinIPPrefix` and have an `allocation_weight` attribute) from `nodeSchemasAtom`; the use case runs one `BuiltinIPPrefix(ids)` query with an inline fragment per weighted kind, built with `jsonToGraphQLQuery`, and skips it when there is no weighted kind. `weightedKinds` is part of the query key.
3. **One use case for utilization.** `getIpPoolUtilization` fetches utilization and weights, maps and sorts (weight descending, missing weight as 0, then prefix with numeric collation). The page and the breadcrumb read the same sorted list from the same cache key.
4. **Allocations: one infinite query, count from the first page.** `InfrahubResourcePoolAllocated` returns `count` with every page, so there is no separate count query. Page size 100, like the number pool.
5. **Shared pieces in `entities/resource-manager/ui/pool/`.** `PoolId`, `SchemaReference`, `UtilizationTooltipMessage`, `KindLabel` move verbatim from the number pool files; `PoolActionsMenu` takes the common menu with `poolKind` and the update and delete decisions, and `NumberPoolActionsMenu` keeps the schema-lock rule and renders it. The usage bar, the list card, the table and the not-found state stay per pool kind: their inputs differ.
6. **Selection in the path.** `getIpPoolResourceUrl(poolId, resourceId?)` builds `/resource-manager/{poolId}/resources/{resourceId}`; `ListBoxItem href` navigates. Without a resource id the page selects the first resource prefix in list order without redirecting.
7. **Member type without a value reads "Member type has no default".** The backend has no fallback at allocation time.
8. **No Branch column.** The backend returns the viewing branch for every row.
9. **Delete the old page files.** `resource-pool-details-body.tsx`, `resource-allocation-details.tsx`, `resource-selector.tsx`, `ResourcePoolUtilization.tsx`, `get-pool-utilization.*`, `get-resource-allocated.*` and the `utilization`/`allocated` query keys go; `knip` confirms nothing dangles.

## Constitution Check

- Schema-driven: the page reads kinds and labels from the loaded schema; nothing is hard-coded except the three pool kind constants that already exist.
- Branch-safe: every query carries the current branch and date, which the old IP pool queries did not.
- Type safety: gql.tada documents and mapped domain types; the one dynamic query returns a typed map.
- Tests: unit tests for rules and mappers, a component test per component, an e2e file for both pool kinds on the default branch and on another branch.
- Simplicity: no new dependency; no IP parsing library (numeric collation on the prefix string is enough for ordering ties).

## Project Structure

```text
frontend/app/src/entities/resource-manager/
├── api/get-ip-pool-from-api.ts, ip-pool.mappers.ts (+test)
├── api/get-ip-pool-utilization-from-api.ts (renamed from get-pool-utilization-from-api.ts, + context)
├── api/get-ip-pool-resource-weights-from-api.ts
├── api/ip-pool-utilization.mappers.ts (+test)
├── api/get-ip-pool-allocations-from-api.ts (renamed from get-resource-allocated-from-api.ts, + context), ip-pool-allocation.mappers.ts (+test)
├── domain/model/ip-pool.ts
├── domain/rules/get-ip-pool-default-entries.ts, sort-ip-pool-resources-by-fill-order.ts, get-weighted-prefix-kinds.ts (+tests)
├── domain/use-cases/get-ip-pool.ts, get-ip-pool-utilization.ts, get-ip-pool-allocations.ts (+tests)
├── ui/queries/get-ip-pool.query.ts, get-ip-pool-utilization.query.ts, get-ip-pool-allocations.query.ts, resource-manager.query-keys.ts
├── ui/routing/ip-pool-urls.ts (+test)
├── ui/pool/pool-id.tsx, schema-reference.tsx, utilization-tooltip-message.tsx, kind-label.tsx, pool-actions-menu.tsx
└── ui/ip-pool/details/ip-pool-header.tsx, ip-pool-defaults-line.tsx, ip-pool-actions-menu.tsx, ip-pool-usage-bar.tsx,
    ip-pool-resources-card.tsx, ip-pool-allocations-card.tsx, ip-pool-allocations-table.tsx (+tests)
frontend/app/src/pages/resource-manager/ip-pool-details.tsx (+test), resource-pool-details.tsx
frontend/app/src/entities/navigation/ui/breadcrumbs/breadcrumb-resource-manager.tsx
frontend/app/src/app/router.tsx
frontend/app/tests/fake/ip-pool.ts
tests/e2e/resource-manager/test_ip_pool_details.py, test_resource_pool.py; tests/e2e/test_breadcrumb.py
docs/docs/tutorials/getting-started/resource-manager.mdx; changelog/+ifc-3573-ip-pool-details.changed.md
.design/ip-pool-details/ (design-jam record)
```

## Complexity Tracking

| Choice | Why | Simpler option rejected because |
|---|---|---|
| Dynamic weights query | No static document can name user-defined prefix kinds | Reading `weight` from the utilization query: it is the prefix size |
| Shared `PoolActionsMenu` | Two menus that differ in two props | Copying 120 lines into the IP menu doubles the surface for the next change |
