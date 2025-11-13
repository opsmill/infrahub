import type { ReactNode } from "react";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";
import { useGetTasksHomepage } from "@/entities/tasks/domain/get-tasks/get-tasks-homepage.query";
import { TaskHomepageItem } from "@/entities/tasks/ui/task-homepage-item";
import { TaskHomepageCardSkeleton } from "@/entities/tasks/ui/tasks-homepage-skeleton";

interface TaskHomepageStateProps {
  states: string[];
  children?: ReactNode;
}

export const TaskHomepageState = ({ states, children }: TaskHomepageStateProps) => {
  const { data, error, isPending } = useGetTasksHomepage({ states, limit: 5 });

  return (
    <>
      {children}

      {isPending && <TaskHomepageCardSkeleton />}

      {error && (
        <EmptyHomeCard
          title="An error occurred"
          subtitle={error.message}
          className="text-center text-gray-500"
        />
      )}

      {!data?.length && !error && !isPending && (
        <EmptyHomeCard
          title="No tasks"
          subtitle="Tasks will appear here after you start a migration or assign a workflow"
          className="text-center text-gray-400"
        />
      )}

      {data?.map((task) => {
        return <TaskHomepageItem key={task.id} {...task} />;
      })}
    </>
  );
};
