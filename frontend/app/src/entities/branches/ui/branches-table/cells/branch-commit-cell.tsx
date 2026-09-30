import { CommitHash } from "@/shared/components/display/commit-hash";
import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchTableRow } from "@/entities/branches/domain/model/branch-table-row";

interface BranchCommitCellProps {
  row: BranchTableRow;
}

export function BranchCommitCell({ row }: BranchCommitCellProps) {
  if (row.state !== "ok" || row.repository.commit === null) {
    return <TableCell className="h-auto min-h-14" />;
  }

  return (
    <TableCell className="h-auto min-h-14">
      <CommitHash hash={row.repository.commit} copyable />
    </TableCell>
  );
}
