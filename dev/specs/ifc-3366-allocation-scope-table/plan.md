# Implementation Plan: Allocation scope table for scoped number pools

**Branch**: `bab-allocation-scope-table-ifc-3366` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/ifc-3366-allocation-scope-table/spec.md`

## Summary

The details page of a scoped number pool shows an error today, because it requests pool-wide usage and the backend refuses that request for a scoped pool. This plan replaces the error with two views:

- **A table of the pool's allocation scopes**: searchable and sortable, scrolling horizontally with the usage column pinned on the right. It draws every row; virtualization comes later.
- **A page for one allocation scope**: it reuses the existing ranges card and allocations card, filtered to that allocation scope.

The page identifies an allocation scope with one `allocation_scope` query string parameter. Its value is a JSON array of the field values. All the data comes from backend queries that already exist. The change is frontend only, plus an end-to-end test, a documentation section and a changelog fragment.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler on)

**Primary Dependencies**: TanStack Query, nuqs 2.9.5, gql.tada, `@infrahub/ui`. None is new. The allocation scopes table is a plain `<table>` (research R5).

**Storage**: N/A. The page reads existing backend data.

**Testing**: Vitest in browser mode (rules, mappers, use cases, components), pytest-playwright end-to-end (`tests/e2e/resource-manager/test_number_pool.py`)

**Target Platform**: The Infrahub web interface, in desktop browsers

**Project Type**: Web application, frontend only

**Performance Goals**: With 1,000 allocation scopes already received, the first rows appear and search results update with no visible delay (SC-003). Larger pools wait for virtualization.

**Constraints**:

- No backend or GraphQL schema change.
- The unscoped page keeps working as it does today (FR-013).
- A page file stays at about 250 lines or fewer.

**Scale/Scope**: One page body, one new card with a table, one summary block, one new query, and a `division` argument added to three existing queries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | Pass | The page reads the pool's `allocation_scope` field names from the pool. It does not hard-code any field. |
| II. Branch-Safe by Default | Pass | Every request carries the current branch and time, as today. Usage counts every live branch, as the backend defines it and as the unscoped page already shows it. |
| III. Type Safety & Explicit Contracts | Pass | gql.tada types every operation. The URL value is parsed with a validator. `GenericScalar` is narrowed in the mapper ([contracts/graphql.md](contracts/graphql.md)). |
| IV. Test Discipline | Pass | Vitest covers the rules, mappers, use cases and components. The e2e test covers the main path (R9). |
| V. Query Performance & Efficiency | Pass, with a note | The backend returns every allocation scope without pagination. That is an existing backend design and outside this feature by decision of the feature owner. |
| Performance Standards: virtualization for large lists | Deferred | The table draws every row. The feature owner deferred virtualization to later work; the spec records it under Out of Scope. |
| VI. Security & Input Boundaries | Pass | The URL value is validated before it is sent. The backend validates it again. |
| VII. Simplicity & Maintainability | Pass | The existing cards are reused. No new dependency. No new `domain/rules` file: helpers with one caller stay in that caller's `ui/` file (R7). |
| Quality gates | Planned | Biome, knip, betterer, Vitest, e2e test, changelog fragment, docs section (R10) |

**Re-check after Phase 1**: no change. The design adds no dependency and no backend change. The one deviation, drawing every row without virtualization, is recorded above and in the spec.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-3366-allocation-scope-table/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R11
├── data-model.md        # domain types, rules, view states
├── quickstart.md        # manual and automated validation
├── contracts/
│   ├── url.md           # URL and query string contract
│   └── graphql.md       # operations, variables and query keys
└── checklists/
    └── requirements.md
```

### Source Code

```text
frontend/app/src/
├── shared/config/qsp.ts                                   # + ALLOCATION_SCOPE, ALLOCATION_SCOPE_SEARCH, ALLOCATION_SCOPE_SORT
├── entities/resource-manager/
│   ├── api/
│   │   ├── get-number-pool-divisions-from-api.ts          # new
│   │   ├── number-pool-division.mappers.ts (+ .test.ts)   # new; reuses the usage mapper
│   │   ├── number-pool-utilization.mappers.ts             # export the usage mapper
│   │   ├── get-number-pool-utilization-from-api.ts        # + division
│   │   ├── get-number-pool-allocations-from-api.ts        # + division
│   │   └── get-number-pool-allocation-count-from-api.ts   # + division
│   ├── domain/
│   │   ├── model/number-pool.ts                           # + division types (data-model.md); no new rules file (R7)
│   │   └── use-cases/
│   │       ├── get-number-pool-divisions.ts (+ test)      # new
│   │       ├── get-number-pool-utilization.ts             # + division
│   │       ├── get-number-pool-allocations.ts             # + division
│   │       └── get-number-pool-allocation-count.ts        # + division
│   └── ui/
│       ├── queries/
│       │   ├── get-number-pool-divisions.query.ts         # new
│       │   ├── resource-manager.query-keys.ts             # + numberPoolDivisions, + division in three keys
│       │   └── get-number-pool-{utilization,allocations,allocation-count}.query.ts  # + division
│       ├── hooks/
│       │   ├── use-number-pool-division.ts (+ test)       # new; reads allocation_scope, builds the request input
│       │   └── use-number-pool-division-table-state.ts    # new; search + sort, and the sort type
│       ├── routing/number-pool-urls.ts                    # + division URLs; keep allocation_scope on range links
│       └── number-pool/details/
│           ├── number-pool-divisions-card.tsx (+ test)    # new; title, count, search, filter and sort of the list
│           ├── number-pool-divisions-table.tsx (+ test)   # new; plain table, sticky header, usage pinned right, row links
│           ├── number-pool-division-summary.tsx (+ test)  # new; "Device: …" + All allocation scopes; finds the open one
│           ├── number-pool-division-mismatch.tsx          # new; the "does not match" message
│           ├── number-pool-header.tsx (+ test)            # "scoped by …"
│           ├── number-pool-ranges-card.tsx                # unchanged; links keep allocation_scope
│           └── number-pool-allocations-card.tsx / -table.tsx  # + division prop
├── pages/resource-manager/number-pool-details.tsx (+ test)  # branches on scoped / allocation_scope
├── pages/proto/number-pool/                               # deleted (R11)
└── app/router.tsx                                         # prototype route removed

frontend/app/tests/fake/number-pool.ts                     # + allocation scope generators, up to 1,000
tests/e2e/resource-manager/test_number_pool.py             # + scoped pool test (R9)
docs/docs/resource-manager/overview.mdx                    # + scoped pool section (R10)
changelog/+ifc-3366-number-pool-allocation-scopes.added.md  # new
```

**Structure Decision**: all code follows the existing `entities/resource-manager` api → domain → ui layers and the page in `pages/resource-manager`. The new card and table sit next to the existing number pool details components. No new route is added, because `allocation_scope` is a query string parameter (R2).

## Delivery Order

1. Domain types. They have no dependencies.
2. The API, mapper, use case and query for the allocation scope list. Add `division` to the three existing operations, use cases, queries and keys.
3. The URL parameters, the hooks and the URL helpers, with hook tests for the request input and the mismatch.
4. The table and the card, with component tests for search, sort, horizontal scrolling with the pinned usage column, and 1,000 rows.
5. The summary and mismatch components. Pass `division` through the allocations card and table, and update the header sentence.
6. Branch the page body, with page tests for every state in [data-model.md](data-model.md).
7. The e2e test, the documentation section and the changelog fragment.
8. Delete the prototype. Run `pnpm knip`, `betterer ci`, `biome ci` and `/pre-ci`.

## Complexity Tracking

No violation to justify.
