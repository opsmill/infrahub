import { Spinner, Tooltip } from "@infrahub/ui";

import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchTableRow } from "@/entities/branches/domain/model/branch-table-row";
import { RepositoryNameLink } from "@/entities/repository/ui/branch-repositories/repository-name-link";

interface BranchRepositoryCellProps {
  row: BranchTableRow;
}

export function BranchRepositoryCell({ row }: BranchRepositoryCellProps) {
  if (row.state === "pending") {
    return (
      <TableCell className="h-auto min-h-14">
        <Spinner />
      </TableCell>
    );
  }

  if (row.state === "error") {
    return (
      <TableCell className="h-auto min-h-14">
        <Tooltip message={row.errorMessage} nonInteractiveTrigger>
          <span className="text-subtle-muted">Could not load repositories</span>
        </Tooltip>
      </TableCell>
    );
  }

  if (row.state === "denied") {
    return (
      <TableCell className="h-auto min-h-14">
        <span className="text-subtle-muted">No permission</span>
      </TableCell>
    );
  }

  if (row.state !== "ok") {
    return (
      <TableCell className="h-auto min-h-14">
        <span className="text-subtle-muted">
          {row.branch.sync_with_git ? "No repositories" : "Not synced with Git"}
        </span>
      </TableCell>
    );
  }

  return (
    <TableCell className="h-auto min-h-14">
      <RepositoryNameLink
        repository={row.repository}
        branchName={row.branch.name}
        isDefaultBranch={Boolean(row.branch.is_default)}
      />
    </TableCell>
  );
}
