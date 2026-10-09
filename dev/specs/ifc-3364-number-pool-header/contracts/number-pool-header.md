# UI contract: number pool header

This work changes no API. This contract describes the components the page uses and what they show in each state.

## `NumberPoolDetailsPage`

Location: `pages/resource-manager/number-pool-details.tsx`. `ResourcePoolContentWithPermissions` renders it when the pool's kind is `CoreNumberPool`.

```ts
interface NumberPoolDetailsPageProps {
  poolId: string;
  schema: ModelSchema; // the CoreNumberPool schema
  permission: Permission;
}
```

It calls `useGetNumberPool(poolId)`.

| State | What it shows |
|-------|---------------|
| Pool loading | `NumberPoolHeaderSkeleton`, then `ResourcePoolDetailsBody` with its own loading state |
| Pool failed to load or not found | The existing error screen |
| Pool loaded | `NumberPoolHeader`, then `ResourcePoolDetailsBody` (the current body, unchanged) |

## `useGetNumberPool`

Location: `entities/resource-manager/ui/queries/get-number-pool.query.ts`.

```ts
useGetNumberPool(poolId: string): UseQueryResult<NumberPoolData>
```

- **Branch and date**: read from the current branch and the time-travel date, and included in the key.
- **Query key**: `resourceManagerQueryKeys.numberPool({ poolId, branchName, atDate })` = `["resource-manager", "number-pool", poolId, branchName, atDate]`.
- **Invalidated by**: the reload button and the menu's `onUpdateComplete`, both through `resourceManagerQueryKeys.all`.

## `NumberPoolHeader` and `NumberPoolHeaderSkeleton`

Location: `entities/resource-manager/ui/number-pool/number-pool-header.tsx`.

```ts
interface NumberPoolHeaderProps {
  pool: NumberPoolData;
  schema: ModelSchema; // the CoreNumberPool schema, for the documentation link
  permission: Permission;
}
```

`NumberPoolHeaderSkeleton` takes no props. It shows a placeholder for the name and one for the Actions button.

Layout of `NumberPoolHeader`, from top to bottom:

1. **First row**:
   - Name: one line, ellipsis, full name on hover.
   - Metadata popover, next to the name, as on other node detail pages.
   - "Managed by schema" tag, for schema-created pools only.
   - On the right: full ID with copy button, reload button (`RefreshButton queryKey={resourceManagerQueryKeys.all}`), Actions menu.
2. **Description**: shown only when the pool has one.
3. **Allocation sentence**: `Allocates to <kind> attribute <attribute>`. The allocation scope is not shown.

Accessible names that tests rely on:

| Element | Role and name |
|---------|---------------|
| Name | `heading`, level 1, the pool name |
| Copy ID button | `button` "Copy ID" |
| Metadata popover | `button` "View node metadata" (unchanged) |
| Reload button | `button` "Refresh data"; invalidates `resourceManagerQueryKeys.all` |
| Actions menu | `button` "Actions" |
| Managed-by tag, schema-created pool | `button` "Managed by schema"; opens `dialog` "Schema viewer" |
| Kind in the sentence, kind in the schema | `button`, the kind name; opens `dialog` "Schema viewer" |
| Attribute, kind in the schema | `button`, the attribute name; opens `dialog` "Schema viewer" |

## `NumberPoolActionsMenu`

Location: `entities/resource-manager/ui/number-pool/number-pool-actions-menu.tsx`.

```ts
interface NumberPoolActionsMenuProps {
  pool: NumberPoolData;
  schema: ModelSchema;
  permission: Permission;
}
```

| Section | Item | Icon | Shown when | Disabled when (tooltip) |
|---------|------|------|-----------|-------------------------|
| Actions | Copy ID | lucide `CopyIcon` (from `CopyToClipboardMenuItem`) | always | never |
| Actions | Copy HFID | lucide `CopyIcon` (from `CopyToClipboardMenuItem`) | `pool.hfid` is set | never |
| Go to | Tasks | `TasksStatusIcon` | always | never |
| Go to | View schema (`/schema?kind=CoreNumberPool`) | `mdi:code-json` | always | never |
| Go to | GraphQL sandbox | `mdi:graphql` | always | never |
| Go to | Documentation (opens in a new tab) | lucide `BookTextIcon` | `schema.documentation` is set | never |
| Manage | Edit | lucide `PencilLineIcon` | always | schema-created (schema lock message), else `!permission.update.isAllowed` (permission message) |
| Manage | Groups | lucide `GroupIcon` | always | schema-created (schema lock message), else `!permission.update.isAllowed` (permission message) |
| Manage | Delete | lucide `Trash2Icon` | always | schema-created (schema lock message), else `!permission.delete.isAllowed` (permission message) |

- **Schema lock message**: `Defined by the schema attribute <node>.<node_attribute>`. On a schema-created pool it replaces the permission message, even when the user also lacks permission.
- **Keyboard**: every item sets `textValue`, so typing a letter moves focus to the first item whose label starts with it.

After the user acts:

- **Edit saved**: the sheet closes. The update mutation reloads the `"objects"` queries, and the menu then invalidates `resourceManagerQueryKeys.all`, so the header shows the new values (research.md R14).
- **Delete succeeded**: the app navigates to `/resource-manager/`.

## URL builders (moved)

Location: `entities/nodes/object/ui/routing/object-urls.ts`.

```ts
getObjectTasksUrl(objectId: string): string
getObjectGraphqlSandboxUrl(objectKind: string, objectId: string): string
getDocumentationUrl(documentation: string): string
```

Each one returns the URL that the object details menu and the artifact details menu build inline today.
