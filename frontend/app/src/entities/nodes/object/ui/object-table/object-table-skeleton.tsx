import { Checkbox } from "@infrahub/ui";
import React from "react";

import { Skeleton } from "@/shared/components/loading/skeleton";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

export interface ObjectsTableSkeletonProps {
  headerCount: number;
  rowCount?: number;
  showSelection?: boolean;
}

export function ObjectTableSkeleton({
  headerCount,
  rowCount = 20,
  showSelection = true,
}: ObjectsTableSkeletonProps) {
  return [...Array(rowCount)].map((_, rowIndex) => {
    return (
      <React.Fragment key={`skeleton-row-${rowIndex}`}>
        {[...Array(headerCount)].map((_, colIndex) => {
          return (
            <TableCell
              key={`skeleton-${rowIndex}-${colIndex}`}
              className={classNames(colIndex === 0 && "sticky left-0 z-1 bg-table-cell-pinned")}
            >
              {colIndex === 0 && showSelection && <Checkbox isDisabled className={"mr-4"} />}
              <Skeleton className="h-4 w-full" />
            </TableCell>
          );
        })}
      </React.Fragment>
    );
  });
}
