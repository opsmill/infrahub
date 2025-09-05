import React from "react";

import { Checkbox } from "@/shared/components/aria/checkbox";
import { Skeleton } from "@/shared/components/skeleton";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

export interface ObjectsTableSkeletonProps {
  headerCount: number;
}

export function ObjectTableSkeleton({ headerCount }: ObjectsTableSkeletonProps) {
  return [...Array(20)].map((_, rowIndex) => {
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
