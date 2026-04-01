# Tasks: Unified Filter Menu with Metadata Filters

**Input**: Design documents from `/specs/ple-filters-IFC-2428/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

All paths relative to `frontend/app/src/` unless otherwise noted.

---

## Phase 1: Setup

**Purpose**: No project initialization needed — this is a feature within an existing codebase. Skip to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Bug fixes and shared infrastructure that MUST be complete before any user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T001 [P] Fix `addFiltersToRequest` to handle `before` and `after` date filter keys in `shared/api/graphql/utils.ts` — add cases for `"before"` and `"after"` in the switch statement (currently silently dropped). Add unit tests for these cases in `shared/api/graphql/utils.test.ts`.
- [ ] T002 [P] Create metadata filter pseudo-schema definitions in `entities/nodes/object/ui/filters/metadata-filter-definitions.ts` — define 4 objects: `node_metadata__created_at` (AttributeSchema, kind DateTime), `node_metadata__updated_at` (AttributeSchema, kind DateTime), `node_metadata__created_by` (RelationshipSchema, peer CoreAccount), `node_metadata__updated_by` (RelationshipSchema, peer CoreAccount). Names MUST use the `node_metadata__` prefix.
- [ ] T003 [P] Update `removeFiltersNotInSchema` in `shared/components/filters/utils/remove-filters-not-in-schema.ts` to allow filters with the `node_metadata__` prefix to pass through validation. Update tests in `remove-filters-not-in-schema.test.ts`.

**Checkpoint**: Foundation ready — `before`/`after` filters serialize to GraphQL, metadata definitions exist, metadata filters survive schema validation.

---

## Phase 3: User Story 1 — Open filter menu and apply an attribute filter (Priority: P1) 🎯 MVP

**Goal**: Replace per-column filter popovers with a single "Filter" button that opens a grouped menu. Hovering a menu item reveals the existing filter form. Applying a filter closes the menu and updates the table.

**Independent Test**: Open a list view, click the filter button, hover an attribute, fill in a value, verify the table filters.

### Implementation for User Story 1

- [ ] T004 [P] [US1] Create `FilterMenuSection` component in `entities/nodes/object/ui/filters/filter-menu-section.tsx` — renders a labeled group of menu items (e.g., "Attributes", "Relationships"). Accepts a `title` string and `children`. Uses `Col` from `@/shared/components/container`.
- [ ] T005 [P] [US1] Create `FilterMenuItem` component in `entities/nodes/object/ui/filters/filter-menu-item.tsx` — renders a single menu item with field name, icon (via `FieldSchemaIcon`), and active filter indicator. Accepts `columnSchema` (AttributeSchema | RelationshipSchema), `isActive` boolean, `onHover` callback. On pointer enter, calls `onHover` with the schema. Uses `Row` from `@/shared/components/container`.
- [ ] T006 [US1] Create `FilterMenu` component in `entities/nodes/object/ui/filters/filter-menu.tsx` — main popover triggered by a filter button. Contains: a scrollable list of `FilterMenuSection` groups (order: suggested, metadata, attributes, relationships), and a side panel that renders `AttributeFilterForm` or `RelationshipFilterForm` for the hovered item. Receives `schema: ModelSchema` and `filters: Filter[]` as props. Uses `Popover`/`PopoverContent`/`PopoverTrigger` from `@/shared/components/ui/popover`. Computes filterable fields using `getAttributesVisibleInListView` and `getRelationshipsVisibleInListView`. Includes metadata definitions from `metadata-filter-definitions.ts`. Passes `onSuccess` callback to filter forms to close the menu on apply.
- [ ] T007 [P] [US1] Simplify `TableColumnHeader` in `entities/nodes/object/ui/object-table/cells/table-column-header.tsx` — remove the `Popover`, `PopoverTrigger`, `PopoverContent`, `AttributeFilterForm`, and `RelationshipFilterForm` imports and rendering. Keep the header cell with field name, `FieldSchemaIcon`, and the filter indicator icon (purple `mdi:filter-variant` when a filter is active for that column). Component should no longer accept or use `PopoverTriggerProps`.
- [ ] T008 [P] [US1] Update `getObjectFieldsColumns` in `entities/nodes/object/ui/object-table/utils/get-object-table-columns.tsx` — remove `headerProps?: PopoverTriggerProps` parameter and stop passing it to `TableColumnHeader`. Update `getObjectTableColumns` signature accordingly.
- [ ] T009 [US1] Update `ObjectsManagerToolbar` in `entities/nodes/object/ui/objects-manager-toolbar.tsx` — add `FilterMenu` component between `FilterSearchInput` and `ActiveObjectFilterTags`. Pass `selectedSchema` and current `filters` from `useObjectTableContext()`.

**Checkpoint**: Filter menu opens from toolbar button, lists all attributes/relationships, hovering shows filter form, applying a filter updates the table. Column headers are display-only.

---

## Phase 4: User Story 2 — View and manage active filters (Priority: P1)

**Goal**: Active filter tags show condition label (e.g., "contains", "is any of"), are clickable to edit, have a remove icon, and active filters are visually marked in the filter menu.

**Independent Test**: Apply a filter, verify the tag shows condition + field + value, click the tag to edit, click the X to remove.

### Implementation for User Story 2

- [ ] T010 [P] [US2] Update `FilterTag` in `entities/nodes/object/ui/filters/filter-tag.tsx` — add a `condition` prop (string) displayed between the label and value (e.g., "Name **contains** router"). Add a dedicated remove button (X icon) with `stopPropagation`. Wrap the tag in a `Popover` that opens on click, rendering children passed via a new `editForm` render prop.
- [ ] T011 [P] [US2] Update `FilterMenuItem` in `entities/nodes/object/ui/filters/filter-menu-item.tsx` — add visual indicator for active filters. Check if any filter in the current `filters` array matches the item's field name (using `filter.name.startsWith(schema.name)`). If active: show a colored dot or checkmark icon next to the field name.
- [ ] T012 [US2] Update `ActiveFilterTags` in `shared/components/filters/active-filter-tags.tsx` — derive the condition label from the filter name suffix using the mapping: `__value`/`__values` → "contains", `__ids` → "is any of", `__isnull` + `true` → "is empty", `__isnull` + `false` → "is not empty", `__before` → "before", `__after` → "after". Pass condition to `FilterTag`. For click-to-edit: resolve the field schema (attribute or relationship) from `fieldSchemas` map and render the appropriate filter form (`AttributeFilterForm` or `RelationshipFilterForm`) inside the tag's `editForm` prop, pre-filled with the current value.
- [ ] T013 [US2] Update `ActiveObjectFilterTags` in `entities/nodes/object/ui/filters/active-object-filter-tags.tsx` — extend the `fieldSchemas` map to include metadata filter definitions (from `metadata-filter-definitions.ts`) so metadata active filter tags can resolve their schema and render the edit form.

**Checkpoint**: Active filter tags display condition labels, are clickable to edit with pre-filled forms, have working remove icons. Filter menu shows active indicators.

---

## Phase 5: User Story 3 — Filter by node metadata (Priority: P2)

**Goal**: Metadata filters (created_at, created_by, updated_at, updated_by) appear in the filter menu and work end-to-end.

**Independent Test**: Open filter menu, select "Created At", set a date range, verify the table filters. Select "Created By", pick a user, verify the table filters.

### Implementation for User Story 3

- [ ] T014 [US3] Integrate metadata filter definitions into `FilterMenu` in `entities/nodes/object/ui/filters/filter-menu.tsx` — import metadata definitions from `metadata-filter-definitions.ts` and add them as a "Metadata" section between suggested filters and attributes. Datetime metadata items render `AttributeFilterForm` on hover; user metadata items render `RelationshipFilterForm` on hover.
- [ ] T015 [US3] Verify metadata filter serialization works end-to-end — ensure that when a user applies a `node_metadata__created_at__after` filter via the date form, `addFiltersToRequest` (fixed in T001) correctly passes `node_metadata__created_at__after` as a GraphQL argument, and `removeFiltersNotInSchema` (fixed in T003) does not strip it out. Same for `node_metadata__created_by__ids`.

**Checkpoint**: All 4 metadata filters work: created_at/updated_at show date range pickers, created_by/updated_by show account selectors, filters apply and display as active tags.

---

## Phase 6: User Story 4 — Suggested filters in menu (Priority: P2)

**Goal**: Suggested filters (e.g., IPAM availability, internal groups) appear at the top of the filter menu as single-click toggle items.

**Independent Test**: Navigate to a CoreGroup list, open filter menu, verify "Hide internal groups" appears at top, click it, verify filter is applied.

### Implementation for User Story 4

- [ ] T016 [US4] Add suggested filter support to `FilterMenu` in `entities/nodes/object/ui/filters/filter-menu.tsx` — accept a `suggestedFilters` prop (array of `{id, label, isActive, onToggle}`). Render these at the top of the menu as a "Suggested" section. Each item is a single-click toggle (no hover submenu). Visually indicate active/inactive state.
- [ ] T017 [US4] Update `ObjectsManagerToolbar` in `entities/nodes/object/ui/objects-manager-toolbar.tsx` — compute suggested filters based on schema kind: `InternalGroupsFilterTag` logic for `CoreGroup`, `IpAvailabilityFilterTag` logic for IP prefix/address schemas. Pass as `suggestedFilters` prop to `FilterMenu`. Remove the `additionalTags` rendering from `ActiveObjectFilterTags` for filters now in the menu (avoid duplication).

**Checkpoint**: Suggested filters appear in the menu for applicable schemas. Clicking toggles the filter. Active state visible in both menu and active filter tags.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, edge cases, and cross-cutting improvements.

- [ ] T018 Ensure filter menu is scrollable when many filters exist — add `overflow-y-auto` with a `max-h` constraint to the menu list container in `entities/nodes/object/ui/filters/filter-menu.tsx`. Test with a schema that has 50+ attributes.
- [ ] T019 Handle edge case: schema with no filterable attributes/relationships — verify the filter menu still renders with metadata and suggested filter sections. Add empty state handling if all sections are empty.
- [ ] T020 Run `pnpm biome:fix` to format all modified and new files in `frontend/app/`.
- [ ] T021 Run `pnpm test` to verify no existing unit tests are broken by the refactor.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (Foundational)**: No dependencies — start immediately. T001, T002, T003 all run in parallel.
- **Phase 3 (US1)**: Depends on Phase 2 completion. T004+T005 in parallel, then T006. T007+T008 in parallel with T004-T006. T009 depends on T006-T008.
- **Phase 4 (US2)**: Depends on Phase 3 (needs FilterMenu and FilterTag). T010+T011 in parallel. T012 depends on T010. T013 depends on T012.
- **Phase 5 (US3)**: Depends on Phase 2 (T002, T003) and Phase 3 (T006 for menu). T014 then T015 sequential.
- **Phase 6 (US4)**: Depends on Phase 3 (T006 for menu). T016 then T017 sequential.
- **Phase 7 (Polish)**: Depends on all user stories.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational phase. This is the MVP.
- **US2 (P1)**: Depends on US1 (needs the filter menu and tag infrastructure).
- **US3 (P2)**: Depends on Foundational (metadata definitions) + US1 (filter menu). Can run in parallel with US2.
- **US4 (P2)**: Depends on US1 (filter menu). Can run in parallel with US2 and US3.

### Parallel Opportunities

Within Phase 2: T001, T002, T003 all touch different files — full parallelism.

Within Phase 3: T004+T005 in parallel (section + item components), then T006; T007+T008 in parallel (column header changes), then T009 integrates.

After Phase 3: US3 and US4 can run in parallel (both only need the filter menu from US1).

---

## Parallel Example: Foundational Phase

```
# All three foundational tasks touch different files — run in parallel:
Task T001: "Fix addFiltersToRequest in shared/api/graphql/utils.ts"
Task T002: "Create metadata-filter-definitions.ts"
Task T003: "Update remove-filters-not-in-schema.ts"
```

## Parallel Example: User Story 1

```
# Menu building blocks in parallel:
Task T004: "Create FilterMenuSection component"
Task T005: "Create FilterMenuItem component"

# Column header cleanup in parallel with menu assembly:
Task T007: "Simplify TableColumnHeader"
Task T008: "Update getObjectFieldsColumns"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001-T003)
2. Complete Phase 3: User Story 1 (T004-T009)
3. **STOP and VALIDATE**: Filter menu opens, lists fields, hover shows forms, applying works, column headers are display-only
4. Deploy/demo if ready

### Incremental Delivery

1. Foundational (Phase 2) → Bug fix + metadata definitions ready
2. US1 (Phase 3) → Filter menu works → **MVP** ✅
3. US2 (Phase 4) → Active filters show conditions, click-to-edit, menu indicators
4. US3 (Phase 5) → Metadata filters work end-to-end
5. US4 (Phase 6) → Suggested filters in menu
6. Polish (Phase 7) → Scrolling, edge cases, lint, tests

Each story adds value without breaking previous stories.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- All new components: named exports, `kebab-case.tsx`, `Col`/`Row` for layout, no `useMemo`/`useCallback`
- Metadata filter names MUST use `node_metadata__` prefix for backend compatibility
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
