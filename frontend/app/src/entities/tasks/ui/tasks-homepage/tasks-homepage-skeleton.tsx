import { Skeleton } from "@/shared/components/skeleton";

export const TaskHomepageCardSkeleton = () => {
  return (
    <div className="flex w-full flex-col gap-2 rounded-lg border border-transparent bg-white p-2 text-xs shadow-sm">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
    </div>
  );
};
