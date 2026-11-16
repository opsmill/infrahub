import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { WIDE_COLUMN_MAX_WIDTH } from "@/shared/components/table/style";

import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import type { BranchTableRow } from "@/entities/branches/ui/branches-table/branch-table-row";
import { BranchActionsCell } from "@/entities/branches/ui/branches-table/cells/branch-actions-cell";
import { BranchCreatedByCell } from "@/entities/branches/ui/branches-table/cells/branch-created-by-cell";
import { BranchDateCell } from "@/entities/branches/ui/branches-table/cells/branch-date-cell";
import { BranchGitStateCell } from "@/entities/branches/ui/branches-table/cells/branch-git-state-cell";
import { BranchIdentifierHeader } from "@/entities/branches/ui/branches-table/cells/branch-identifier-header";
import { BranchNameCell } from "@/entities/branches/ui/branches-table/cells/branch-name-cell";
import { BranchProposedChangesCell } from "@/entities/branches/ui/branches-table/cells/branch-proposed-changes-cell";
import { BranchRepositoriesCell } from "@/entities/branches/ui/branches-table/cells/branch-repositories-cell";
import { BranchStatusCell } from "@/entities/branches/ui/branches-table/cells/branch-status-cell";
import { BranchStatusHeader } from "@/entities/branches/ui/branches-table/cells/branch-status-header";
import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableColumnHeaderSimple } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-simple";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";

const columnHelper = createColumnHelper<BranchTableRow>();

export function getBranchIdentifierColumn(): ColumnDef<BranchTableRow> {
  return columnHelper.display({
    id: "id",
    meta: { gridTrack: `fit-content(${WIDE_COLUMN_MAX_WIDTH})` },
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

export function getBranchFieldsColumns(): Array<ColumnDef<BranchTableRow>> {
  return [
    columnHelper.display({
      id: "status",
      header: () => <BranchStatusHeader />,
      cell: ({ row }) => <BranchStatusCell status={row.original.status} />,
    }),
    columnHelper.display({
      id: "proposed_changes",
      meta: { gridTrack: "minmax(150px, 200px)" },
      size: 250,
      minSize: 250,
      header: () => (
        <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.proposed_changes} />
      ),
      cell: ({ row }) => <BranchProposedChangesCell branchName={row.original.name} />,
    }),
    columnHelper.display({
      id: "repositories",
      // Fixed so the cells filling in as repositories load do not shift the columns.
      meta: { gridTrack: "minmax(12rem, 18rem)" },
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.repositories} />,
      cell: ({ row }) => <BranchRepositoriesCell branch={row.original} />,
    }),
    columnHelper.display({
      id: "git_state",
      meta: { gridTrack: "9rem" },
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.git_state} />,
      cell: ({ row }) => <BranchGitStateCell branch={row.original} />,
    }),
    columnHelper.display({
      id: "branched_from",
      header: () => <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.branched_from} />,
      cell: ({ row }) => <BranchDateCell date={row.original.branched_from} />,
    }),
    columnHelper.display({
      id: "updated_at",
      header: () => (
        <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.node_metadata__updated_at} />
      ),
      cell: ({ row }) => <BranchDateCell date={row.original.updated_at} />,
    }),
    columnHelper.display({
      id: "created_at",
      header: () => (
        <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.node_metadata__created_at} />
      ),
      cell: ({ row }) => <BranchDateCell date={row.original.created_at} />,
    }),
    columnHelper.display({
      id: "created_by",
      header: () => (
        <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.node_metadata__created_by} />
      ),
      cell: ({ row }) => <BranchCreatedByCell createdBy={row.original.created_by} />,
    }),
  ];
}

export function getBranchActionsColumn(): ColumnDef<BranchTableRow> {
  return columnHelper.display({
    id: "actions",
    meta: { gridTrack: "2.5rem" },
    header: () => <ActionsHeaderCell />,
    cell: ({ row }) => <BranchActionsCell branch={row.original} />,
  });
}

export function getBranchTableColumns(): Array<ColumnDef<BranchTableRow>> {
  return [getBranchIdentifierColumn(), ...getBranchFieldsColumns(), getBranchActionsColumn()];
}
