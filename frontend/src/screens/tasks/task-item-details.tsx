import { gql } from "@apollo/client";
import { TASK_OBJECT } from "../../config/constants";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";

import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { BADGE_TYPES, Badge } from "../../components/display/badge";
import { DateDisplay } from "../../components/display/date-display";
import { SearchInput } from "../../components/search/search-bar";
import { List } from "../../components/table/list";
import { Id } from "../../components/utils/id";
import { Link } from "../../components/utils/link";
import { getTaskItemDetails } from "../../graphql/queries/tasks/getTasksItemDetails";
import { constructPath } from "../../utils/fetch";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { Logs, tLog } from "./logs";

export const getConclusionBadge: { [key: string]: any } = {
  success: <Badge type={BADGE_TYPES.VALIDATE}>success</Badge>,
  unknown: <Badge type={BADGE_TYPES.LIGHT}>unknown</Badge>,
  failure: <Badge type={BADGE_TYPES.CANCEL}>failure</Badge>,
};

export const TaskItemDetails = () => {
  useTitle("Task details");

  const [search, setSearch] = useState("");

  const { task } = useParams();

  const queryString = getTaskItemDetails({
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

  const columns = [
    {
      name: "id",
      label: "ID",
    },
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

  const object = edges[0].node;

  const row = {
    values: {
      id: object.id,
      title: object.title,
      conclusion: getConclusionBadge[object.conclusion],
      related_node: <Id id={object.related_node} kind={object.related_node_kind} preventCopy />,
      related_node_kind: object.related_node_kind,
      duration: <DateDisplay date={object.created_at} endDate={object.updated_at} />,
      updated_at: <DateDisplay date={object.updated_at} />,
    },
  };

  const logs = object.logs.edges
    .map((edge: any) => edge.node)
    .filter((log: tLog) => {
      if (!search) return true;

      return (
        log.message?.includes(search) || log.severity?.includes(search) || log.id?.includes(search)
      );
    });

  // const count = object.logs.count;
  const count = logs.length;

  return (
    <div className=" flex-1 flex flex-col">
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

        {loading && !result && <LoadingScreen />}

        <List columns={columns} row={row} />
      </div>

      <div className="rounded-md overflow-hidden bg-custom-white m-4 p-2">
        <div className="flex mb-2">
          <h2 className="flex-1 font-semibold text-gray-900 m-2 ml-0">Task Logs ({count})</h2>

          <div className="flex flex-1 justify-end">
            <SearchInput onChange={setSearch} placeholder="Search logs from title or message" />
          </div>
        </div>

        <Logs logs={logs} />
      </div>
    </div>
  );
};
