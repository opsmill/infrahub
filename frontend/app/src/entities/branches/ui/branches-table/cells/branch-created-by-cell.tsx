import { TableCell } from "@/shared/components/table/table-cell";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";

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
