import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { DateDisplay } from "@/shared/components/display/date-display";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import type { RepositoryCommit } from "@/entities/repository/domain/model/repository";
import { getCommitWebUrl } from "@/entities/repository/domain/rules/get-commit-web-url";
import { RepositoryCommitRowActions } from "@/entities/repository/ui/repository-commit-row-actions";
import { RepositoryCommitStateBadges } from "@/entities/repository/ui/repository-commit-state-badges";

const columnHelper = createColumnHelper<RepositoryCommit>();

function ColumnHeader({ children }: { children: string }) {
  return <div className={classNames(cellsStyle, cellHeaderStyle)}>{children}</div>;
}

export function getRepositoryCommitsColumns({
  importedCommit,
  repositoryLocation,
}: {
  importedCommit: string | null;
  repositoryLocation: string | null;
}): Array<ColumnDef<RepositoryCommit>> {
  return [
    columnHelper.accessor("short_hash", {
      header: () => <ColumnHeader>Hash</ColumnHeader>,
      cell: ({ cell }) => (
        <TableCell>
          <code className="font-mono text-xs">{cell.getValue()}</code>
        </TableCell>
      ),
    }),
    columnHelper.accessor("summary", {
      header: () => <ColumnHeader>Summary</ColumnHeader>,
      cell: ({ cell }) => (
        <TableCell>
          <span className="truncate" title={cell.getValue()}>
            {cell.getValue()}
          </span>
        </TableCell>
      ),
    }),
    columnHelper.accessor("author_name", {
      header: () => <ColumnHeader>Author</ColumnHeader>,
      cell: ({ cell }) => (
        <TableCell>
          <span className="truncate" title={cell.getValue()}>
            {cell.getValue()}
          </span>
        </TableCell>
      ),
    }),
    columnHelper.accessor("authored_at", {
      header: () => <ColumnHeader>Date</ColumnHeader>,
      cell: ({ cell }) => (
        <TableCell>
          <DateDisplay date={cell.getValue()} className="text-sm" />
        </TableCell>
      ),
    }),
    columnHelper.display({
      id: "state",
      header: () => <ColumnHeader>State</ColumnHeader>,
      cell: ({ row }) => (
        <TableCell>
          <RepositoryCommitStateBadges commit={row.original} importedCommit={importedCommit} />
        </TableCell>
      ),
    }),
    columnHelper.display({
      id: "actions",
      header: () => <ActionsHeaderCell />,
      cell: ({ row }) => (
        <RepositoryCommitRowActions
          commit={row.original}
          webUrl={
            repositoryLocation ? getCommitWebUrl(repositoryLocation, row.original.hash) : null
          }
        />
      ),
    }),
  ] as Array<ColumnDef<RepositoryCommit>>;
}
