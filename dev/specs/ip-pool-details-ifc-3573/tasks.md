---
description: "Task list for the IP prefix pool and IP address pool details page redesign"
---

# Tasks: Redesign the IP prefix pool and IP address pool details page

**Input**: [plan.md](plan.md), [spec.md](spec.md). Prototype: `git show 8827d389b5:frontend/app/src/proto/ip-pool-defaults/{shared,row-parts,s-dots}.tsx`.

**Tests**: included; each component has a test next to it, each rule and mapper a unit test, and one e2e file covers both pool kinds.

## Format: `[ID] [P?] [Story] Description`

Paths are under `frontend/app/` unless they start with `tests/`, `docs/` or `changelog/`. `$RM` = `src/entities/resource-manager`.

## Phase 1: Shared pieces (FR-021 gate)

- [x] T001 Create `$RM/ui/pool/pool-id.tsx`, `schema-reference.tsx`, `utilization-tooltip-message.tsx`, `kind-label.tsx` by moving the JSX verbatim out of `number-pool-header.tsx`, `number-pool-usage-bar.tsx`, `number-pool-allocations-table.tsx`; import them back there.
- [x] T002 Create `$RM/ui/pool/pool-actions-menu.tsx` (`PoolActionsMenu({ pool, poolKind, schema, updateDecision, deleteDecision, onDeleted })`) from `number-pool-actions-menu.tsx`; `NumberPoolActionsMenu` keeps the schema-lock decisions and renders it.
- [x] T003 Run `pnpm test src/entities/resource-manager/ui/number-pool src/pages/resource-manager` and `pnpm knip`; both green before phase 2.

## Phase 2: Data layer

- [x] T004 [P] `$RM/domain/model/ip-pool.ts`: `IpPoolData` (discriminated on `__typename`), `IpPoolResourceUsage`, `IpPoolResource`, `IpPoolUtilization`, `IpPoolAllocation`, `IpPoolAllocationsPage`, `IpPoolDefaultEntry`, member type constants.
- [x] T005 [P] `$RM/domain/rules/get-ip-pool-default-entries.ts` + test (US1 scenarios 1-4).
- [x] T006 [P] `$RM/domain/rules/sort-ip-pool-resources-by-fill-order.ts` + test (weights 100/100/50, ties by IP version, address and prefix length, labels that are not prefixes last whatever the input order, null as 0 last, non-mutating).
- [x] T007 [P] `$RM/domain/rules/get-weighted-prefix-kinds.ts` + test (kind inheriting both `BuiltinIPPrefix` and `CoreWeightedPoolResource` found; kind without the generic skipped; empty list).
- [x] T008 `$RM/api/get-ip-pool-from-api.ts` (both kinds, `ContextParams`), `ip-pool.mappers.ts` + test; `domain/use-cases/get-ip-pool.ts` + test ("IP pool not found"); `ui/queries/get-ip-pool.query.ts`.
- [x] T009 Rename `get-pool-utilization-from-api.ts` to `get-ip-pool-utilization-from-api.ts` with `ContextParams`; add `get-ip-pool-resource-weights-from-api.ts` (typed `CoreWeightedPoolResource(ids)` query); `ip-pool-utilization.mappers.ts` + test; `domain/use-cases/get-ip-pool-utilization.ts` + test (skips weights unless every resource prefix kind is weighted; no weights when the weights query throws; sorted output); `ui/queries/get-ip-pool-utilization.query.ts` (`useGetIpPoolUtilization(poolId)`, derives `weightedKinds` from `nodeSchemasAtom`).
- [x] T010 Rename `get-resource-allocated-from-api.ts` to `get-ip-pool-allocations-from-api.ts` with `ContextParams`; `ip-pool-allocation.mappers.ts` + test; `domain/use-cases/get-ip-pool-allocations.ts` (returns `{ count, allocations }`); `ui/queries/get-ip-pool-allocations.query.ts` (`infiniteQueryOptions`, page size 100).
- [x] T011 `resource-manager.query-keys.ts`: add `ipPool`, `ipPoolUtilization` (with `weightedKinds`), `ipPoolAllocations` (all with `branchName`, `atDate`); drop `utilization` and `allocated` once T019 removes their consumers.
- [x] T012 [P] `$RM/ui/routing/ip-pool-urls.ts` (`getIpPoolResourceUrl`) + test; `getIpamNamespaceUrl({ id, isDefault })` in `src/entities/ipam/ip-namespaces/ui/routing/ipam-urls.ts` + test.
- [x] T013 [P] `tests/fake/ip-pool.ts` generators.

## Phase 3: Components (US1, US2, US3, US4)

- [x] T014 [P] [US1] `$RM/ui/ip-pool/details/ip-pool-defaults-line.tsx` + test (the four spec lines, kind opens the schema viewer, namespace href), `ip-pool-header.tsx` + test (title, description, metadata, id, refresh, actions, skeleton).
- [x] T015 [P] [US4] `$RM/ui/ip-pool/details/ip-pool-actions-menu.tsx` + test (the View schema link points to the prefix pool or address pool schema). The enabled and disabled states of Edit, Groups and Delete, with their tooltips, are tested on the shared menu in `number-pool-actions-menu.test.tsx`; opening the IP pool form from Edit is tested in the e2e test (T024).
- [x] T016 [P] [US2] `$RM/ui/ip-pool/details/ip-pool-usage-bar.tsx` + test (two segments, tooltips "Default branch" and "This branch only", percent label) and `ip-pool-resources-card.tsx` + test (order, "Weight N" only when set, selected option, href, empty card).
- [x] T017 [P] [US3] `$RM/ui/ip-pool/details/ip-pool-allocations-table.tsx` + test (columns by pool kind, identifier "None", link, count, load more) and `ip-pool-allocations-card.tsx` + test (not found, empty).

## Phase 4: Page, route, deletions

- [x] T018 `src/pages/resource-manager/ip-pool-details.tsx` + test (first resource selected, resource from the path, utilization error keeps the header, no resources).
- [x] T019 `resource-pool-details.tsx` routes by kind; delete `resource-pool-details-body.tsx`, `resource-allocation-details.tsx`, `$RM/ui/resource-selector.tsx`, `$RM/ui/ResourcePoolUtilization.tsx`, `get-pool-utilization.*`, `get-resource-allocated.*`, `src/shared/components/form/object-edit-slide-over-trigger.tsx`, `roundNumber` in `src/shared/utils/number.ts`; `router.tsx` keeps `resources/:resourceId` as a path-only child; `.betterer.results` entry removed.
- [x] T020 `breadcrumb-resource-manager.tsx` reads `useGetIpPoolUtilization(poolId)`, which shares the page's request through the query cache, and `getIpPoolResourceUrl`, and keeps the loaded resource prefixes when a refresh fails; + test.
- [x] T021 Gates: `cd frontend && pnpm exec biome ci .`; `cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test`.

## Phase 5: Design-jam review (phases 3-4 of the design-jam skill)

- [ ] T022 Run the review passes (`emil-ui-polish`, `emil-surfaces`, `emil-ui-review`, `emil-prep-for-prod`) on the built page and fix or accept each finding.

## Phase 6: E2E, docs, changelog

- [x] T023 [P] Patch `tests/e2e/resource-manager/test_resource_pool.py` (heading, defaults line, Actions > Edit, description in the header) and `tests/e2e/test_breadcrumb.py` (select the option "203.111.0.0/16").
- [x] T024 [P] New `tests/e2e/resource-manager/test_ip_pool_details.py` (`shard_sites_a`, `data_sites`): prefix pool and address pool lines on the default branch, identifiers, "None", link with a resource prefix, not found, empty resource prefix, an allocation made on another branch is listed on that branch (count + 1) and is absent on the default branch (the second usage-bar segment is tested in `ip-pool-usage-bar.test.tsx`), Edit from Actions, read-only menu; add the file to `dev/specs/e2e-pytest-sharding.md` if it lists files.
- [x] T025 [P] Docs and changelog: update the tutorial text in `docs/docs/tutorials/getting-started/resource-manager.mdx`; add `changelog/+ifc-3573-ip-pool-details.changed.md`.
- [ ] T031 Regenerate `docs/docs/media/tutorial_resource_manager_loopbacks_pool.png` by running `test_address_pool_on_default_branch` in `tests/e2e/resource-manager/test_ip_pool_details.py` with `UPDATE_DOCS_SCREENSHOTS=1`, then run `uv run invoke docs.lint`.
- [x] T026 `uv run ruff check tests/e2e && uv run ruff format --check tests/e2e`.

## Phase 7: Review rounds

- [x] T027 Show the whole pool's usage above the resource prefixes, link the selected resource prefix to its IPAM page, and start the usage request alongside the pool request.
- [x] T028 Keep loaded allocations and offer a Retry button when the next page fails, in the IP pool and number pool tables (`$RM/ui/pool/pool-load-more-error.tsx`).
- [x] T029 Show the pool type and the schema extension fields in the header (`get-ip-pool-extra-fields.ts`, `ip-pool-extra-fields.tsx`), and the ID column in the allocations table.
- [x] T030 Tutorial: the pool page lists the allocations of the viewed branch, while an allocation made on a branch stays reserved on every branch.
