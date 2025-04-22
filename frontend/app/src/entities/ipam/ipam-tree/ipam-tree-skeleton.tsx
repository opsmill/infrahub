import { Skeleton } from "@/shared/components/skeleton";

export const IpamTreeSkeleton = () => {
  return (
    <div className="space-y-2 border border-gray-200 rounded-sm p-1.5">
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
