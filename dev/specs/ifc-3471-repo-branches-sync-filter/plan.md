# Implementation Plan: Filter a repository's branches by sync status

**Branch**: `ple-repo-branches-sync-filter-ifc-3471` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-3471-repo-branches-sync-filter/spec.md`

## Summary

The Branches section of a repository's page gains a Sync Status filter, offered from the filter picker and from the Sync Status column header. The server already narrows `InfrahubRepositoryBranchStatus` by `sync_status__value`, counts the filtered rows and pages them after filtering, so the change is frontend only: declare the query variable, map the stored filter to it behind a five-value guard, build the filter definitions from the repository schema's `sync_status` Dropdown attribute (which carries the labels), enable the column header filter, and show the label in the Sync Status filter tag through an optional formatter on the shared `ActiveFilterTags` that no other caller passes.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2

**Primary Dependencies**: gql.tada (typed GraphQL documents), TanStack Table, the shared filter components in `frontend/app/src/entities/nodes/filters/` and `frontend/app/src/entities/nodes/object/ui/filters/`

**Storage**: N/A. The filter is stored in the page URL under the card's `branches_filter` key, as the other filters are.

**Testing**: Vitest in browser mode (component and unit tests next to the source), pytest-playwright end-to-end tests under `tests/e2e/`

**Target Platform**: Infrahub web interface

**Project Type**: Web application, frontend change only

**Performance Goals**: No new request. Applying the filter sends the same single paged request the card already sends, with one more argument.

**Constraints**: No backend or GraphQL schema change. Filter tags in other object tables and the Status tag of this section keep their current display. No `useMemo` or `useCallback` (React Compiler).

**Scale/Scope**: One card, about 8 source files and 6 test files, one generated file, one end-to-end test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Schema-Driven Integrity | Pass | Values and labels come from the `sync_status` Dropdown attribute of the repository schema. `graphql-cache.d.ts` is regenerated with `pnpm codegen:graphql`, not edited. |
| II. Branch-Safe by Default | Pass | The query is already branch-aware; the filter matches the value each branch resolves, inherited values included. |
| III. Type Safety & Explicit Contracts | Pass | The variable type comes from the gql.tada document. `isFilterableSyncStatus` is a type guard, no `as` casts. |
| IV. Test Discipline | Pass after change | Unit and component tests for each layer. The spec's assumption "no new end-to-end test" conflicted with "E2E tests MUST be included for all user-facing features"; the plan adds one end-to-end test and the spec assumption is updated. |
| V. Query Performance | Pass | No new query; filtering happens on the server before paging. |
| VI. Security & Input Boundaries | Pass | A URL value outside the five values is dropped before the request. Read-only feature, no permission change. |
| VII. Simplicity | Pass | One optional prop on a shared component instead of a copied tag component; no new shared helper (the choice lookup stays inline, as in two other places). |

Re-check after Phase 1 design: no change.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3471-repo-branches-sync-filter/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── branches-section-filter.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/app/src/entities/repository/
├── domain/model/repository.ts                      # five-value list and guard
├── api/get-repository-branch-status-from-api.ts    # $sync_status__value
└── ui/repository-branches-card/
    ├── branch-row-fields.ts                        # definitions from schema, tag formatter
    ├── to-repository-branch-arguments.ts           # sync_status__value argument
    ├── repository-branches-toolbar.tsx             # schema prop, formatter
    ├── repository-branches-card.tsx                # passes schema
    └── columns.tsx                                 # header filter enabled
frontend/app/src/entities/nodes/filters/ui/active-filter-tags.tsx   # optional formatFilterValue
frontend/app/src/shared/api/graphql/generated/graphql-cache.d.ts    # regenerated
frontend/app/tests/fake/repository.ts                               # five choices fixture
tests/e2e/repository/test_repository_branches_sync_filter.py        # new
changelog/+ifc-3471-repo-branches-sync-filter.added.md              # new
```

**Structure Decision**: Feature-Sliced layout already used by the card: domain rule in `domain/model`, request in `api`, UI in `ui/repository-branches-card`. The only change outside the `repository` entity is the optional prop on the shared tag component.

## Design decisions

See [research.md](research.md) for rationale and rejected alternatives.

1. **Tag label**: optional `formatFilterValue({ filter, filterDefinition })` prop on `ActiveFilterTags`, threaded to `getFilterTagDisplay` and used only for attribute `value`/`values` tags, falling back to `formatAttributeFilterValue`. The Branches toolbar passes `formatBranchRowFilterValue`, which returns the choice label for `sync_status` only.
2. **Toolbar input**: `RepositoryBranchesToolbar({ schema })` builds `getBranchRowFilterDefinitions(schema)` itself, mirroring `getRepositoryBranchesColumns(schema)`. `getSyncStatusAttribute(schema)` in `branch-row-fields.ts` replaces the literal lookup in `columns.tsx`.
3. **Value guard**: static `FILTERABLE_SYNC_STATUSES` and `isFilterableSyncStatus` in `domain/model/repository.ts`, mirroring `isFilterableBranchStatus`.
4. **`hasRepositoryBranchFilters`**: one explicit check per argument.

## Implementation order

Test first, red then green. Wave 1 units share no file and can run in parallel; waves 2 and 3 are sequential because wave 3 edits one test file throughout.

- **Wave 1**: domain values and guard; query variable and codegen; optional formatter on shared tags (with a guard test that a Dropdown tag keeps its raw value without a formatter).
- **Wave 2**: request arguments.
- **Wave 3**: five-choice fixture; Sync Status in the picker; column header; tag labels.
- **Last**: end-to-end test, changelog fragment, frontend CI gate.

## Complexity Tracking

No violations to justify.
