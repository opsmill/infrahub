# Quickstart: Unified Filter Menu with Metadata Filters

## Prerequisites

```bash
cd frontend/app && pnpm install
```

## Dev Server

```bash
cd frontend/app && pnpm dev
```

Navigate to any object list view (e.g., `/objects/InfraDevice`) to see the filter toolbar.

## Key Files to Understand

| File | Purpose |
|------|---------|
| `entities/nodes/object/ui/objects-manager-toolbar.tsx` | Toolbar composition: search + filters + create |
| `entities/nodes/object/ui/filters/attribute-filter-form.tsx` | Attribute filter form (reused in menu) |
| `entities/nodes/object/ui/filters/relationship-filter-form.tsx` | Relationship filter form (reused in menu) |
| `entities/nodes/object/ui/filters/active-object-filter-tags.tsx` | Active filter tag display |
| `entities/nodes/object/ui/object-table/cells/table-column-header.tsx` | Column header (currently has filter popover) |
| `shared/hooks/useFilters.ts` | Filter state management hook |
| `shared/api/graphql/utils.ts` | `addFiltersToRequest` — filter → GraphQL args |
| `shared/components/filters/active-filter-tags.tsx` | Shared active filter tag rendering |
| `entities/nodes/object/utils/get-attributes-visible-in-list-view.ts` | Determines filterable attributes |
| `entities/nodes/object/utils/get-relationships-visible-in-list-view.ts` | Determines filterable relationships |
| `shared/api/graphql/fragments.ts` | `nodeMetadataFragment` — metadata field definitions |

## Running Tests

```bash
cd frontend/app && pnpm test                    # Unit tests
cd frontend/app && pnpm test:e2e                # E2E tests
cd frontend/app && pnpm biome:fix               # Lint/format
```

## Implementation Order

1. Fix `addFiltersToRequest` to handle `before`/`after` date filters (bug fix, unlocks datetime filtering)
2. Create `metadata-filter-definitions.ts` (pseudo-schema objects for metadata fields)
3. Update `remove-filters-not-in-schema.ts` to allow metadata filter names
4. Build `FilterMenu` component (popover with grouped list + hover submenu)
5. Simplify `TableColumnHeader` (remove popover, keep display-only)
6. Update `ObjectsManagerToolbar` to use FilterMenu
7. Add click-to-edit on active filter tags
8. Add suggested filters to menu
9. Tests (unit + E2E)
