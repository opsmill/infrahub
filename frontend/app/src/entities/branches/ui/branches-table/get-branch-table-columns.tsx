import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import {
  type BranchTableRow,
  isBranchAnchorRow,
} from "@/entities/branches/domain/model/branch-table-row";
import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { BranchActionsCell } from "@/entities/branches/ui/branches-table/cells/branch-actions-cell";
import { BranchCommitCell } from "@/entities/branches/ui/branches-table/cells/branch-commit-cell";
import { BranchCreatedByCell } from "@/entities/branches/ui/branches-table/cells/branch-created-by-cell";
import { BranchDateCell } from "@/entities/branches/ui/branches-table/cells/branch-date-cell";
import { BranchGitStateCell } from "@/entities/branches/ui/branches-table/cells/branch-git-state-cell";
import { BranchIdentifierHeader } from "@/entities/branches/ui/branches-table/cells/branch-identifier-header";
import { BranchNameCell } from "@/entities/branches/ui/branches-table/cells/branch-name-cell";
import { BranchProposedChangesCell } from "@/entities/branches/ui/branches-table/cells/branch-proposed-changes-cell";
import { BranchRepositoryCell } from "@/entities/branches/ui/branches-table/cells/branch-repository-cell";
import { BranchStatusCell } from "@/entities/branches/ui/branches-table/cells/branch-status-cell";
import { BranchStatusHeader } from "@/entities/branches/ui/branches-table/cells/branch-status-header";
import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableColumnHeaderSimple } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-simple";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";

const columnHelper = createColumnHelper<BranchTableRow>();

export function getBranchIdentifierColumn(): ColumnDef<BranchTableRow, string> {
  return columnHelper.accessor((r) => r.branch.name, {
    id: "id",
    header: ({ table }) => (
      <BranchIdentifierHeader
        isSelected={table.getIsAllRowsSelected()}
        isIndeterminate={table.getIsSomePageRowsSelected()}
        onChange={table.toggleAllRowsSelected}
      />
    ),
    cell: ({ row, table }) => {
      const anchor = table.getRow(row.original.branch.id);
      const isAnchor = isBranchAnchorRow(row.original);
      return (
        <BranchNameCell
          branch={row.original.branch}
          isSelected={anchor.getIsSelected()}
          onClickCheckbox={getToggleSelectedRowHandler({ row: anchor, table })}
          repositoryName={isAnchor ? undefined : row.original.repository?.name}
          excludeFromTabOrder={!isAnchor}
        />
      );
    },
  });
}

function getBranchRepositoryColumns(): Array<ColumnDef<BranchTableRow>> {
  return [
    columnHelper.display({
      id: "repository",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.repository} />,
      cell: ({ row }) => <BranchRepositoryCell row={row.original} />,
    }),
    columnHelper.display({
      id: "git_state",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.git_state} />,
      cell: ({ row }) => <BranchGitStateCell row={row.original} />,
    }),
    columnHelper.display({
      id: "commit",
      header: () => <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.commit} />,
      cell: ({ row }) => <BranchCommitCell row={row.original} />,
    }),
  ];
}

export function getBranchFieldsColumns(): Array<ColumnDef<BranchTableRow>> {
  return [
    columnHelper.accessor((r) => r.branch.status, {
      id: "status",
      header: () => <BranchStatusHeader />,
      cell: ({ cell }) => <BranchStatusCell status={cell.getValue()} />,
    }) as ColumnDef<BranchTableRow>,
    columnHelper.display({
      id: "proposed_changes",
      size: 250,
      minSize: 250,
      header: () => (
        <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.proposed_changes} />
      ),
      cell: ({ row }) => (
        <BranchProposedChangesCell
          branchName={row.original.branch.name}
          excludeFromTabOrder={!isBranchAnchorRow(row.original)}
        />
      ),
    }),
    ...getBranchRepositoryColumns(),
    columnHelper.accessor((r) => r.branch.branched_from, {
      id: "branched_from",
      header: () => <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.branched_from} />,
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }) as ColumnDef<BranchTableRow>,
    columnHelper.accessor((r) => r.branch.updated_at, {
      id: "updated_at",
      header: () => (
        <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.node_metadata__updated_at} />
      ),
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }) as ColumnDef<BranchTableRow>,
    columnHelper.accessor((r) => r.branch.created_at, {
      id: "created_at",
      header: () => (
        <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.node_metadata__created_at} />
      ),
      cell: ({ cell }) => <BranchDateCell date={cell.getValue()} />,
    }) as ColumnDef<BranchTableRow>,
    columnHelper.accessor((r) => r.branch.created_by, {
      id: "created_by",
      header: () => (
        <TableColumnHeader columnSchema={BRANCH_FIELD_SCHEMAS.node_metadata__created_by} />
      ),
      cell: ({ cell }) => <BranchCreatedByCell createdBy={cell.getValue()} />,
    }) as ColumnDef<BranchTableRow>,
  ];
}

export function getBranchActionsColumn(): ColumnDef<BranchTableRow> {
  return columnHelper.display({
    id: "actions",
    header: () => <ActionsHeaderCell />,
    cell: ({ row }) => (
      <BranchActionsCell
        branch={row.original.branch}
        excludeFromTabOrder={!isBranchAnchorRow(row.original)}
      />
    ),
  });
}

export function getBranchTableColumns(): Array<ColumnDef<BranchTableRow>> {
  return [
    getBranchIdentifierColumn() as ColumnDef<BranchTableRow>,
    ...getBranchFieldsColumns(),
    getBranchActionsColumn(),
  ];
}
