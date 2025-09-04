import React from "react";

import { Skeleton } from "@/shared/components/skeleton";

export interface ProposedChangesTableSkeletonProps {
  headerCount: number;
}

export function ProposedChangesTableSkeleton({ headerCount }: ProposedChangesTableSkeletonProps) {
  return [...Array(5)].map((_, rowIndex) => {
    return (
      <React.Fragment key={`skeleton-row-${rowIndex}`}>
        {[...Array(headerCount)].map((_, colIndex) => {
          return (
            <div className="p-2 border-t border-gray-200" key={colIndex}>
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-2xl" />
              </div>
            </div>
          );
        })}
      </React.Fragment>
    );
  });
}
