import { TASK_OBJECT } from "@/config/constants";
import { getTasksItemsCount } from "@/graphql/queries/tasks/getTasksItemsCount";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { TaskItems } from "@/screens/tasks/task-items";
import { gql } from "@apollo/client";

const TasksPage = () => {
  useTitle("Task Overview");

  const queryString = getTasksItemsCount({
    kind: TASK_OBJECT,
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

  const { count } = result;

  return (
    <Content.Card>
      <Content.CardTitle title="Task Overview" badgeContent={count} />

      <TaskItems />
    </Content.Card>
  );
};

export function Component() {
  return <TasksPage />;
}
