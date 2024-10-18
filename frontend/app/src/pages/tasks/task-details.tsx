import { TASK_OBJECT } from "@/config/constants";
import { getTaskItemDetailsTitle } from "@/graphql/queries/tasks/getTasksItemDetailsTitle";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { gql } from "@apollo/client";
import { useParams } from "react-router-dom";
import { TaskItemDetails } from "../../screens/tasks/task-item-details";

const TaskDetailsPage = () => {
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

  const result = data ? (data[TASK_OBJECT] ?? {}) : {};

  const { edges = [] } = result;

  const object = edges[0].node;

  return (
    <Content.Card>
      <Content.CardTitle title={object.title} />

      <TaskItemDetails />
    </Content.Card>
  );
};

export function Component() {
  return <TaskDetailsPage />;
}
