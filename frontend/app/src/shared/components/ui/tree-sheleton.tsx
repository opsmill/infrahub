import { Skeleton } from "@/shared/components/loading/skeleton";
import { classNames } from "@/shared/utils/common";

export const TreeSkeleton = ({ className }: { className?: string }) => {
  return (
    <div className={classNames("w-full space-y-2", className)}>
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
