# Implementation Plan: Number pool create and edit forms with weighted ranges

**Branch**: `ple-number-pool-form-ifc-3361` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3361-number-pool-form/spec.md`

## Summary

Rework the existing number pool form (`frontend/app/src/entities/resource-manager/ui/number-pool-form.tsx`) so that a user can create a pool with several weighted ranges and an allocation scope, and edit the name, description and ranges of an existing pool. The ranges are a list of rows built with react-hook-form `useFieldArray`. The pool is written with the existing generic object mutations; ranges are written with dedicated range api functions orchestrated by one use-case, in the order of FR-008, stopping at the first refusal. The edit form loads the pool and its ranges with a dedicated query. The "What it allocates" block (node kind, attribute, scope) has one layout with an input variant (create) and a read-only variant (edit). Frontend only; no backend or GraphQL schema change.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2 (React Compiler enabled; no manual memoization)

**Primary Dependencies**: react-hook-form (existing), TanStack Query (existing), `@infrahub/ui` (ListBox, Autocomplete, Popover, Tooltip), generated GraphQL types (`frontend/app/src/shared/api/graphql/generated`)

**Storage**: N/A (server state through GraphQL)

**Testing**: Vitest (unit and browser-mode component tests), pytest-playwright (`tests/e2e/`)

**Target Platform**: Infrahub web UI

**Project Type**: Web application, frontend only

**Performance Goals**: A save with N range changes issues N sequential range calls and one cache invalidation at the end

**Constraints**: Each form file under about 300 lines (`dev/guidelines/frontend/page-architecture.md`); entity layering (`dev/knowledge/frontend/entities-structure.md`)

**Scale/Scope**: Pools with a handful of ranges (typically 1–10)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | Pass | No schema change. Scope candidates and attribute limits are read from the node schema at runtime. |
| II. Branch-Safe by Default | Pass | All queries and mutations pass the current branch through the existing GraphQL client. Pools are branch-agnostic on the server; the form does not assume the default branch. |
| III. Type Safety & Explicit Contracts | Pass | Generated GraphQL types; typed `graphql()` documents; no `any`. Contract in [contracts/graphql-operations.md](contracts/graphql-operations.md). |
| IV. Test Discipline | Pass | Unit tests for every rule, component tests for the form parts, e2e for create/edit and the schema pool (FR-014). |
| V. Query Performance | Pass | One query loads the pool with its ranges; range writes are sequential by necessity (overlap check against stored state). |
| VI. Security & Input Boundaries | Pass | Server remains authoritative; client validation only prevents requests the server refuses. |
| VII. Simplicity & Maintainability | Pass, with one justified addition | Dedicated range api functions instead of the generic object hooks: see Complexity Tracking. No helper is extracted for a hypothetical caller (no shared `formatRange` for the future details page). |

Post-design re-check: Pass, no new violation.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3361-number-pool-form/
├── spec.md
├── plan.md              # This file
├── research.md          # Decisions and rejected alternatives
├── data-model.md        # Form and domain types, validation and diff rules
├── quickstart.md        # Validation guide
├── contracts/
│   └── graphql-operations.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks output
```

### Source Code (repository root)

```text
frontend/app/src/entities/resource-manager/
├── domain/
│   ├── model/
│   │   ├── number-pool.ts              # NumberPoolForEditing (modified)
│   │   ├── number-pool-range.ts        # RangeRow, StoredRange, RangeChanges (new)
│   │   └── scope-candidate.ts          # ScopeCandidate (new)
│   ├── rules/
│   │   ├── validate-range-rows.ts      # validateRangeRows, getRangeClipHint (+ .test.ts) (new)
│   │   ├── plan-range-changes.ts       # sortStoredRanges, diffRanges, linkRowsToStoredRanges (+ .test.ts) (new)
│   │   └── get-scope-candidates.ts     # (+ .test.ts) (new)
│   └── use-cases/
│       ├── get-number-pool-for-editing.ts            (new)
│       └── apply-number-pool-range-changes.ts        (+ .test.ts) (new)
├── api/
│   ├── get-number-pool-for-editing-from-api.ts       (new)
│   ├── create-number-pool-range-from-api.ts          (new)
│   ├── update-number-pool-range-from-api.ts          (new)
│   ├── delete-number-pool-range-from-api.ts          (new)
│   └── number-pool.mappers.ts                        (+ .test.ts) (new)
└── ui/
    ├── number-pool-form.tsx                          # rewritten (+ .test.tsx)
    ├── number-pool-form/
    │   ├── allocates-block.tsx                       # (+ .test.tsx) (new)
    │   ├── ranges-field.tsx                          # (+ .test.tsx) (new)
    │   └── scope-field.tsx                           # (+ .test.tsx) (new)
    └── queries/
        ├── get-number-pool-for-editing.query.ts      (new)
        ├── apply-number-pool-range-changes.mutation.ts (new)
        └── resource-manager.query-keys.ts            # new keys (modified)

tests/e2e/
├── resource-manager/test_number_pool.py              # updated + 2 new tests
├── object-template/test_template_with_number_pool.py # updated
└── tutorial/guides/test_resource_manager_guide.py    # updated

changelog/                                            # one fragment
docs/                                                 # refreshed guide screenshot resource_manager_pool_vlan
```

**Structure Decision**: Everything lives in the existing `resource-manager` entity, following the api/domain/ui layering. `shared/components/form/object-form.tsx` already routes `CoreNumberPool` to `NumberPoolForm` with `currentObject`, so it is not modified.

## Design summary

- **Pool write**: create and update through the existing generic object mutation hooks (unchanged global error toast). `ranges` is removed from the form data before the generic mutation builder runs; the current early return when no pool field changed is removed so a ranges-only save proceeds.
- **Range write**: `applyNumberPoolRangeChanges` runs deletes, then shrinks, then grows, then creates (FR-008, rule in [data-model.md](data-model.md)), and stops at the first refusal. Range api functions suppress the global toast so the message appears once, inline (FR-009).
- **Refused save** (create and edit): stop, refetch the pool, keep every row as typed, link rows already created to their stored range by bounds (`linkRowsToStoredRanges`), show one alert above the ranges. The next save diffs the refetched ranges against the rows.
- **FR-015**: the form holds `createdPoolId` in component state; `poolId = currentObject?.id ?? createdPoolId` selects the edit path and the query.
- **Rows**: plain strings `{ rangeId?, start, end, weight }`, not `{ source, value }`, because ranges are peer nodes, not attributes of the pool. `useFieldArray` keeps its own `id` as the row key.
- **Scope picker**: candidates from `getScopeCandidates(schema, nodeAttribute)`, where `schema` is the node or generic schema of the selected kind (`ModelSchema`); composed from `@infrahub/ui` parts as in the prototype. Every scope rule lives in `get-scope-candidates.ts` only, so the server rule from IFC-3348 can later replace that one file.
- **Errors during a range save**: any rejection (server refusal or network failure) stops the sequence; the use-case returns the number of changes applied and the message (a generic message for non-GraphQL errors).
- **Cache invalidation**: once, after the last range call: the editing query key, `objectQueryKeys.all` (object list and details) and the pool utilization query key.
- **Documentation**: update the web-interface steps and the screenshot `resource_manager_pool_vlan.png` in `docs/docs/resource-manager/allocate-number.mdx`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Dedicated range api functions and a use-case instead of the generic object mutation hooks | The generic api calls show every refusal as a global toast (no `processErrorMessage`), so the inline message would show twice; the generic hooks invalidate the object caches after every call, refetching the object table once per range during a save; a loop of calls is orchestration, which belongs in `domain/use-cases` | Calling the generic hooks in a loop from the form: double error display, N refetches per save, orchestration in `ui/` |
