import { ScrollArea } from "@/shared/components/ui/scroll-area";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";
import { useGetTasksHomepage } from "@/entities/tasks/domain/get-tasks-homepage/get-tasks-homepage.query";
import { TaskHomepageItem } from "@/entities/tasks/ui/tasks-homepage/task-homepage-item";
import { TaskHomepageCardSkeleton } from "@/entities/tasks/ui/tasks-homepage/tasks-homepage-skeleton";

const TASK_LIMIT = 5;

interface TaskHomepageStateProps {
  states: string[];
  emptyTitle?: string;
  emptySubtitle?: string;
}

export const TaskHomepageState = ({
  states,
  emptyTitle = "No tasks",
  emptySubtitle = "Nothing to display",
}: TaskHomepageStateProps) => {
  const { data, error, isPending } = useGetTasksHomepage({ states, limit: TASK_LIMIT });

  if (isPending) {
    return Array.from({ length: TASK_LIMIT }, (_, i) => <TaskHomepageCardSkeleton key={i} />);
  }

  if (error) {
    return (
      <EmptyHomeCard
        title="An error occurred"
        subtitle={error.message}
        className="w-full text-center"
      />
    );
  }

  if (!data.length) {
    return (
      <EmptyHomeCard
        title={emptyTitle}
        subtitle={emptySubtitle}
        className="w-full text-center text-gray-400"
      />
    );
  }

  return (
    <ScrollArea className="h-full w-full">
      <div className="flex flex-col gap-1.5">
        {data.map((task) => {
          return <TaskHomepageItem key={task.id} {...task} />;
        })}
      </div>
    </ScrollArea>
  );
};
