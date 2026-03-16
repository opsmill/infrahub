import { TableCell } from "@/shared/components/table/table-cell";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";

interface BranchCreatedByCellProps {
  createdBy?: NodeCore | null;
}

export function BranchCreatedByCell({ createdBy }: BranchCreatedByCellProps) {
  return (
    <TableCell className="h-auto min-h-14">
      {createdBy ? (
        <span className="truncate">{getNodeLabel(createdBy)}</span>
      ) : (
        <span className="text-gray-400">-</span>
      )}
    </TableCell>
  );
}
