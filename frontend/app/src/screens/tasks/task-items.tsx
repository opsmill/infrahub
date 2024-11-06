import { Table, tColumn } from "@/components/table/table";
import { Pagination } from "@/components/ui/pagination";
import { TASK_OBJECT, TASK_TAB } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import { gql } from "@apollo/client";

import { DateDisplay } from "@/components/display/date-display";
import { Id } from "@/components/ui/id";
import { QSP } from "@/config/qsp";
import { getTasksItems } from "@/graphql/queries/tasks/getTasksItems";
import ErrorScreen from "@/screens/errors/error-screen";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { constructPath } from "@/utils/fetch";
import { forwardRef, useImperativeHandle } from "react";
import { useLocation, useParams } from "react-router-dom";
import { getStateBadge } from "./task-item-details";

interface TaskItemsProps {
  hideRelatedNode?: boolean;
}

export const TaskItems = forwardRef(({ hideRelatedNode }: TaskItemsProps, ref) => {
  const { objectid, proposedChangeId } = useParams();
  const location = useLocation();

  const { pathname } = location;

  const queryString = getTasksItems({
    kind: TASK_OBJECT,
    relatedNode: objectid || proposedChangeId,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data = {}, refetch } = useQuery(query);

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  if (loading) {
    return <LoadingScreen hideText />;
  }

  const result = data ? (data[TASK_OBJECT] ?? {}) : {};

  const { count, edges = [] } = result;

  const columns = [
    {
      name: "title",
      label: "Title",
    },
    {
      name: "state",
      label: "State",
    },
    !hideRelatedNode && {
      name: "related_node",
      label: "Related node",
    },
    {
      name: "progress",
      label: "Progress",
    },
    {
      name: "updated_at",
      label: "Updated at",
    },
  ].filter((v): v is tColumn => !!v);

  const getUrl = (id: string) => {
    if (!objectid && !proposedChangeId) {
      return constructPath(`/tasks/${id}`);
    }

    const url = constructPath(pathname, [
      { name: proposedChangeId ? QSP.PROPOSED_CHANGES_TAB : QSP.TAB, value: TASK_TAB },
      { name: QSP.TASK_ID, value: id },
    ]);

    return url;
  };

  const rows = edges.map((edge: any) => ({
    link: getUrl(edge.node.id),
    values: {
      title: {
        display: edge.node.title,
      },
      state: {
        display: getStateBadge[edge.node.state],
      },
      related_node: {
        display: edge.node.related_node_kind && (
          <Id id={edge.node.related_node} kind={edge.node.related_node_kind} preventCopy />
        ),
      },
      duration: {
        display: edge.node.progress,
      },
      updated_at: {
        display: <DateDisplay date={edge.node.updated_at} />,
      },
    },
  }));

  return (
    <div className="bg-custom-white flex-1 flex flex-col">
      {loading && !rows && <LoadingScreen />}

      {rows && (
        <div>
          <Table columns={columns} rows={rows} className="border-none" />

          <Pagination count={count} />
        </div>
      )}
    </div>
  );
});
