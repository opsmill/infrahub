import type { ReactNode } from "react";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";
import { useGetTasks } from "@/entities/tasks/domain/get-tasks/get-tasks.query";
import { TaskHomepageCard } from "@/entities/tasks/ui/task-homepage-card";
import { TaskHomepageColumn } from "@/entities/tasks/ui/task-homepage-column";
import { TaskHomepageDetails } from "@/entities/tasks/ui/task-homepage-details";
import { TaskHomepageCardSkeleton } from "@/entities/tasks/ui/tasks-homepage-skeleton";

interface TaskHomepageStateProps {
  states: string[];
  children?: ReactNode;
}

export const TaskHomepageState = ({ states, children }: TaskHomepageStateProps) => {
  const { data, error, isPending } = useGetTasks({ states, limit: 5 });

  return (
    <TaskHomepageColumn>
      {children}

      {isPending && <TaskHomepageCardSkeleton />}

      {error && (
        <EmptyHomeCard
          title="An error occured"
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
        return (
          <TaskHomepageCard key={task.id}>
            <TaskHomepageDetails {...task} />
          </TaskHomepageCard>
        );
      })}
    </TaskHomepageColumn>
  );
};
