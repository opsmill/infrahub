import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";
import { useGetTasksHomepage } from "@/entities/tasks/domain/get-tasks/get-tasks-homepage.query";
import { TaskHomepageItem } from "@/entities/tasks/ui/tasks-homepage/task-homepage-item";
import { TaskHomepageCardSkeleton } from "@/entities/tasks/ui/tasks-homepage/tasks-homepage-skeleton";

interface TaskHomepageStateProps {
  states: string[];
}

export const TaskHomepageState = ({ states }: TaskHomepageStateProps) => {
  const { data, error, isPending } = useGetTasksHomepage({ states, limit: 5 });

  if (isPending) {
    return (
      <>
        <TaskHomepageCardSkeleton />
        <TaskHomepageCardSkeleton />
        <TaskHomepageCardSkeleton />
        <TaskHomepageCardSkeleton />
        <TaskHomepageCardSkeleton />
      </>
    );
  }

  if (error) {
    return (
      <EmptyHomeCard
        title="An error occurred"
        subtitle={error.message}
        className="w-full text-center text-gray-500"
      />
    );
  }

  if (!data.length) {
    return (
      <EmptyHomeCard
        title="No tasks"
        subtitle="Tasks will appear here after you start a migration or assign a workflow"
        className="w-full text-center text-gray-400"
      />
    );
  }

  return data.map((task) => {
    return <TaskHomepageItem key={task.id} {...task} />;
  });
};
