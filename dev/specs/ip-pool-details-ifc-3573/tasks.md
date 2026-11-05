---
description: "Task list for the IP prefix pool and IP address pool details page redesign"
---

# Tasks: Redesign the IP prefix pool and IP address pool details page

**Input**: [plan.md](plan.md), [spec.md](spec.md). Prototype: `git show 8827d389b5:frontend/app/src/proto/ip-pool-defaults/{shared,row-parts,s-dots}.tsx`.

**Tests**: included; each component has a test next to it, each rule and mapper a unit test, and one e2e file covers both pool kinds.

## Format: `[ID] [P?] [Story] Description`

Paths are under `frontend/app/` unless they start with `tests/`, `docs/` or `changelog/`. `$RM` = `src/entities/resource-manager`.

## Phase 1: Shared pieces (FR-021 gate)

- [ ] T001 Create `$RM/ui/pool/pool-id.tsx`, `schema-reference.tsx`, `utilization-tooltip-message.tsx`, `kind-label.tsx` by moving the JSX verbatim out of `number-pool-header.tsx`, `number-pool-usage-bar.tsx`, `number-pool-allocations-table.tsx`; import them back there.
- [ ] T002 Create `$RM/ui/pool/pool-actions-menu.tsx` (`PoolActionsMenu({ pool: { id, hfid, name }, poolKind, schema, permission: { update, delete }, onDeleted })`) from `number-pool-actions-menu.tsx`; `NumberPoolActionsMenu` keeps the schema-lock decisions and renders it.
- [ ] T003 Run `pnpm test src/entities/resource-manager/ui/number-pool src/pages/resource-manager` and `pnpm knip`; both green before phase 2.

## Phase 2: Data layer

- [ ] T004 [P] `$RM/domain/model/ip-pool.ts`: `IpPoolData` (discriminated on `__typename`), `IpPoolResourceUsage`, `IpPoolResource`, `IpPoolUtilization`, `IpPoolAllocation`, `IpPoolAllocationsPage`, `IpPoolDefaultEntry`, member type constants.
- [ ] T005 [P] `$RM/domain/rules/get-ip-pool-default-entries.ts` + test (US1 scenarios 1-4).
- [ ] T006 [P] `$RM/domain/rules/sort-ip-pool-resources-by-fill-order.ts` + test (weights 100/100/50, ties by prefix with numeric collation, null as 0 last, non-mutating).
- [ ] T007 [P] `$RM/domain/rules/get-weighted-prefix-kinds.ts` + test (kind inheriting `BuiltinIPPrefix` with `allocation_weight` found; kind without skipped; empty list).
- [ ] T008 `$RM/api/get-ip-pool-from-api.ts` (both kinds, `ContextParams`), `ip-pool.mappers.ts` + test; `domain/use-cases/get-ip-pool.ts` + test ("IP pool not found"); `ui/queries/get-ip-pool.query.ts`.
- [ ] T009 Rename `get-pool-utilization-from-api.ts` to `get-ip-pool-utilization-from-api.ts` with `ContextParams`; add `get-ip-pool-resource-weights-from-api.ts` (`jsonToGraphQLQuery`, `__on` per kind); `ip-pool-utilization.mappers.ts` + test; `domain/use-cases/get-ip-pool-utilization.ts` + test (skips weights when no weighted kind; sorted output); `ui/queries/get-ip-pool-utilization.query.ts` (`useGetIpPoolUtilization(poolId, config?)`, derives `weightedKinds` from `nodeSchemasAtom`).
- [ ] T010 Rename `get-resource-allocated-from-api.ts` to `get-ip-pool-allocations-from-api.ts` with `ContextParams`; `ip-pool-allocation.mappers.ts` + test; `domain/use-cases/get-ip-pool-allocations.ts` (returns `{ count, allocations }`); `ui/queries/get-ip-pool-allocations.query.ts` (`infiniteQueryOptions`, page size 100).
- [ ] T011 `resource-manager.query-keys.ts`: add `ipPool`, `ipPoolUtilization` (with `weightedKinds`), `ipPoolAllocations` (all with `branchName`, `atDate`); drop `utilization` and `allocated` once T019 removes their consumers.
- [ ] T012 [P] `$RM/ui/routing/ip-pool-urls.ts` (`getIpPoolResourceUrl`) + test; `getIpamNamespaceUrl({ id, isDefault })` in `src/entities/ipam/ip-namespaces/ui/routing/ipam-urls.ts` + test.
- [ ] T013 [P] `tests/fake/ip-pool.ts` generators.

## Phase 3: Components (US1, US2, US3, US4)

- [ ] T014 [P] [US1] `$RM/ui/ip-pool/details/ip-pool-defaults-line.tsx` + test (the four spec lines, kind opens the schema viewer, namespace href), `ip-pool-header.tsx` + test (title, description, metadata, id, refresh, actions, skeleton).
- [ ] T015 [P] [US4] `$RM/ui/ip-pool/details/ip-pool-actions-menu.tsx` + test (renders `PoolActionsMenu` with the pool kind; Edit opens the IP pool form; disabled items with tooltip).
- [ ] T016 [P] [US2] `$RM/ui/ip-pool/details/ip-pool-usage-bar.tsx` + test (two segments, tooltips "Default branch" and "This branch only", percent label) and `ip-pool-resources-card.tsx` + test (order, "Weight N" only when set, selected option, href, empty card).
- [ ] T017 [P] [US3] `$RM/ui/ip-pool/details/ip-pool-allocations-table.tsx` + test (columns by pool kind, identifier "None", link, count, load more) and `ip-pool-allocations-card.tsx` + test (not found, empty).

## Phase 4: Page, route, deletions

- [ ] T018 `src/pages/resource-manager/ip-pool-details.tsx` + test (first resource selected, resource from the path, utilization error keeps the header, no resources).
- [ ] T019 `resource-pool-details.tsx` routes by kind; delete `resource-pool-details-body.tsx`, `resource-allocation-details.tsx`, `$RM/ui/resource-selector.tsx`, `$RM/ui/ResourcePoolUtilization.tsx`, `get-pool-utilization.*`, `get-resource-allocated.*`; `router.tsx` keeps `resources/:resourceId` as a path-only child; `.betterer.results` entry removed.
- [ ] T020 `breadcrumb-resource-manager.tsx` reads `useGetIpPoolUtilization(poolId, { enabled: false })` and `getIpPoolResourceUrl`; + test.
- [ ] T021 Gates: `cd frontend && pnpm exec biome ci .`; `cd frontend/app && pnpm knip && pnpm exec betterer ci && pnpm test`.

## Phase 5: Design-jam review (phases 3-4 of the design-jam skill)

- [ ] T022 `.design/ip-pool-details/03-decisions.md`; run the review passes (`emil-ui-polish`, `emil-surfaces`, `emil-ui-review`, `emil-prep-for-prod`) on the built page and fix or accept each finding in `04-review.md`; `05-handoff.md`, `05-implement.md`, `STATE.md`.

## Phase 6: E2E, docs, changelog

- [ ] T023 [P] Patch `tests/e2e/resource-manager/test_resource_pool.py` (heading, defaults line, Actions > Edit, description in the header) and `tests/e2e/test_breadcrumb.py` (select the option "203.111.0.0/16").
- [ ] T024 [P] New `tests/e2e/resource-manager/test_ip_pool_details.py` (`shard_sites_a`, `data_sites`): prefix pool and address pool lines on the default branch, identifiers, "None", link with a resource prefix, not found, empty resource prefix, allocation on another branch shows the second segment and is absent on the default branch, Edit from Actions, read-only menu; add the file to `dev/specs/e2e-pytest-sharding.md` if it lists files.
- [ ] T025 [P] Docs: `docs/docs/tutorials/getting-started/resource-manager.mdx` (lines 27-45 and 96-110), regenerate `media/tutorial_resource_manager_loopbacks_pool.png` from the e2e with `save_screenshot_for_docs`; `changelog/+ifc-3573-ip-pool-details.changed.md`; `uv run invoke docs.lint`.
- [ ] T026 `uv run ruff check tests/e2e && uv run ruff format --check tests/e2e`.
