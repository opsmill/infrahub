import { Checkbox } from "@infrahub/ui";

import { Skeleton } from "@/shared/components/loading/skeleton";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

export interface ObjectsTableSkeletonProps {
  headerCount: number;
  rowCount?: number;
  showSelection?: boolean;
  // Carries `role="row"` / `role="cell"`, which an ARIA table requires and a plain grid must not have.
  semantic?: boolean;
}

export function ObjectTableSkeleton({
  headerCount,
  rowCount = 20,
  showSelection = true,
  semantic = false,
}: ObjectsTableSkeletonProps) {
  return [...Array(rowCount)].map((_, rowIndex) => {
    return (
      // `contents` keeps the cells as direct grid items, so the wrapper costs no layout.
      <div
        className="contents"
        key={`skeleton-row-${rowIndex}`}
        role={semantic ? "row" : undefined}
      >
        {[...Array(headerCount)].map((_, colIndex) => {
          return (
            <TableCell
              key={`skeleton-${rowIndex}-${colIndex}`}
              className={classNames(colIndex === 0 && "sticky left-0 z-1 bg-table-cell-pinned")}
              role={semantic ? "cell" : undefined}
            >
              {colIndex === 0 && showSelection && <Checkbox isDisabled className={"mr-4"} />}
              <Skeleton className="h-4 w-full" />
            </TableCell>
          );
        })}
      </div>
    );
  });
}
