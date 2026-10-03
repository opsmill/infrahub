# Implementation Plan: IP Prefix Tree Map

**Branch**: `pmc/ip-prefix-treemap-viz-5dfe40f9` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-ip-prefix-treemap/spec.md`

## Summary

Add a "Tree Map" tab to the IPAM prefix detail page that renders the prefix's direct children and
free blocks as a squarified treemap, tiles sized by address space, allocated tiles carrying an inner
utilisation fill, with click-to-drill-down on children and click-to-create on free blocks. The
feature is frontend-only: one new typed GraphQL document against the existing `BuiltinIPPrefix`
root field with `include_available: true`, a pure-function layout in the domain layer rendered as
accessible HTML tiles, and reuse of the existing create sheet, permission gate, tooltip and meter.
No backend, schema, dependency or auth change.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler enabled), Python 3.14 only for E2E tests

**Primary Dependencies**: react-router 8 (nested routes, `Link`), @tanstack/react-query 5, gql.tada over the urql-backed client, `@infrahub/ui` (`Button`, `Sheet`, `Tooltip`, `Meter`), Tailwind CSS 4 with the semantic theme tokens. No new dependency; Recharts stays unused here (research R3).

**Storage**: N/A. Pure projection of an existing read query.

**Testing**: Vitest 4 in browser mode for unit and component tests; pytest-playwright under `tests/e2e/` for the user journeys.

**Target Platform**: Web application, browser frontend served by the existing Vite app.

**Project Type**: Web application, frontend slice only.

**Performance Goals**: SC-001, a prefix with 256 direct children renders within 3 s warm; SC-005, 1,000 children render within 5 s with the page responsive.

**Constraints**: No backend change in v1 (research R9). Cap of 1,000 children per map, address-ordered because the server computes free blocks only inside the fetched window (research R2). Exact address arithmetic across IPv4 and IPv6 (research R4). All colours through theme tokens.

**Scale/Scope**: About 14 new frontend files (api, model, three rules, use-case, key factory, query hook, four UI components, page shim) plus edits to the router, the IPAM tab bar and the available-row identifier; one new E2E module; one docs section; one changelog fragment. Roughly 700 lines of source and 400 of tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | No schema change. Reads existing attributes on `BuiltinIPPrefix`; generated files untouched. |
| II. Branch-Safe by Default | PASS | Branch and time-machine date flow into the query context and the query key (research R8), so a branch switch refetches. The resolver already applies branch filters. FR-013 and User Story 1 scenario 6 are tested end to end. No cross-branch side effects. |
| III. Type Safety & Explicit Contracts | PASS | New typed gql.tada document (contracts/graphql-query.md); domain types in data-model.md; no `any`, no `as` casts. The page shim reads params through the existing IPAM pattern; no new `useParams() as` is introduced. |
| IV. Test Discipline | PASS | Unit tests for three pure rules, component tests for tiles and empty state, E2E for every user story (research R11). Written alongside implementation. |
| V. Query Performance & Efficiency | PASS with watch | One request per map. Per-child utilisation is computed on read by the backend, one Cypher query per node, which the Children tab already pays. The 1,000 cap bounds it; SC-001 is measured in quickstart step 5 and a batched lookup is a separate gated follow-up if it fails. |
| VI. Security & Input Boundaries | PASS | Read-only query with bound variables. Create goes through the existing form and permission gate. CIDR strings from the API are parsed defensively; a malformed one is dropped, never interpolated. |
| VII. Simplicity & Maintainability | PASS | No new dependency; squarified layout is one eighty-line pure function justified in research R3. The create sheet is extracted only because a second caller now exists. Follows the entity api/domain/ui layering and the IPAM family's existing context pattern rather than introducing a parallel one. |

**Post-Phase 1 re-check**: All gates still pass. No new entities, no new dependencies, no new
architectural patterns. The one deviation from a guideline, reading the parent through
`FormContext` instead of outlet context, follows the guideline's own "do not mix patterns within a
family" rule and is recorded in research R6.

## Project Structure

### Documentation (this feature)

```text
specs/005-ip-prefix-treemap/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1 to R12
├── data-model.md        # Phase 1: domain types, constants, invariants
├── quickstart.md        # Phase 1: validation runbook and SC-001 measurement
├── contracts/
│   ├── graphql-query.md # the typed document, response shape, sandbox sample
│   └── ui-contract.md   # route, tab, tile roles and selectors, states
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks), not created here
```

### Source Code (repository root)

```text
frontend/app/src/
├── app/
│   └── router.tsx                                   # add `tree-map` child route before `:relationshipName`
├── pages/ipam/
│   ├── ipam-details-layout.tsx                      # add the "Tree Map" LinkTab for prefix kinds
│   └── ipam-details-tree-map-page.tsx               # NEW shim: FormContext parent + RequireObjectPermissions → IpPrefixTreeMap
└── entities/ipam/ip-prefixes/
    ├── api/
    │   └── get-ip-prefix-tree-map-from-api.ts       # NEW typed document GET_IP_PREFIX_TREE_MAP
    ├── domain/
    │   ├── model/
    │   │   └── ip-prefix-tree-map.ts                # NEW types and constants (data-model.md)
    │   ├── rules/
    │   │   ├── parse-prefix-length.ts               # NEW + .test.ts
    │   │   ├── build-tree-map-tiles.ts              # NEW + .test.ts (aggregation, remainder, invariants)
    │   │   └── layout-tree-map.ts                   # NEW + .test.ts (squarified layout to percentages)
    │   └── use-cases/
    │       └── get-ip-prefix-tree-map.ts            # NEW maps the response to TreeMapData
    └── ui/
        ├── queries/
        │   ├── ip-prefix.query-keys.ts              # NEW ipPrefixesQueryKeys.treeMap under objectQueryKeys.all
        │   └── get-ip-prefix-tree-map.query.ts      # NEW queryOptions + useGetIpPrefixTreeMap
        ├── ip-prefix-tree-map.tsx                   # NEW container: states, notice, legend, create sheet wiring
        ├── ip-prefix-tree-map-tile.tsx              # NEW + .test.tsx: allocated, free, aggregate, remainder tiles
        ├── ip-prefix-tree-map-empty-state.tsx       # NEW + .test.tsx: address-type parent
        ├── ip-prefix-create-sheet.tsx               # NEW, extracted from ip-prefix-available-identifier.tsx
        └── ip-prefix-available-identifier.tsx       # use IpPrefixCreateSheet

tests/e2e/ipam/
└── test_ip_prefix_tree_map.py                       # NEW, shard_foundation, data_ipam_pools

docs/docs/ipam/
└── overview.mdx                                     # "Tree Map" subsection under Utilization

changelog/
└── +ip-prefix-tree-map.added.md                     # via `towncrier create`
```

**Structure Decision**: Frontend-only slice inside the existing `entities/ipam/ip-prefixes` entity,
following the api/domain/ui layering from `dev/knowledge/frontend/entities-structure.md`. The page
shim and route follow `dev/guidelines/frontend/route-architecture.md`, except that the parent is
read through the IPAM family's existing `FormContext` pattern (research R6). No backend directory
is touched.

## Design Notes for the Task Phase

These are the decisions the tasks must respect; the reasoning is in research.md.

1. **Query** (R1, R2): `GET_IP_PREFIX_TREE_MAP` with `limit: TREE_MAP_CHILD_LIMIT`. Split nodes by
   `__typename === IP_PREFIX_AVAILABLE_KIND`. Use `prefix.value` for the CIDR on both kinds.
2. **Arithmetic** (R4): BigInt address counts; fraction weights only after aggregation.
3. **Aggregation and remainder** (R2, R5): threshold `parentCount / 4096n`; remainder tile only
   when `count > children.length`; invariants in data-model.md are test assertions.
4. **Layout** (R3): squarified, tiles sorted by weight descending, output in percentages for a 2:1
   container; no resize observer.
5. **Tiles** (R10, ui-contract.md): allocated tiles are `Link`s, free tiles are `Button`s, aggregate
   links go to the parent's Children tab. Accessible names never depend on the visible label.
6. **Create** (R7): extract `IpPrefixCreateSheet`; both callers invalidate `objectQueryKeys.all`.
7. **Context** (R6, R8): parent from `useCurrentFormContext()`, permission from
   `RequireObjectPermissions`, branch and date from `useCurrentBranch` and `datetimeAtom`.
8. **Drill-down URL**: build the child's tree-map path with the same helper the IPAM tree uses to
   link to a prefix, appending the `tree-map` segment, so namespace and kind query params survive.
9. **Docs and changelog** (R12): `docs/docs/ipam/overview.mdx` subsection; `towncrier create`
   fragment of type `added`.
10. **Measurement** (R9): fill the SC-001 table in quickstart.md before opening the PR.

## Spec amendments made during planning

- FR-011 and User Story 5 scenario 1 now say the cap keeps the **first 1,000 children in address
  order** and shows the uncovered space as one remainder tile, because the backend computes free
  blocks only within the fetched window (research R2). The spec's Assumptions section records the
  reason.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
