import { Badge } from "@/components/ui/badge";
import { TASK_OBJECT } from "@/config/constants";
import { getTasksItemsCount } from "@/graphql/queries/tasks/getTasksItemsCount";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { gql } from "@apollo/client";
import { TaskItems } from "./task-items";

const TaskItemsScreen = () => {
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

  const result = data ? data[TASK_OBJECT] ?? {} : {};

  const { count } = result;

  return (
    <Content className="bg-custom-white">
      <Content.Title
        title={
          <>
            Task Overview <Badge>{count}</Badge>
          </>
        }
      />

      <TaskItems />
    </Content>
  );
};

export default TaskItemsScreen;
