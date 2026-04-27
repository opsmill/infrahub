# Research: Unified Filter Menu with Metadata Filters

## R1: Date range filters (before/after) not serialized to GraphQL

**Decision**: Add `before` and `after` cases to `addFiltersToRequest` in `shared/api/graphql/utils.ts`.

**Rationale**: The `DateRangeFilterForm` in `attribute-filter-form.tsx` creates filters with names like `fieldName__before` and `fieldName__after`, but `addFiltersToRequest` only handles `value`, `values`, `isnull`, and `ids` keys. The `before`/`after` cases silently fall through the switch statement, meaning date range filters are created in the UI but never sent to the backend. This is an existing bug that must be fixed for metadata timestamp filters to work.

**Fix**: Add cases for `before` and `after` in the switch:
```typescript
case "before":
case "after": {
  acc[filter.name] = filter.value;
  break;
}
```

**Alternatives considered**: None — this is a straightforward bug fix required for the feature.

## R2: Backend support for metadata filtering in GraphQL

**Decision**: Backend fully supports all metadata filters. No backend changes needed.

**Finding**: The backend GraphQL API supports all four metadata fields with the `node_metadata__` prefix:

| Filter | GraphQL Argument |
|--------|-----------------|
| Created at (after) | `node_metadata__created_at__after` |
| Created at (before) | `node_metadata__created_at__before` |
| Created by (ids) | `node_metadata__created_by__ids` |
| Updated at (after) | `node_metadata__updated_at__after` |
| Updated at (before) | `node_metadata__updated_at__before` |
| Updated by (ids) | `node_metadata__updated_by__ids` |

**Critical implementation detail**: Metadata filter names MUST use the `node_metadata__` prefix (e.g., `node_metadata__created_at__after`), NOT `created_at__after`. This prefix is how the backend distinguishes metadata filters from schema attribute filters.

**Backend references**:
- GraphQL schema: `schema/schema.graphql` (lines 12483-12501)
- Filter argument registration: `backend/infrahub/graphql/manager.py` (`_get_node_metadata_filter_arguments()`, lines 1084-1110)
- Query builder: `backend/infrahub/core/query/node.py` (`NODE_METADATA_PREFIX = "node_metadata__"`)

**Note**: Old `_updated_at` fields are deprecated with message "Query the node_metadata field instead. Will be removed in Infrahub 1.9".

## R3: Filter menu interaction pattern (hover submenu)

**Decision**: Use a popover-based menu with hover-triggered submenu panels.

**Rationale**: The filter menu needs to show a list of filter names, and on hover, reveal the filter form (AttributeFilterForm or RelationshipFilterForm) to the side. This is a standard submenu/flyout pattern.

**Implementation approach**:
- Main menu: A `Popover` (from shared UI components) triggered by the filter button
- Menu items: Custom list items with `onHoverStart` / `onPointerEnter` to track the hovered item
- Submenu panel: A side panel (positioned to the right of the menu) that renders the appropriate filter form for the hovered item
- The filter forms already accept `onSuccess` callbacks to close the menu after applying

**Alternatives considered**:
- React Aria `MenuTrigger` + `SubMenu`: More semantic but would require wrapping existing filter forms as menu items, which is awkward since they contain interactive form elements
- Radix UI `DropdownMenu` with sub-menus: Same issue — sub-menus expect menu items, not complex forms
- Custom popover with side panel: Most flexible, allows existing filter forms to render unmodified

## R4: Metadata filter field definitions

**Decision**: Define metadata filters as pseudo-schema objects that match `AttributeSchema` / `RelationshipSchema` types.

**Rationale**: The existing `AttributeFilterForm` expects an `AttributeSchema` object, and `RelationshipFilterForm` expects a `RelationshipSchema` object. To reuse these components for metadata filters, we need to create compatible type definitions for:
- `created_at`: `AttributeSchema` with `kind: "DateTime"`, `name: "node_metadata__created_at"`, `label: "Created At"`
- `updated_at`: `AttributeSchema` with `kind: "DateTime"`, `name: "node_metadata__updated_at"`, `label: "Updated At"`
- `created_by`: `RelationshipSchema` with `peer: "CoreAccount"`, `name: "node_metadata__created_by"`, `label: "Created By"`
- `updated_by`: `RelationshipSchema` with `peer: "CoreAccount"`, `name: "node_metadata__updated_by"`, `label: "Updated By"`

**Critical**: The `name` field uses the `node_metadata__` prefix so that when the filter form creates filters like `node_metadata__created_at__after`, the `addFiltersToRequest` utility passes them through to GraphQL with the correct prefix the backend expects.

These will be defined in a new `metadata-filter-definitions.ts` file.

**Alternatives considered**:
- Extending the schema at the backend level to include metadata as real attributes: Too invasive, changes the schema contract
- Building separate form components for metadata: Violates FR-006 (reuse existing components)

## R5: Active filter tag click-to-edit behavior

**Decision**: Wrap each `FilterTag` in a popover that shows the filter form on click.

**Rationale**: Currently `FilterTag` only supports removal (via the TagGroup's `onSelectionChange`). The spec requires clicking a tag to open the filter form for editing. This requires:
- Adding a popover/overlay trigger to each filter tag
- When clicked, showing the appropriate filter form (attribute or relationship) pre-filled with the current filter value
- The tag's remove icon (X) must still work independently of the click-to-edit

**Implementation approach**: The `FilterTag` component gets wrapped in a `Popover`. Clicking the tag body opens the popover with the filter form. The remove icon gets `stopPropagation` to prevent triggering the edit popover.

**Condition display**: Active filter tags must show the filter condition alongside field name and value. The condition is derived from the filter name suffix:
- `__value` / `__values` → "contains" (or "is any of" for arrays)
- `__ids` → "is any of"
- `__isnull` with `true` → "is empty"
- `__isnull` with `false` → "is not empty"
- `__before` → "before"
- `__after` → "after"

This mapping can use/extend the existing `getCurrentFilterCondition` utility in `shared/components/filters/utils/`.

## R6: Suggested filters in the menu

**Decision**: Suggested filters (InternalGroupsFilterTag, IpAvailability) appear as simple toggle items at the top of the menu.

**Rationale**: These filters don't have complex forms — they're binary toggles. In the menu, they appear as clickable items that directly apply/toggle the filter when clicked (no hover submenu needed).

**Implementation approach**: 
- The menu receives `suggestedFilters` as a prop (list of filter definitions with label, id, and toggle handler)
- Each suggested filter is a single-click menu item (no submenu)
- The schema-specific suggested filters (InternalGroups for CoreGroup, IpAvailability for IP schemas) are determined by the parent component based on schema kind

## R7: remove-filters-not-in-schema update

**Decision**: Update `removeFiltersNotInSchema` to allow metadata filter names to pass through validation.

**Rationale**: Currently, `removeFiltersNotInSchema` checks that filter names match schema attributes or relationships. Metadata filters (`node_metadata__created_at__*`, `node_metadata__created_by__*`, etc.) don't exist in the schema, so they'd be stripped out. The function needs to recognize the `node_metadata__` prefix and allow those filters through.

## R8: Active filters visible in filter menu

**Decision**: Menu items with active filters show a visual indicator (e.g., dot, checkmark, or highlighted background) and optionally the current filter summary.

**Rationale**: When a user opens the filter menu, they need to see at a glance which filters are already applied. This prevents confusion and allows quick navigation to edit an existing filter.

**Implementation approach**:
- Each `FilterMenuItem` receives the current filters array and checks if any filter matches its field name
- If a filter is active for that item: render a visual indicator (e.g., a colored dot or checkmark icon) and optionally show a condensed value summary
- Hovering an active filter item in the menu opens the same filter form, pre-filled with the current value (same behavior as hovering an inactive item, but the form has the existing value)
- This reuses the same logic as `ActiveFilterTags` for determining whether a filter matches a field

## R9: Column header simplification

**Decision**: Replace `TableColumnHeader` popover with a display-only header, keeping the filter icon indicator.

**Rationale**: Per clarification, column headers should no longer be clickable filter triggers. The `TableColumnHeader` component currently wraps content in a `Popover` with `PopoverTrigger`. This needs to be simplified to a plain header cell that:
- Shows the field name and icon
- Shows the filter indicator icon (purple) when a filter is active for that column
- Is NOT interactive (no popover, no click handler)

This also means `getObjectFieldsColumns` no longer needs to pass `PopoverTriggerProps` to headers.
