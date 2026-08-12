import type { BranchStatus } from "@/shared/api/graphql/generated/types";
import { TableCell } from "@/shared/components/table/table-cell";

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
