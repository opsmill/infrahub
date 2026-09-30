import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchTableRow } from "@/entities/branches/domain/model/branch-table-row";
import { GitStatePill } from "@/entities/repository/ui/branch-repositories/git-state-pill";

interface BranchGitStateCellProps {
  row: BranchTableRow;
}

export function BranchGitStateCell({ row }: BranchGitStateCellProps) {
  if (row.state !== "ok") {
    return <TableCell className="h-auto min-h-14" />;
  }

  return (
    <TableCell className="h-auto min-h-14">
      <GitStatePill syncStatus={row.repository.syncStatus} />
    </TableCell>
  );
}
