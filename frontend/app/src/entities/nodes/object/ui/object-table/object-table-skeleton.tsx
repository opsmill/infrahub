import React from "react";

import { Checkbox } from "@/shared/components/aria/checkbox";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

export interface ObjectsTableSkeletonProps {
  headerCount: number;
  rowCount?: number;
}

export function ObjectTableSkeleton({ headerCount, rowCount = 20 }: ObjectsTableSkeletonProps) {
  return [...Array(rowCount)].map((_, rowIndex) => {
    return (
      <React.Fragment key={`skeleton-row-${rowIndex}`}>
        {[...Array(headerCount)].map((_, colIndex) => {
          return (
            <TableCell
              key={`skeleton-${rowIndex}-${colIndex}`}
              className={classNames(colIndex === 0 && "sticky left-0 z-1 bg-white")}
            >
              {colIndex === 0 && <Checkbox isDisabled className={"mr-4"} />}
              <Skeleton className="h-4 w-full" />
            </TableCell>
          );
        })}
      </React.Fragment>
    );
  });
}
