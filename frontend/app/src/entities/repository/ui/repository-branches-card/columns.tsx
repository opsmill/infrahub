import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { CommitHash } from "@/shared/components/display/commit-hash";
import { COLUMN_MAX_WIDTH } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";

import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";
import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import type { RepositoryBranchStatusRow } from "@/entities/repository/domain/model/repository-branch-status";
import {
  BRANCH_ROW_FILTER_CONDITIONS,
  BRANCH_STATUS_FIELD_SCHEMA,
} from "@/entities/repository/ui/repository-branches-card/branch-row-fields";
import { BranchNameCell } from "@/entities/repository/ui/repository-branches-card/cells/branch-name-cell";
import { SyncStatusCell } from "@/entities/repository/ui/repository-branches-card/cells/sync-status-cell";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";

const columnHelper = createColumnHelper<RepositoryBranchStatusRow>();

// Declared once so the memoised grid style keeps a stable identity across renders.
export const branchesGridTemplateColumns = (columnCount: number) =>
  columnCount > 1 ? `repeat(${columnCount - 1}, fit-content(${COLUMN_MAX_WIDTH})) 1fr` : "1fr";

function findAttribute(schema: ModelSchema, name: string): AttributeSchema | undefined {
  return schema.attributes?.find((attribute) => attribute.name === name);
}

function getSyncStatusColumn(
  columnSchema: AttributeSchema
): ColumnDef<RepositoryBranchStatusRow, unknown> {
  // Disabled because nothing in this column's menu could be honoured: the query orders by branch
  // node metadata alone, and this card offers no sync-status filter.
  return columnHelper.display({
    id: "sync_status",
    header: () => <TableColumnHeader columnSchema={columnSchema} isDisabled role="columnheader" />,
    cell: ({ row }) => (
      <TableCell role="cell">
        {row.original.syncStatus && <SyncStatusCell syncStatus={row.original.syncStatus} />}
      </TableCell>
    ),
  });
}

function getCommitColumn(
  columnSchema: AttributeSchema
): ColumnDef<RepositoryBranchStatusRow, unknown> {
  // Disabled: the query can neither order nor filter by a commit.
  return columnHelper.display({
    id: "commit",
    header: () => <TableColumnHeader columnSchema={columnSchema} isDisabled role="columnheader" />,
    cell: ({ row }) => (
      <TableCell role="cell">
        {row.original.commit && <CommitHash hash={row.original.commit} />}
      </TableCell>
    ),
  });
}

function getRefColumn(
  columnSchema: AttributeSchema
): ColumnDef<RepositoryBranchStatusRow, unknown> {
  // Disabled: the query can neither order nor filter by a ref.
  return columnHelper.display({
    id: "ref",
    header: () => <TableColumnHeader columnSchema={columnSchema} isDisabled role="columnheader" />,
    cell: ({ row }) => (
      <TableCell role="cell">
        <span className="truncate">{row.original.ref}</span>
      </TableCell>
    ),
  });
}

export function getRepositoryBranchesColumns(
  schema: ModelSchema
): Array<ColumnDef<RepositoryBranchStatusRow, unknown>> {
  const syncStatus = findAttribute(schema, "sync_status");
  const commit = findAttribute(schema, "commit");
  const ref = findAttribute(schema, "ref");

  return [
    columnHelper.display({
      id: "name",
      header: () => (
        <TableColumnHeader
          columnSchema={BRANCH_FIELD_SCHEMAS.name}
          filterConditions={BRANCH_ROW_FILTER_CONDITIONS}
          role="columnheader"
        />
      ),
      cell: ({ row }) => (
        <BranchNameCell name={row.original.name} isDefault={row.original.isDefault} role="cell" />
      ),
    }),
    columnHelper.display({
      id: "status",
      header: () => (
        <TableColumnHeader
          columnSchema={BRANCH_STATUS_FIELD_SCHEMA}
          filterConditions={BRANCH_ROW_FILTER_CONDITIONS}
          role="columnheader"
        />
      ),
      cell: ({ row }) => (
        <TableCell role="cell">
          <BranchStatusBadge status={row.original.status} showOpen />
        </TableCell>
      ),
    }),
    ...(syncStatus ? [getSyncStatusColumn(syncStatus)] : []),
    ...(commit ? [getCommitColumn(commit)] : []),
    ...(ref ? [getRefColumn(ref)] : []),
  ];
}
