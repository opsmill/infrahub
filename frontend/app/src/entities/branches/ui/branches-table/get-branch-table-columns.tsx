import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { BranchActionsCell } from "@/entities/branches/ui/branches-table/cells/branch-actions-cell";
import { BranchCreatedByCell } from "@/entities/branches/ui/branches-table/cells/branch-created-by-cell";
import { BranchDateCell } from "@/entities/branches/ui/branches-table/cells/branch-date-cell";
import { BranchIdentifierHeader } from "@/entities/branches/ui/branches-table/cells/branch-identifier-header";
import { BranchNameCell } from "@/entities/branches/ui/branches-table/cells/branch-name-cell";
import { BranchProposedChangesCell } from "@/entities/branches/ui/branches-table/cells/branch-proposed-changes-cell";
import { BranchStatusCell } from "@/entities/branches/ui/branches-table/cells/branch-status-cell";
import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { TableColumnHeaderSimple } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-simple";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";

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
  // TODO: Enable filters when backend supports them (use TableColumnHeader instead of TableColumnHeaderSimple)
  return [
    columnHelper.accessor("status", {
      id: "status",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.status} />,
      cell: ({ cell }) => <BranchStatusCell status={cell.getValue()} />,
    }) as ColumnDef<BranchListItem>,
    columnHelper.display({
      id: "proposed_changes",
      header: () => (
        <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.proposed_changes} />
      ),
      cell: ({ row }) => <BranchProposedChangesCell branchName={row.original.name} />,
    }),
    columnHelper.accessor("branched_from", {
      id: "branched_from",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.branched_from} />,
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }),
    columnHelper.accessor("updated_at", {
      id: "updated_at",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.updated_at} />,
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }),
    columnHelper.accessor("created_at", {
      id: "created_at",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.created_at} />,
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }),
    columnHelper.accessor("created_by", {
      id: "created_by",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.created_by} />,
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
