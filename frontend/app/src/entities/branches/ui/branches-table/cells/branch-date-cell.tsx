import { DateDisplay } from "@/shared/components/display/date-display";
import { TableCell } from "@/shared/components/table/table-cell";

interface BranchDateCellProps {
  date?: string | null;
}

export function BranchDateCell({ date }: BranchDateCellProps) {
  return (
    <TableCell className="h-auto min-h-14">
      {date ? <DateDisplay date={date} hideDefault /> : <span className="text-gray-400">-</span>}
    </TableCell>
  );
}
