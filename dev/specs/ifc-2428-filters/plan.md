# Implementation Plan: Unified Filter Menu with Metadata Filters

**Branch**: `ple-filters-IFC-2428` | **Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/ple-filters-IFC-2428/spec.md`

## Summary

Replace the current per-column-header filter popovers with a single unified filter menu button next to the search bar. The menu lists all filterable fields (suggested filters, metadata, attributes, relationships) with hover-to-reveal filter forms. Add metadata filters (created_at, created_by, updated_at, updated_by) available on all list views. Active filters display as clickable/removable tags below the toolbar.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19.2
**Primary Dependencies**: React Aria Components (menus/popovers), Tailwind CSS 4.2, nuqs (query string state), json-to-graphql-query, @tanstack/react-table
**Storage**: URL query string parameters (via nuqs `parseAsJson`)
**Testing**: Vitest (unit/component), Playwright (E2E)
**Target Platform**: Web (modern browsers)
**Project Type**: Web frontend (part of monorepo)
**Performance Goals**: Filter menu opens instantly (<100ms), filter application reflects in table within existing query latency
**Constraints**: Must reuse existing `AttributeFilterForm` and `RelationshipFilterForm` components; must not break existing filter persistence in URL
**Scale/Scope**: Schemas with up to 50+ attributes and relationships; menu must remain usable at this scale

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | PASS | Filterable fields derived from schema; metadata fields added as virtual fields, not manual schema edits |
| II. Branch-Safe by Default | PASS | Filters are query-string based, branch-agnostic at UI layer; backend handles branch context |
| III. Type Safety & Explicit Contracts | PASS | No `any` types; metadata filter fields will have typed definitions; existing Filter type extended |
| IV. Test Discipline | PASS | Unit tests for filter menu logic, E2E tests for user flows |
| V. Query Performance & Efficiency | PASS | No new queries; existing query patterns used; `addFiltersToRequest` extended for `before`/`after` |
| VI. Security & Input Boundaries | PASS | Filter values already sanitized via schema validation; no new user input vectors |
| VII. Simplicity & Maintainability | PASS | Reuses existing filter form components; single new component (filter menu); follows Feature-Sliced architecture |

## Project Structure

### Documentation (this feature)

```text
specs/ple-filters-IFC-2428/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/app/src/
├── entities/nodes/object/ui/
│   ├── filters/
│   │   ├── filter-menu.tsx                    # NEW: Main filter menu component (popover with grouped filter list)
│   │   ├── filter-menu-item.tsx               # NEW: Individual menu item with hover-to-reveal form, active filter indicator
│   │   ├── filter-menu-section.tsx            # NEW: Grouped section (suggested, metadata, attributes, relationships)
│   │   ├── metadata-filter-definitions.ts     # NEW: Metadata filter field definitions (created_at/by, updated_at/by)
│   │   ├── active-object-filter-tags.tsx       # MODIFY: Add click-to-edit behavior, integrate metadata filter display, pass active filters to menu
│   │   ├── attribute-filter-form.tsx           # EXISTING: Reused inside menu
│   │   ├── relationship-filter-form.tsx        # EXISTING: Reused inside menu
│   │   ├── filter-search-input.tsx             # EXISTING: Unchanged
│   │   ├── filter-tag.tsx                      # MODIFY: Add click handler for edit, add remove icon, display filter condition label
│   │   └── internal-groups-filter-tag.tsx      # EXISTING: Integrated into menu as suggested filter
│   ├── object-table/
│   │   ├── cells/
│   │   │   └── table-column-header.tsx         # MODIFY: Remove popover/filter trigger, keep display-only with filter indicator
│   │   └── utils/
│   │       └── get-object-table-columns.tsx    # MODIFY: Update header props (no longer needs PopoverTriggerProps)
│   └── objects-manager-toolbar.tsx             # MODIFY: Add FilterMenu button between search and active filters
├── shared/
│   ├── api/graphql/
│   │   └── utils.ts                            # MODIFY: Add before/after cases to addFiltersToRequest
│   └── components/filters/
│       ├── active-filter-tags.tsx               # MODIFY: Support click-to-edit on filter tags
│       └── utils/
│           └── remove-filters-not-in-schema.ts  # MODIFY: Allow metadata filter names to pass through
```

**Structure Decision**: All new components go under `entities/nodes/object/ui/filters/` following the existing Feature-Sliced architecture. Shared utilities updated in `shared/`. No new directories created outside existing structure.

## Implementation Guidelines

Per `dev/knowledge/frontend/` and `dev/guidelines/frontend/`:

- **Layout**: Use `Col`/`Row` from `@/shared/components/container` — no raw flex divs
- **React 19**: No `memo()`, `useMemo()`, `useCallback()` — compiler handles memoization. `ref` is a regular prop (no `forwardRef`)
- **TypeScript**: Named exports, no `any` (use `unknown` + type guards), no `!` non-null assertions
- **Styling**: Tailwind classes via `classNames()` utility. CVA for 2+ visual variants. No inline styles or CSS modules. Use theme colors (`bg-custom-blue-700`), not hex values
- **File naming**: `kebab-case.tsx` for components, `useCamelCase.ts` for hooks, colocated tests (`filter-menu.test.tsx`)
- **Component pattern**: Early returns for state handling: `isPending` → `error` → content
- **Architecture**: New filter components go in `entities/nodes/object/ui/filters/` (entity-specific, not shared) following Feature-Sliced architecture
- **State**: Filter state managed by `useFilters()` hook (nuqs/URL query string). No Jotai atoms needed — existing pattern is sufficient
- **Imports**: Always use `@/` alias

## Complexity Tracking

No constitution violations requiring justification.
