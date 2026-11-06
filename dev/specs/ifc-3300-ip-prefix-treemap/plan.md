# Implementation Plan: IP Prefix Tree Map

**Branch**: `pmc/ip-prefix-treemap-viz-5dfe40f9` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3300-ip-prefix-treemap/spec.md`

## Summary

Add a "Tree Map" tab to the IPAM prefix detail page that renders the prefix's direct children and
free blocks as an address-ordered treemap along a Hilbert curve, tiles sized by address space and
placed so that neighbouring blocks share an edge, allocated tiles carrying an inner utilisation
fill, with click-to-drill-down on children and click-to-create on free blocks. The
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

**Scale/Scope**: About 14 new frontend files (api, model, three rules, use-case, key factory, query hook, four UI components, page shim) plus edits to the router, the IPAM tab bar and the available-row identifier; one new E2E module; one docs guide with two cross-references; one changelog fragment. Roughly 700 lines of source and 400 of tests.

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
| VII. Simplicity & Maintainability | PASS | No new dependency; the Hilbert layout is one short pure function of integer arithmetic justified in research R3. The create sheet is extracted only because a second caller now exists. Follows the entity api/domain/ui layering and the IPAM family's existing context pattern rather than introducing a parallel one. |

**Post-Phase 1 re-check**: All gates still pass. No new entities, no new dependencies, no new
architectural patterns. The one deviation from a guideline, reading the parent through
`FormContext` instead of outlet context, follows the guideline's own "do not mix patterns within a
family" rule and is recorded in research R6.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3300-ip-prefix-treemap/
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
│   ├── router.tsx                                   # add `tree-map` child route before `:relationshipName`
│   └── styles/index.css                             # `--accent-fill` and `--pool*` tokens, hatch utilities (app-local, not @infrahub/ui)
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
    │   │   ├── prefix-size.ts                      # NEW + .test.ts (network address parsing, block arithmetic, CIDR formatting)
    │   │   ├── build-tree-map-tiles.ts              # NEW + .test.ts (address order, per-cell aggregation, not-loaded range, invariants)
    │   │   └── layout-tree-map.ts                   # NEW + .test.ts (Hilbert-curve placement to percentages, adjacency)
    │   └── use-cases/
    │       └── get-ip-prefix-tree-map.ts            # NEW maps the response to TreeMapData
    └── ui/
        ├── queries/
        │   ├── ip-prefix.query-keys.ts              # NEW ipPrefixesQueryKeys.treeMap under objectQueryKeys.all
        │   └── get-ip-prefix-tree-map.query.ts      # NEW queryOptions + useGetIpPrefixTreeMap
        ├── ip-prefix-tree-map.tsx                   # NEW container: states, notice, legend, create sheet wiring
        ├── ip-prefix-tree-map-tile.tsx              # NEW + .test.tsx: allocated, free, aggregate, not-loaded tiles
        ├── ip-prefix-tree-map-empty-state.tsx       # NEW + .test.tsx: address-type parent without child prefixes
        ├── ip-prefix-create-sheet.tsx               # NEW, extracted from ip-prefix-available-identifier.tsx
        └── ip-prefix-available-identifier.tsx       # use IpPrefixCreateSheet

tests/e2e/ipam/
└── test_ip_prefix_tree_map.py                       # NEW, shard_foundation, data_ipam_pools

docs/docs/ipam/
├── visualize-prefix-utilization.mdx                 # NEW how-to guide for the Tree Map tab
└── overview.mdx                                     # pointer to the guide (also from resource-manager/overview.mdx)

changelog/
└── 10858.added.md                                   # Tree Map tab, via `towncrier create`
```

**Structure Decision**: Frontend-only slice inside the existing `entities/ipam/ip-prefixes` entity,
following the api/domain/ui layering from `dev/knowledge/frontend/entities-structure.md`. The page
shim and route follow `dev/guidelines/frontend/route-architecture.md`, except that the parent is
read through the IPAM family's existing `FormContext` pattern (research R6). No backend directory
is touched.

## Design Notes for the Task Phase

These are the decisions the tasks must respect; the reasoning is in research.md.

1. **Query** (R1, R2): `GET_IP_PREFIX_TREE_MAP` with `limit: TREE_MAP_CHILD_LIMIT`, fetching the
   parent through an aliased `BuiltinIPPrefix(ids: [$parentId])` in the same document. Split
   child nodes by `__typename === IP_PREFIX_AVAILABLE_KIND`. Use `prefix.value`, `prefix.prefixlen`
   and `prefix.version` on every kind; never `num_addresses`.
2. **Arithmetic** (R4): BigInt network addresses and address counts; percentages only in the
   layout output.
3. **Aggregation and the not-loaded range** (R2, R5): cell depth `TREE_MAP_CELL_DEPTH` (12 bits
   below the parent), one aggregate per full cell placed at the cell; split a partially loaded
   boundary cell into aligned CIDR blocks and aggregate each loaded block separately. Not-loaded tiles only when
   `count > children.length`, covering the range after the last fetched block; invariants in
   data-model.md are test assertions.
4. **Layout** (R3): Hilbert-curve placement by network address, no sorting by size, output in
   percentages for a 2:1 container; no resize observer.
5. **Tiles** (R10, ui-contract.md): allocated tiles are `Link`s, free tiles are `Button`s, aggregate
   links go to the parent's Children tab. Accessible names never depend on the visible label.
6. **Create** (R7): extract `IpPrefixCreateSheet`; both callers invalidate `objectQueryKeys.all`.
7. **Context** (R6, R8): parent from `useCurrentFormContext()`, permission from
   `RequireObjectPermissions`, branch and date from `useCurrentBranch` and `datetimeAtom`.
8. **Drill-down URL**: build the child's tree-map path with the same helper the IPAM tree uses to
   link to a prefix, appending the `tree-map` segment, so namespace and kind query params survive.
9. **Docs and changelog** (R12): the `docs/docs/ipam/visualize-prefix-utilization.mdx` guide
   with pointers from the IPAM and Resource Manager overviews; `towncrier create` fragment of type
   `added`.
10. **Measurement** (R9): fill the SC-001 table in quickstart.md before opening the PR.

## Spec amendments made during planning

- FR-011 and User Story 5 scenario 1 now say the cap keeps the **first 1,000 children in address
  order** and shows the uncovered space as one remainder tile, because the backend computes free
  blocks only within the fetched window (research R2). The spec's Assumptions section records the
  reason.
- After review of the first implementation (2026-10-04): FR-002a added for address adjacency; FR-011
  now marks the space after the last loaded block as **not loaded** rather than drawing one
  remainder tile; FR-012 aggregates **per cell** rather than into a single tile; a new assumption
  records that prefix length and family come from the API, not from string parsing; the sidebar fix
  moved out of scope to its own change (#10866). Research R3, R4, R5 and R10 and the data model
  carry the matching decisions.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
