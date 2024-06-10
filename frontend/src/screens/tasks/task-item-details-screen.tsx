import { TASK_OBJECT } from "@/config/constants";
import { gql } from "@apollo/client";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";

import { Link } from "@/components/ui/link";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { getTaskItemDetailsTitle } from "../../graphql/queries/tasks/getTasksItemDetailsTitle";
import ErrorScreen from "../errors/error-screen";
import Content from "../layout/content";
import LoadingScreen from "../loading-screen/loading-screen";
import { TaskItemDetails } from "./task-item-details";

const TaskItemDetailsScreen = () => {
  useTitle("Task details");

  const { task } = useParams();

  const queryString = getTaskItemDetailsTitle({
    kind: TASK_OBJECT,
    id: task,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data = {} } = useQuery(query);

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  if (loading) {
    return <LoadingScreen hideText />;
  }

  const result = data ? data[TASK_OBJECT] ?? {} : {};

  const { edges = [] } = result;

  const object = edges[0].node;

  return (
    <Content>
      <Content.Title
        title={
          <div className="flex items-center gap-1">
            <Link to={constructPath("/tasks")}>Task Details</Link>

            <Icon icon="mdi:chevron-right" className="text-2xl shrink-0 text-gray-400" />

            <p className="max-w-2xl text-gray-500 font-normal">{object.title}</p>
          </div>
        }
      />

      <TaskItemDetails />
    </Content>
  );
};

export default TaskItemDetailsScreen;
