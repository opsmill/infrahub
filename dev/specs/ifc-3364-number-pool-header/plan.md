# Implementation Plan: Number pool details header

**Branch**: `number-pool-header-ifc-3364` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3364-number-pool-header/spec.md`

## Summary

Replace the generic card title on the number pool details page (`/resource-manager/:id`) with a header that shows:

- the pool's name and description
- who manages the pool (the schema or users)
- what the pool allocates to
- an Actions menu that blocks Edit, Groups and Delete on pools the schema created

The change is frontend only:

- **New number pool page**: `NumberPoolDetailsPage` loads the pool through a new typed fetch path (api → use-case → query) that returns `NumberPoolData`, and passes it to the header. Later work passes the same value to the new body.
- **New code**: a `ui/number-pool/` folder in the `resource-manager` entity, which later work on the number pool page extends. `SchemaReference` picks the schema modal tab from the field. The allocation scope is not shown (research.md R18).
- **Shared body**: the current page body moves into `ResourcePoolDetailsBody`, which both pages render unchanged.
- **Reload**: the header uses the existing `RefreshButton` with the `resourceManagerQueryKeys.all` prefix, so one reload covers the pool, its utilization and its allocated resources (research.md R2).
- **URL builders**: three menu URL builders move into `object-urls.ts`, and all menus use them.

IP prefix pools and IP address pools keep the current header.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler enabled)

**Primary Dependencies**: `@infrahub/ui` (Menu, Tooltip, Button, Sheet), TanStack Query, react-router, lucide-react. No new dependency.

**Storage**: N/A. A new GraphQL query, `GET_NUMBER_POOL`, reads existing `CoreNumberPool` fields. There is no schema or API change (see [research.md R1](research.md#r1-a-number-pool-page-that-loads-a-typed-number-pool-and-passes-it-down)).

**Testing**:
- **Unit and component tests**: Vitest in browser mode.
- **End-to-end test**: pytest-playwright in `tests/e2e/resource-manager/test_number_pool.py`.

**Target Platform**: the Infrahub web app in modern browsers

**Project Type**: web application, frontend only (`frontend/app`)

**Performance Goals**: the header adds one small query with only the fields it needs. The unchanged body keeps its own request until the new body replaces it (research.md R1, Consequences).

**Constraints**:
- **Entity layering**: follows `dev/knowledge/frontend/entities-structure.md`.
- **Unchanged pages**: no change for other pool kinds (SC-004).
- **Generated files**: none are edited by hand. The gql.tada cache is regenerated with `pnpm codegen:graphql` after the new query is added.

**Scale/Scope**:
- 1 new page component, 3 new components (header, header placeholder, actions menu).
- 1 new fetch path (api, mapper, use-case, query), 1 new domain type, 2 vocabulary constants and the `NumberPoolType` union.
- 1 body component moved out of the current page without changes.
- 3 new URL builders.
- 3 callers updated: the 2 existing menus and the pool page.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | Pass | Scope labels and the documentation link are read from the loaded schema. No generated file is edited. |
| II. Branch-Safe by Default | Pass | The pool exists on all branches, while its kind's schema depends on the branch. The header handles a kind or a field that is missing from the current branch's schema (data-model.md, "Allocation scope labels"). No writes. |
| III. Type Safety | Pass | No `any`. The response is typed from the generated GraphQL schema, and the mapper narrows `allocation_scope` with a type guard, not a cast. |
| IV. Test Discipline | Pass | Unit tests for the mapper and the use-case, component tests for the header, the menu and the page, and an extended end-to-end spec (research.md R11). |
| V. Query Performance | Pass | The new query asks only for the fields the page shows. The body's existing request stays until the body work replaces it. |
| VI. Security & Input Boundaries | Pass | Disabled menu items only make the UI clearer. The backend still refuses range writes on schema-created pools and checks permissions. |
| VII. Simplicity | Pass | URL builders are extracted only because three callers exist (R4). The permission and schema-lock decision stays inline because it has one caller (R5). A dedicated menu is preferred to adding single-caller options to `ObjectDetailsMenu` (R3). |
| Changelog gate | Pass | `changelog/+ifc-3364-number-pool-header.changed.md` (R13). |
| Documentation requirement | Deferred | User docs and screenshots are updated once the rest of the number pool page is built. See Complexity Tracking. |

Post-design re-check: no change. The design adds no violation.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3364-number-pool-header/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── number-pool-header.md
├── checklists/
│   └── requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
frontend/app/src/
├── entities/resource-manager/
│   ├── api/
│   │   ├── get-number-pool-from-api.ts                     # new: GET_NUMBER_POOL
│   │   ├── number-pool.mappers.ts                          # new: → NumberPoolData
│   │   └── number-pool.mappers.test.ts                     # new
│   ├── domain/
│   │   ├── model/number-pool.ts                            # + NumberPoolData
│   │   ├── model/pool.ts                                   # + NUMBER_POOL_TYPE_SCHEMA, NUMBER_POOL_TYPE_USER, NumberPoolType
│   │   └── use-cases/
│   │       ├── get-number-pool.ts                          # new
│   │       └── get-number-pool.test.ts                     # new
│   └── ui/
│       ├── queries/get-number-pool.query.ts                # new: useGetNumberPool
│       ├── queries/resource-manager.query-keys.ts          # + numberPool key
│       └── number-pool/
│           ├── number-pool-header.tsx                      # new: header + NumberPoolHeaderSkeleton
│           ├── number-pool-header.test.tsx                 # new
│           ├── number-pool-actions-menu.tsx                # new
│           └── number-pool-actions-menu.test.tsx           # new
├── entities/nodes/object/ui/
│   ├── object-details/
│   │   └── object-details-menu.tsx                         # use the moved URL builders
│   └── routing/
│       ├── object-urls.ts                                  # + 3 URL builders
│       └── object-urls.test.ts                             # + one test per builder
├── entities/artifacts/ui/artifact-details-menu.tsx         # use the moved URL builders
└── pages/resource-manager/
    ├── resource-pool-details.tsx                           # renders NumberPoolDetailsPage for CoreNumberPool
    ├── number-pool-details.tsx                             # new: useGetNumberPool, renders header + body
    ├── number-pool-details.test.tsx                        # new: loading, error, loaded
    └── resource-pool-details-body.tsx                           # new: current body, moved without changes

frontend/app/src/shared/api/graphql/generated/graphql-cache.d.ts  # regenerated by pnpm codegen:graphql, never edited
tests/e2e/resource-manager/test_number_pool.py              # + header assertions
changelog/+ifc-3364-number-pool-header.changed.md           # new
```

**Structure Decision**:
- **The number pool UI belongs to the `resource-manager` entity**, which already owns the number pool vocabulary (`NUMBER_POOL_KIND`) and the number pool edit form. It sits in `ui/number-pool/`, the folder that later number pool page work also uses.
- **Pages compose entity UI into complete views**: `NumberPoolDetailsPage` and `ResourcePoolDetailsBody` live in `pages/resource-manager/` next to the route modules, because they combine UI from several entities (`resource-manager`, `nodes/object`, `groups`, `permission`) into the number pool view.
- **The page owns the pool data**: `NumberPoolDetailsPage` loads `NumberPoolData` through `useGetNumberPool` and handles loading and errors. The header, and later the body, receive it as a prop.
- **The fetch path follows the entity layers**: the API query and the mapper live in `api/`, the type in `domain/model/`, the use-case in `domain/use-cases/`, and the hook and key in `ui/queries/`.
- **The route stays shared**: `/resource-manager/:resourcePoolId` serves every pool kind and picks the number pool page only after it knows the kind (research.md R10).

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| User documentation not updated in this work (constitution: "New features MUST be documented in `docs/`") | Docs and screenshots are updated once, after the page body of the number pool page changes too | Updating the docs now would describe a page that changes again in the next piece of work |

## Risks

- **The edit form cannot save multi-range pools**: `NumberPoolForm` requires `start_range` and `end_range`, which are null on a pool with several ranges, so Actions → Edit cannot save there. This is existing behaviour, outside this work (research.md R12).
- **The documentation screenshot changes**: `test_number_pool_attribute_kind_resource_manager` saves a screenshot of the schema-created pool, and the new header changes it. Screenshots are refreshed once the rest of the number pool page is built.
- **The number pool page loads the pool three times until the body work**: the existing kind lookup, the new `GET_NUMBER_POOL`, and the unchanged body's own `useGetObject` call. Without the header, the page loads it twice (research.md R1).
- **The page body offers Edit on schema-created pools**: the Edit button on the property list (`ObjectEditSlideOverTrigger` in `pages/resource-manager/resource-pool-details-body.tsx::ResourcePoolDetailsBody`) ignores the schema lock. Separate work replaces this body (spec Assumptions).
- **The property list can show old values after a reload**: it reads the pool through the `"objects"` query, which the header's reload button does not reload (research.md R2).
