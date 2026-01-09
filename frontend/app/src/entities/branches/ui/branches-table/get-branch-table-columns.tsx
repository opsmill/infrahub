import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { BranchActionsCell } from "@/entities/branches/ui/branches-table/cells/branch-actions-cell";
import { BranchCreatedByCell } from "@/entities/branches/ui/branches-table/cells/branch-created-by-cell";
import { BranchDateCell } from "@/entities/branches/ui/branches-table/cells/branch-date-cell";
import { BranchIdentifierHeader } from "@/entities/branches/ui/branches-table/cells/branch-identifier-header";
import { BranchNameCell } from "@/entities/branches/ui/branches-table/cells/branch-name-cell";
import { BranchTableHeader } from "@/entities/branches/ui/branches-table/cells/branch-table-header";
import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

const columnHelper = createColumnHelper<BranchListItem>();

export function getBranchIdentifierColumn(): ColumnDef<BranchListItem, string> {
  return columnHelper.accessor("name", {
    id: "id",
    header: ({ table }) => (
      <BranchIdentifierHeader
        isSelected={table.getIsAllRowsSelected()}
        isIndeterminate={table.getIsSomePageRowsSelected()}
        onChange={table.toggleAllRowsSelected}
      />
    ),
    cell: ({ row, table }) => (
      <BranchNameCell
        branch={row.original}
        isSelected={row.getIsSelected()}
        onClickCheckbox={getToggleSelectedRowHandler({ row, table })}
      />
    ),
  });
}

export function getBranchFieldsColumns(): Array<ColumnDef<BranchListItem>> {
  return [
    columnHelper.accessor("branched_from", {
      id: "branched_from",
      header: () => (
        <BranchTableHeader fieldSchema={{ kind: "DateTime" } as AttributeSchema}>
          Last Rebase
        </BranchTableHeader>
      ),
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }),
    columnHelper.accessor("updated_at", {
      id: "updated_at",
      header: () => (
        <BranchTableHeader fieldSchema={{ kind: "DateTime" } as AttributeSchema}>
          Last Update
        </BranchTableHeader>
      ),
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }),
    columnHelper.accessor("created_at", {
      id: "created_at",
      header: () => (
        <BranchTableHeader fieldSchema={{ kind: "DateTime" } as AttributeSchema}>
          Created At
        </BranchTableHeader>
      ),
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }),
    columnHelper.accessor("created_by", {
      id: "created_by",
      header: () => (
        <BranchTableHeader fieldSchema={{ peer: "CoreAccount" } as RelationshipSchema}>
          Created By
        </BranchTableHeader>
      ),
      cell: ({ cell }) => <BranchCreatedByCell createdBy={cell.getValue()} />,
    }),
  ];
}

export function getBranchActionsColumn(): ColumnDef<BranchListItem> {
  return columnHelper.display({
    id: "actions",
    header: () => <ActionsHeaderCell />,
    cell: ({ row }) => <BranchActionsCell branch={row.original} />,
  });
}

export function getBranchTableColumns(): Array<ColumnDef<BranchListItem>> {
  return [
    getBranchIdentifierColumn() as ColumnDef<BranchListItem>,
    ...getBranchFieldsColumns(),
    getBranchActionsColumn(),
  ];
}
