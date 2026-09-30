import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { DateDisplay } from "@/shared/components/display/date-display";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { StickyRightCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import type { RepositoryCommit } from "@/entities/repository/domain/model/repository";
import { RepositoryCommitStateBadges } from "@/entities/repository/ui/repository-commit-state-badges";

const columnHelper = createColumnHelper<RepositoryCommit>();

function ColumnHeader({ children }: { children: string }) {
  return <div className={classNames(cellsStyle, cellHeaderStyle)}>{children}</div>;
}

export function getRepositoryCommitsColumns(
  importedCommit: string | null
): Array<ColumnDef<RepositoryCommit>> {
  return [
    columnHelper.accessor("shortHash", {
      header: () => <ColumnHeader>Hash</ColumnHeader>,
      cell: ({ cell }) => (
        <TableCell>
          <code className="font-mono">{cell.getValue()}</code>
        </TableCell>
      ),
    }),
    columnHelper.accessor("summary", {
      header: () => <ColumnHeader>Summary</ColumnHeader>,
      cell: ({ cell }) => (
        <TableCell>
          <span className="truncate">{cell.getValue()}</span>
        </TableCell>
      ),
    }),
    columnHelper.accessor("authorName", {
      header: () => <ColumnHeader>Author</ColumnHeader>,
      cell: ({ cell }) => (
        <TableCell>
          <span className="truncate">{cell.getValue()}</span>
        </TableCell>
      ),
    }),
    columnHelper.accessor("authoredAt", {
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
        <StickyRightCell>
          <CopyToClipboardButton
            data={row.original.hash}
            aria-label={`Copy full hash ${row.original.shortHash}`}
          />
        </StickyRightCell>
      ),
    }),
  ] as Array<ColumnDef<RepositoryCommit>>;
}
