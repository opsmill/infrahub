# Object Permissions DataTable Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `object-permissions.tsx` from the legacy `Table` component to the shared `DataTable` component, fully aligning with the pattern used by accounts, groups, and roles pages.

**Architecture:** Create two new files (`object-permission-table.tsx` and `get-object-permission-table-columns.tsx`) following the exact same structure as the existing account table files, then simplify the page component to use `ObjectTableProvider` + `ObjectsManagerToolbar` + `ObjectPermissionTable`.

**Tech Stack:** React 19, TanStack React Table v8, TypeScript, Vitest

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/entities/role-manager/ui/get-object-permission-table-columns.tsx` | Column definitions + decision icon rendering |
| Create | `src/entities/role-manager/ui/object-permission-table.tsx` | Table component with data fetching |
| Modify | `src/pages/role-management/object-permissions.tsx` | Simplify to provider + toolbar + table |

---

### Task 1: Create column definitions

**Files:**
- Create: `src/entities/role-manager/ui/get-object-permission-table-columns.tsx`

- [ ] **Step 1: Create the column definitions file**

Create `src/entities/role-manager/ui/get-object-permission-table-columns.tsx`:

```tsx
import { Icon } from "@iconify-icon/react";
import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { Pill } from "@/shared/components/display/pill";
import { TableCell } from "@/shared/components/table/table-cell";

import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableIdentifierHeader } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-header";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeAttribute, NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { objectDecisionOptions } from "@/entities/role-manager/constants";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";

export const OBJECT_PERMISSION_TABLE_ATTRIBUTES = ["namespace", "name", "action", "decision"];
export const OBJECT_PERMISSION_TABLE_RELATIONSHIPS = ["roles"];

const decisionIcons: Record<string, React.ReactNode> = {
  allow: (
    <Pill className="flex h-6 w-6 items-center justify-center bg-green-500/40">
      <Icon icon="mdi:lock-open-check-outline" className="text-green-900" />
    </Pill>
  ),
  deny: (
    <Pill className="flex h-6 w-6 items-center justify-center bg-red-500/40">
      <Icon icon="mdi:lock-remove-outline" className="text-red-900" />
    </Pill>
  ),
};

const columnHelper = createColumnHelper<NodeObject>();

export function getObjectPermissionTableColumns(
  schema: ModelSchema
): Array<ColumnDef<NodeObject>> {
  const attributesVisible = (schema.attributes ?? []).filter(
    ({ name }) => OBJECT_PERMISSION_TABLE_ATTRIBUTES.includes(name) && name !== "name" && name !== "decision"
  );
  const relationshipsVisible = (schema.relationships ?? []).filter(({ name }) =>
    OBJECT_PERMISSION_TABLE_RELATIONSHIPS.includes(name)
  );

  return [
    columnHelper.accessor((node) => getNodeLabel(node), {
      id: "id",
      header: ({ table }) => (
        <TableIdentifierHeader
          schema={schema}
          isSelected={table.getIsAllRowsSelected()}
          isIndeterminate={table.getIsSomePageRowsSelected()}
          onChange={table.toggleAllRowsSelected}
        />
      ),
      cell: ({ cell, row, table }) => {
        const label = cell.getValue();
        return (
          <TableIdentifierCell
            objectKind={row.original.__typename}
            objectId={row.original.id}
            label={label}
            isSelected={row.getIsSelected()}
            onClickCheckbox={getToggleSelectedRowHandler({ row, table })}
          />
        );
      },
    }),
    ...attributesVisible.map((attribute) =>
      columnHelper.accessor(attribute.name, {
        header: () => <TableColumnHeader columnSchema={attribute} />,
        cell: ({ cell }) => {
          const attributeData = cell.getValue() as NodeAttribute | undefined;
          return (
            <TableCell>
              <TableAttributeCell attributeSchema={attribute} attributeData={attributeData} />
            </TableCell>
          );
        },
      })
    ),
    columnHelper.accessor("decision", {
      header: () => "Decision",
      cell: ({ cell }) => {
        const attributeData = cell.getValue() as NodeAttribute | undefined;
        const value = attributeData?.value;
        const label = objectDecisionOptions.find((o) => o.value === value)?.label;
        const iconKey = typeof value === "string" ? value : undefined;
        return (
          <TableCell>
            <div className="flex items-center gap-2">
              {iconKey && decisionIcons[iconKey]}
              {label}
            </div>
          </TableCell>
        );
      },
    }),
    ...relationshipsVisible.map((relationship) =>
      columnHelper.accessor(relationship.name, {
        header: () => <TableColumnHeader columnSchema={relationship} />,
        cell: ({ cell }) => {
          const relationshipData = cell.getValue() as NodeRelationship | undefined;
          if (!relationshipData) return null;
          return (
            <TableCell>
              <TableRelationshipCell
                relationshipSchema={relationship as RelationshipSchema}
                relationshipData={relationshipData}
              />
            </TableCell>
          );
        },
      })
    ),
  ] as Array<ColumnDef<NodeObject>>;
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd frontend/app && pnpm tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors related to `get-object-permission-table-columns.tsx`

- [ ] **Step 3: Commit**

```bash
git add src/entities/role-manager/ui/get-object-permission-table-columns.tsx
git commit -m "feat(frontend): add object permission table column definitions"
```

---

### Task 2: Create table component

**Files:**
- Create: `src/entities/role-manager/ui/object-permission-table.tsx`

- [ ] **Step 1: Create the table component file**

Create `src/entities/role-manager/ui/object-permission-table.tsx`:

```tsx
import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import {
  OBJECT_PERMISSION_TABLE_ATTRIBUTES,
  OBJECT_PERMISSION_TABLE_RELATIONSHIPS,
  getObjectPermissionTableColumns,
} from "@/entities/role-manager/ui/get-object-permission-table-columns";

export function ObjectPermissionTable() {
  const { filters, selectedSchema, permission } = useObjectTableContext();

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters,
  });

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage, error } = useObjects({
    schema: selectedSchema,
    filters,
    getAttributesVisible: (attributes) =>
      attributes.filter((a) => OBJECT_PERMISSION_TABLE_ATTRIBUTES.includes(a.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((r) => OBJECT_PERMISSION_TABLE_RELATIONSHIPS.includes(r.name)),
  });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [
    ...getObjectPermissionTableColumns(selectedSchema),
    getObjectActionsColumn(permission),
  ];
  const rows = data?.pages.flat() ?? [];

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={rows}
        count={count}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
      />
    </InfiniteScroll>
  );
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd frontend/app && pnpm tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors related to `object-permission-table.tsx`

- [ ] **Step 3: Commit**

```bash
git add src/entities/role-manager/ui/object-permission-table.tsx
git commit -m "feat(frontend): add ObjectPermissionTable component"
```

---

### Task 3: Rewrite the page component

**Files:**
- Modify: `src/pages/role-management/object-permissions.tsx`

- [ ] **Step 1: Replace the entire file contents**

Replace `src/pages/role-management/object-permissions.tsx` with:

```tsx
import { OBJECT_PERMISSION_OBJECT } from "@/shared/config/constants";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { ObjectPermissionTable } from "@/entities/role-manager/ui/object-permission-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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

- [ ] **Step 2: Verify the file compiles**

Run: `cd frontend/app && pnpm tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [ ] **Step 3: Run linter**

Run: `cd frontend/app && pnpm biome:fix`
Expected: All files formatted/linted cleanly

- [ ] **Step 4: Commit**

```bash
git add src/pages/role-management/object-permissions.tsx
git commit -m "feat(frontend): migrate object-permissions page to DataTable"
```

---

### Task 4: Verify build and tests

- [ ] **Step 1: Run the full build**

Run: `cd frontend/app && pnpm build`
Expected: Build succeeds with no errors

- [ ] **Step 2: Run existing tests**

Run: `cd frontend/app && pnpm test`
Expected: All tests pass (no regressions)

- [ ] **Step 3: Final commit if any lint/format changes were needed**

If Step 1 or 2 required fixes, commit them:

```bash
git add -u
git commit -m "fix(frontend): address build/lint issues from object-permissions migration"
```
