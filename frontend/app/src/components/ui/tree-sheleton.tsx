import { Skeleton } from "@/components/skeleton";
import { classNames } from "@/utils/common";

export const TreeSkeleton = ({ className }: { className?: string }) => {
  return (
    <div className={classNames("space-y-2 w-full", className)}>
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
