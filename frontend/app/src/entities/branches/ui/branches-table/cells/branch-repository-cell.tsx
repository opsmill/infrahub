import { Spinner, Tooltip } from "@infrahub/ui";

import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchTableRow } from "@/entities/branches/domain/model/branch-table-row";
import { RepositoryNameLink } from "@/entities/repository/ui/branch-repositories/repository-name-link";

interface BranchRepositoryCellProps {
  row: BranchTableRow;
}

export function BranchRepositoryCell({ row }: BranchRepositoryCellProps) {
  return (
    <TableCell className="h-auto min-h-14">
      <BranchRepositoryCellContent row={row} />
    </TableCell>
  );
}

function BranchRepositoryCellContent({ row }: BranchRepositoryCellProps) {
  switch (row.state) {
    case "pending":
      return <Spinner />;
    case "error":
      return (
        <>
          <Tooltip message={row.errorMessage} nonInteractiveTrigger>
            <span className="text-foreground-muted">Could not load repositories</span>
          </Tooltip>
          <span className="sr-only">{row.errorMessage}</span>
        </>
      );
    case "denied":
      return <span className="text-foreground-muted">No permission</span>;
    case "empty":
      return (
        <span className="text-foreground-muted">
          {row.branch.sync_with_git ? "No repositories" : "Not synced with Git"}
        </span>
      );
    case "ok":
      return (
        <RepositoryNameLink
          repository={row.repository}
          branchName={row.branch.name}
          isDefaultBranch={Boolean(row.branch.is_default)}
        />
      );
  }
}
