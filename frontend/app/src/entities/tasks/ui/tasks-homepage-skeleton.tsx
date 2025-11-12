import { Skeleton } from "@/shared/components/skeleton";

import { TaskHomepageCard } from "@/entities/tasks/ui/task-homepage-card";

export const TaskHomepageCardSkeleton = () => {
  return (
    <TaskHomepageCard>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
    </TaskHomepageCard>
  );
};
