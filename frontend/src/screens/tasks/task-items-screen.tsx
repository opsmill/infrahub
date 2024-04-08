import { gql } from "@apollo/client";
import { TASK_OBJECT } from "../../config/constants";
import { getTasksItemsCount } from "../../graphql/queries/tasks/getTasksItemsCount";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { TaskItems } from "./task-items";
import Content from "../layout/content";
import { Badge } from "../../components/ui/badge";

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
