import { Spinner } from "@infrahub/ui";

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

  if (row.state !== "ok") {
    return <TableCell className="h-auto min-h-14" />;
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
