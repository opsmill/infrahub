import { TableCell } from "@/shared/components/table/table-cell";

import type { BranchStatus } from "@/entities/branches/constants";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";

interface BranchStatusCellProps {
  status: BranchStatus;
}

export function BranchStatusCell({ status }: BranchStatusCellProps) {
  return (
    <TableCell className="h-auto min-h-14">
      <BranchStatusBadge status={status} showOpen />
    </TableCell>
  );
}
