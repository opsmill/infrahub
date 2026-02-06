import { useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Col, Row } from "@/shared/components/container";
import { DateDisplay } from "@/shared/components/display/date-display";
import { InlineDisplay } from "@/shared/components/display/inline-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Table, type tColumn } from "@/shared/components/table/table";
import { Id } from "@/shared/components/ui/id";
import { Link } from "@/shared/components/ui/link";
import { Pagination } from "@/shared/components/ui/pagination";
import { SEARCH_ANY_FILTER, TASK_TAB } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";
import useFilters from "@/shared/hooks/useFilters";

import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { RefreshButton } from "@/entities/nodes/object/ui/object-details/refresh-button";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { tasksQueryKeys } from "@/entities/tasks/domain/tasks.query-keys";
import { useGetTaskCount } from "@/entities/tasks/domain/get-node-task-count/get-task-count.query";
import { useGetTaskList } from "@/entities/tasks/domain/get-task-list/get-task-list.query";
import { TaskFilters } from "@/entities/tasks/ui/task-filters";
import { getStateBadge } from "@/entities/tasks/ui/task-item-details";

interface TaskItemsProps {
  relatedNodeId?: string;
}

export function TaskItems({ relatedNodeId }: TaskItemsProps) {
  const location = useLocation();
  const [filters] = useFilters();

  const search = filters.find((filter) => filter.name === SEARCH_ANY_FILTER)?.value;
  const branchName = filters.find((filter) => filter.name === "branch__value")?.value;
  const state = filters.find((filter) => filter.name === "state__value")?.value;
  const node = filters.find((filter) => filter.name === "node__value")?.value;

  const { pathname } = location;

  const relatedNode = relatedNodeId || node;

  const {
    data: count,
    isPending: isPendingCount,
    error: errorCount,
  } = useGetTaskCount({
    search,
    branchName,
    state,
    relatedNodeIds: relatedNode ? [relatedNode] : undefined,
  });

  const {
    data,
    error,
    isPending: loading,
  } = useGetTaskList({
    search,
    branchName,
    state,
    relatedNodeIds: relatedNode ? [relatedNode] : undefined,
  });

  if (isPendingCount) {
    return <LoadingIndicator className="h-full p-4" />;
  }

  if (error || errorCount) {
    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  const columns = [
    {
      name: "title",
      label: "Title",
    },
    {
      name: "branch",
      label: "Branch",
    },
    {
      name: "state",
      label: "State",
    },
    !relatedNodeId && {
      name: "related_nodes",
      label: "Related nodes",
    },
    {
      name: "progress",
      label: "Progress",
    },
    {
      name: "workflow",
      label: "Workflow",
    },
    {
      name: "updated_at",
      label: "Updated at",
    },
  ].filter((v): v is tColumn => !!v);

  const getUrl = (id: string) => {
    if (!relatedNodeId) {
      return constructPath(`/tasks/${id}`);
    }

    return constructPath(pathname, [
      { name: QSP.TAB, value: TASK_TAB },
      { name: QSP.TASK_ID, value: id },
    ]);
  };

  const rows = data?.map((task) => {
    return {
      link: getUrl(task.id),
      values: {
        title: {
          display: task.title,
        },
        branch: {
          display: task.branch,
        },
        state: {
          display: getStateBadge[task.state!],
        },
        related_nodes: {
          display: (
            <InlineDisplay
              items={task.related_nodes?.filter((n) => !!n) ?? []}
              render={(item) => {
                if (typeof item === "string") return null;

                if (!item.id) return null;

                return (
                  <Link
                    key={item.id}
                    to={getObjectDetailsUrl(item.kind!, item.id, [
                      { name: QSP.BRANCH, value: task.branch },
                    ])}
                  >
                    <Id
                      id={item.id}
                      kind={item.kind}
                      branch={task.branch}
                      date={new Date(task.updated_at)}
                      preventCopy
                    />
                  </Link>
                );
              }}
            />
          ),
        },
        progress: {
          display: task.progress,
        },
        workflow: {
          display: task.workflow,
        },
        updated_at: {
          display: <DateDisplay date={task.updated_at} />,
        },
      },
    };
  });

  return (
    <Col className="gap-0">
      <Row className="p-2">
        <RefreshButton className="rounded-md border-gray-300" queryKey={tasksQueryKeys.all} />
        <FilterSearchInput placeholder="Filter tasks..." />
        <TaskFilters />
      </Row>

      {loading && !rows && <LoadingIndicator className="p-4" />}

      {rows && (
        <div>
          <Table columns={columns} rows={rows} className="border-none" />

          <Pagination count={count} />
        </div>
      )}
    </Col>
  );
}
