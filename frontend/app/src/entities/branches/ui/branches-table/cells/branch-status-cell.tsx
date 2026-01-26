import { CheckCircleIcon } from "lucide-react";

import { TableCell } from "@/shared/components/table/table-cell";
import { Badge } from "@/shared/components/ui/badge";

import type { BranchStatus } from "@/entities/branches/constants";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";

interface BranchStatusCellProps {
  status: BranchStatus;
}

export function BranchStatusCell({ status }: BranchStatusCellProps) {
  const badge = BranchStatusBadge({ status });

  return (
    <TableCell className="h-auto min-h-14">
      {badge ?? (
        <Badge className="gap-1 rounded-full font-normal" variant="green">
          <CheckCircleIcon className="size-3" /> Open
        </Badge>
      )}
    </TableCell>
  );
}
