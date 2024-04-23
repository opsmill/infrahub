import { Skeleton } from "../../../components/skeleton";
import React from "react";

export const IpamTreeSkeleton = () => {
  return (
    <div className="space-y-2 border rounded p-1.5">
      <Skeleton className="h-4 w-11/12" />
      <Skeleton className="h-4 w-8/12" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-10/12" />
      <Skeleton className="h-4 w-9/12" />
      <Skeleton className="h-4 w-11/12" />
      <Skeleton className="h-4 w-8/12" />
      <Skeleton className="h-4 w-8/12" />
      <Skeleton className="h-4 w-10/12" />
    </div>
  );
};
