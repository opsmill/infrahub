import { Skeleton } from "@/shared/components/skeleton";
import React from "react";

export interface ProposedCHangesTableSkeletonProps {
  headerCount: number;
}

export function ProposedCHangesTableSkeleton({ headerCount }: ProposedCHangesTableSkeletonProps) {
  return [...Array(20)].map((_, rowIndex) => {
    return (
      <React.Fragment key={`skeleton-row-${rowIndex}`}>
        {[...Array(headerCount)].map((_, colIndex) => {
          return (
            <div className="p-2 border border-gray-200" key={colIndex}>
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
