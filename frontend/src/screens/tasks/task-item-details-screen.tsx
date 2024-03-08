import { gql } from "@apollo/client";
import { TASK_OBJECT } from "../../config/constants";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";

import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { useParams } from "react-router-dom";
import { Link } from "../../components/utils/link";
import { getTaskItemDetailsTitle } from "../../graphql/queries/tasks/getTasksItemDetailsTitle";
import { constructPath } from "../../utils/fetch";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { TaskItemDetails } from "./task-item-details";
import Content from "../layout/content";

export const TaskItemDetailsScreen = () => {
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
      <div className="bg-custom-white">
        <div className="flex items-center p-4 w-full">
          <div className="sm:flex-auto flex items-center">
            <Link to={constructPath("/tasks")}>
              <h1 className="text-md font-semibold text-gray-900 mr-2">Task Details</h1>
            </Link>

            <ChevronRightIcon
              className="w-4 h-4 mt-1 mx-2 flex-shrink-0 text-gray-400"
              aria-hidden="true"
            />
            <p className="max-w-2xl  text-gray-500">{object.title}</p>
          </div>
        </div>
      </div>

      <TaskItemDetails />
    </Content>
  );
};
