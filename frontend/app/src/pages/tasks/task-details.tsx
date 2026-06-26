import { Icon } from "@iconify-icon/react";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Link } from "@/shared/components/ui/link";
import { useRequiredParams } from "@/shared/hooks/use-required-params";
import { useTitle } from "@/shared/hooks/useTitle";

import { useGetTaskDetailsTitle } from "@/entities/tasks/ui/queries/get-task-details-title.query";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

const TaskDetailsPage = () => {
  useTitle("Task Details");
  const { taskId } = useRequiredParams("taskId");

  const {
    isLoading,
    isFetching,
    error,
    data: taskData,
    refetch,
  } = useGetTaskDetailsTitle({ ids: [taskId] });

  if (error) {
    return <ErrorScreen message="An error occurred while fetching task details." />;
  }

  if (isLoading) {
    return <LoadingIndicator className="h-full" />;
  }

  if (!taskData) {
    return <ErrorScreen message={`Task with ID ${taskId} not found.`} />;
  }

  const title = (
    <div className="flex items-center gap-2">
      <div className="flex bg-white font-normal text-sm">
        <Link to={constructPath("/tasks")} className="flex items-center p-2">
          <Icon icon={"mdi:chevron-left"} />
          All tasks
        </Link>
      </div>
      {taskData.title}
    </div>
  );

  return (
    <Content.Card>
      <Content.CardTitle title={title} isReloadLoading={isFetching} reload={() => refetch()} />

      <TaskItemDetails />
    </Content.Card>
  );
};

export const Component = TaskDetailsPage;
