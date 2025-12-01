import { useQueryState } from "nuqs";
import { forwardRef, useImperativeHandle, useState } from "react";
import { useParams } from "react-router";

import useQuery from "@/shared/api/graphql/useQuery";
import { DateDisplay } from "@/shared/components/display/date-display";
import { InlineDisplay } from "@/shared/components/display/inline-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { List } from "@/shared/components/table/list";
import { Badge } from "@/shared/components/ui/badge";
import { Id } from "@/shared/components/ui/id";
import { Link } from "@/shared/components/ui/link";
import { SearchInput } from "@/shared/components/ui/search-input";
import { TASK_OBJECT } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { TASK_DETAILS } from "@/entities/tasks/api/getTasksItemDetails";

import { Logs, type tLog } from "./logs";

export const getStateBadge: { [key: string]: any } = {
  SCHEDULED: <Badge variant={"blue"}>SCHEDULED</Badge>,
  PENDING: <Badge variant={"blue-outline"}>PENDING</Badge>,
  RUNNING: <Badge variant={"green-outline"}>RUNNING</Badge>,
  COMPLETED: <Badge variant={"green"}>COMPLETED</Badge>,
  FAILED: <Badge variant={"red"}>FAILED</Badge>,
  CANCELLED: <Badge variant={"red-outline"}>CANCELLED</Badge>,
  CRASHED: <Badge variant={"yellow"}>CRASHED</Badge>,
  PAUSED: <Badge variant={"blue-outline"}>PAUSED</Badge>,
  CANCELLING: <Badge variant={"gray"}>CANCELLING</Badge>,
};

export const TaskItemDetails = forwardRef((_, ref) => {
  const [idFromQsp] = useQueryState(QSP.TASK_ID);
  const [search, setSearch] = useState("");

  const { task: idFromParams } = useParams();

  const ids = idFromParams || idFromQsp ? [idFromParams || idFromQsp] : undefined;

  const { loading, error, data = {}, refetch } = useQuery(TASK_DETAILS, { variables: { ids } });

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  if (loading) {
    return <LoadingIndicator message="Loading task..." className="h-[400px]" />;
  }

  const result = data ? (data[TASK_OBJECT] ?? {}) : {};

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
      name: "state",
      label: "State",
    },
    {
      name: "related_nodes",
      label: "Related nodes",
    },
    {
      name: "progress",
      label: "Progress",
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
      state: getStateBadge[object.state],
      related_nodes: (
        <InlineDisplay
          items={object.related_nodes}
          render={(item) => {
            if (typeof item === "string") return null;

            if (!item.id) return null;

            return (
              <Link
                key={item.id}
                to={getObjectDetailsUrl(item.kind, item.id, [
                  { name: QSP.BRANCH, value: object.branch },
                ])}
              >
                <Id id={item.id} kind={item.kind} preventCopy />
              </Link>
            );
          }}
        />
      ),
      progress: object.progress,
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

  const count = logs.length;

  return (
    <div className="flex flex-1 flex-col">
      <div className="bg-white">
        <List columns={columns} row={row} />
      </div>

      <div className="m-4 overflow-hidden rounded-md bg-white p-2">
        <div className="mb-2 flex">
          <h2 className="m-2 ml-0 flex-1 font-semibold text-gray-900">Task Logs ({count})</h2>

          <div className="flex flex-1 justify-end">
            <SearchInput
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search logs from message or severity"
              className="min-w-96"
            />
          </div>
        </div>

        <Logs logs={logs} />
      </div>
    </div>
  );
});
