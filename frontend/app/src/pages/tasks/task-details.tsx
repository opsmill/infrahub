import { Link } from "@/components/ui/link";
import { TASK_OBJECT } from "@/config/constants";
import { getTaskItemDetailsTitle } from "@/graphql/queries/tasks/getTasksItemDetailsTitle";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { TaskItemDetails } from "@/screens/tasks/task-item-details";
import { constructPath } from "@/utils/fetch";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";

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
    return <LoadingScreen hideText />;
  }

  const taskData = data?.[TASK_OBJECT]?.edges?.[0]?.node;

  const title = (
    <div className="flex items-center gap-2">
      <div className="flex bg-custom-white text-sm font-normal">
        <Link to={constructPath("/tasks")} className="flex items-center p-2 ">
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
