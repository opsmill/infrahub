import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { CommitHash } from "@/shared/components/display/commit-hash";
import { COLUMN_MAX_WIDTH } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";

import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { DropdownCell } from "@/entities/nodes/object/ui/object-table/cells/dropdown-cell";
import { TableColumnHeaderSimple } from "@/entities/nodes/object/ui/object-table/cells/table-column-header-simple";
import type { RepositoryBranchStatusRow } from "@/entities/repository/domain/model/repository-branch-status";
import { BranchNameCell } from "@/entities/repository/ui/repository-branches-card/cells/branch-name-cell";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";

const columnHelper = createColumnHelper<RepositoryBranchStatusRow>();

// Declared once so the table's memoised grid style keeps a stable identity; the default tracks
// reserve a trailing row-action column this card does not have.
export const branchesGridTemplateColumns = (columnCount: number) =>
  `repeat(${columnCount - 1}, fit-content(${COLUMN_MAX_WIDTH})) 1fr`;

function findAttribute(schema: ModelSchema, name: string): AttributeSchema | undefined {
  return schema.attributes?.find((attribute) => attribute.name === name);
}

function getSyncStatusColumn(
  columnSchema: AttributeSchema
): ColumnDef<RepositoryBranchStatusRow, unknown> {
  return columnHelper.display({
    id: "sync_status",
    header: () => <TableColumnHeaderSimple columnSchema={columnSchema} role="columnheader" />,
    cell: ({ row }) => (
      <TableCell role="cell">
        {row.original.syncStatus && <DropdownCell dropdown={row.original.syncStatus} />}
      </TableCell>
    ),
  });
}

function getCommitColumn(
  columnSchema: AttributeSchema
): ColumnDef<RepositoryBranchStatusRow, unknown> {
  return columnHelper.display({
    id: "commit",
    header: () => <TableColumnHeaderSimple columnSchema={columnSchema} role="columnheader" />,
    cell: ({ row }) => (
      <TableCell role="cell">
        {row.original.commit && <CommitHash hash={row.original.commit} copyable={false} />}
      </TableCell>
    ),
  });
}

function getRefColumn(
  columnSchema: AttributeSchema
): ColumnDef<RepositoryBranchStatusRow, unknown> {
  return columnHelper.display({
    id: "ref",
    header: () => <TableColumnHeaderSimple columnSchema={columnSchema} role="columnheader" />,
    cell: ({ row }) => (
      <TableCell role="cell">
        <span className="truncate">{row.original.ref}</span>
      </TableCell>
    ),
  });
}

// Each column exists only where the viewed kind declares its attribute, which is what keeps `ref`
// off the read-write repository without a kind list.
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
        <TableColumnHeaderSimple columnSchema={BRANCH_FIELD_SCHEMAS.name} role="columnheader" />
      ),
      cell: ({ row }) => (
        <BranchNameCell name={row.original.name} isDefault={row.original.isDefault} role="cell" />
      ),
    }),
    ...(syncStatus ? [getSyncStatusColumn(syncStatus)] : []),
    ...(commit ? [getCommitColumn(commit)] : []),
    ...(ref ? [getRefColumn(ref)] : []),
  ];
}
