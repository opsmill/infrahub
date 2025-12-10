import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router";

import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Link } from "@/shared/components/ui/link";
import { TASK_OBJECT } from "@/shared/config/constants";
import { useTitle } from "@/shared/hooks/useTitle";

import { getTaskItemDetailsTitle } from "@/entities/tasks/api/getTasksItemDetailsTitle";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";

const TaskDetailsPage = () => {
  useTitle("Task Details");
  const { task: taskId } = useParams();

  const query = gql(
    getTaskItemDetailsTitle({
      kind: TASK_OBJECT,
      id: taskId,
    })
  );
  const { loading, error, data, refetch } = useQuery(query);

  if (error) {
    return <ErrorScreen message="An error occurred while fetching task details." />;
  }

  if (loading) {
    return <LoadingIndicator className="h-full" />;
  }

  const taskData = data?.[TASK_OBJECT]?.edges?.[0]?.node;

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

  if (!taskData) {
    return <ErrorScreen message={`Task with ID ${taskId} not found.`} />;
  }

  return (
    <Content.Card>
      <Content.CardTitle title={title} isReloadLoading={loading} reload={() => refetch()} />

      <TaskItemDetails />
    </Content.Card>
  );
};

export const Component = TaskDetailsPage;
