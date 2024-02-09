import { gql } from "@apollo/client";
import { Table } from "../../components/table/table";
import { Pagination } from "../../components/utils/pagination";
import { TASK_OBJECT } from "../../config/constants";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";

import { DateDisplay } from "../../components/display/date-display";
import { Id } from "../../components/utils/id";
import { getTasksItems } from "../../graphql/queries/tasks/getTasksItems";
import { constructPath } from "../../utils/fetch";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { getConclusionBadge } from "./task-item-details";

export const TaskItems = () => {
  useTitle("Task Overview");

  const queryString = getTasksItems({
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

  const { count, edges = [] } = result;

  const columns = [
    {
      name: "title",
      label: "Title",
    },
    {
      name: "conclusion",
      label: "Conclusion",
    },
    {
      name: "related_node",
      label: "Related node",
    },
    {
      name: "duration",
      label: "Duration",
    },
    {
      name: "updated_at",
      label: "Updated at",
    },
  ];

  const rows = edges.map((edge: any) => ({
    link: constructPath(`/tasks/${edge.node.id}`),
    values: {
      title: edge.node.title,
      conclusion: getConclusionBadge[edge.node.conclusion],
      related_node: (
        <Id id={edge.node.related_node} kind={edge.node.related_node_kind} preventCopy />
      ),
      duration: <DateDisplay date={edge.node.created_at} endDate={edge.node.updated_at} />,
      updated_at: <DateDisplay date={edge.node.updated_at} />,
    },
  }));

  return (
    <div className="bg-custom-white flex-1 flex flex-col">
      <div className="flex items-center p-4 w-full">
        <div className="sm:flex-auto flex items-center">
          <h1 className="text-md font-semibold text-gray-900 mr-2">Task Overview ({count})</h1>

          <div className="text-sm"></div>
        </div>
      </div>

      {loading && !rows && <LoadingScreen />}

      {rows && (
        <div>
          <Table columns={columns} rows={rows} />

          <Pagination count={count} />
        </div>
      )}
    </div>
  );
};
