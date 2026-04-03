# Object Permissions DataTable Migration

## Summary

Migrate `src/pages/role-management/object-permissions.tsx` from the legacy `Table` component to the shared `DataTable` component, fully aligning with the pattern already used by accounts, groups, and roles pages.

## Approach

Full pattern alignment (Approach A): mirror the structure of `accounts.tsx`, `groups.tsx`, and `roles.tsx` exactly.

- Switch from `useGetObjectPermissions` to the generic `useObjects` + `useObjectsCount` queries
- Use `ObjectTableProvider` for permissions, filters, and schema context
- Use `ObjectsManagerToolbar` for search/filter and create button
- Use `DataTable` with `InfiniteScroll` for the table
- Use `getObjectActionsColumn` for row-level edit/delete actions

## Files to Create

### `src/entities/role-manager/ui/object-permission-table.tsx`

Table component following the established pattern:

- Uses `useObjectTableContext()` for filters, schema, permission
- Fetches data with `useObjects` and `useObjectsCount`
- Filters visible attributes to: `namespace`, `name`, `action`, `decision`
- Filters visible relationships to: `roles`
- Combines custom columns with `getObjectActionsColumn`
- Wraps `DataTable` in `InfiniteScroll`

Exported constants:
- `OBJECT_PERMISSION_TABLE_ATTRIBUTES = ["namespace", "name", "action", "decision"]`
- `OBJECT_PERMISSION_TABLE_RELATIONSHIPS = ["roles"]`

### `src/entities/role-manager/ui/get-object-permission-table-columns.tsx`

Column definitions using `createColumnHelper<NodeObject>`:

1. **Identifier column** - Standard `TableIdentifierHeader` + `TableIdentifierCell` with checkbox and link
2. **Attribute columns** - Standard `TableAttributeCell` for `namespace` and `action` (name excluded, already in identifier)
3. **Decision column** (custom) - Renders allow/deny icon (green/red `Pill` + `Icon`) alongside the label from `objectDecisionOptions`
4. **Relationship columns** - Standard `TableRelationshipCell` for `roles`

Module-level `decisionIcons` map moved from the current page file.

## Files to Modify

### `src/pages/role-management/object-permissions.tsx`

Simplified to:

```tsx
export function Component() {
  const { schema } = useSchema(OBJECT_PERMISSION_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <ObjectPermissionTable />
    </ObjectTableProvider>
  );
}
```

All removed:
- Manual state: `search`, `rowToDelete`, `rowToUpdate`, `showDrawer`
- `useGetObjectPermissions` query hook usage
- `useDebounce` for search
- `schemaKindNameState` atom usage
- Inline column/row definitions
- `SearchInput`, `Pagination`, `SlideOver`, `ModalDeleteObject`, `ObjectForm`
- Manual error/loading/permission handling

## What Changes for Users

- **Gained:** Infinite scroll, bulk row selection, bulk edit/delete actions, filter tags, standard filter search (replaces simple text search)
- **Lost:** `BadgeCopy` identifier column (replaced by standard identifier cell with link to detail page)
- **Changed:** Decision column still shows icon + label but uses DataTable cell styling

## Column Order

Identifier | Namespace | Action | Decision | Roles | Actions (dropdown)

## No Changes To

- `useGetObjectPermissions` hook (remains in codebase, just unused by this page after migration)
- `objectDecisionOptions` constant (still imported by the new column definitions)
- `global-permissions.tsx` (separate migration)
