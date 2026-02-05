import { useLocation } from "react-router";

import useQuery from "@/shared/api/graphql/useQuery";
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
import { SEARCH_ANY_FILTER, TASK_OBJECT, TASK_TAB } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";
import useFilters from "@/shared/hooks/useFilters";

import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { GET_TASK_ITEMS } from "@/entities/tasks/api/getTasksItems";
import { TaskFilters } from "@/entities/tasks/ui/task-filters";

import { getStateBadge } from "./task-item-details";

interface TaskItemsProps {
  relatedNodeId?: string;
}

export function TaskItems({ relatedNodeId }: TaskItemsProps) {
  const location = useLocation();
  const [filters] = useFilters();

  const search = filters.find((filter) => filter.name === SEARCH_ANY_FILTER)?.value;
  const branch = filters.find((filter) => filter.name === "branch__value")?.value;
  const state = filters.find((filter) => filter.name === "state__value")?.value;
  const node = filters.find((filter) => filter.name === "node__value")?.value;

  const { pathname } = location;

  const relatedNode = relatedNodeId || node;

  const {
    loading,
    error,
    data = {},
  } = useQuery(GET_TASK_ITEMS, {
    variables: {
      search,
      branch,
      state,
      relatedNodes: relatedNode ? [relatedNode] : [],
    },
  });

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching list." />;
  }

  const result = data ? (data[TASK_OBJECT] ?? {}) : {};

  const { count, edges } = result;

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

  const rows = edges?.map((edge: any) => {
    return {
      link: getUrl(edge.node.id),
      values: {
        title: {
          display: edge.node.title,
        },
        branch: {
          display: edge.node.branch,
        },
        state: {
          display: getStateBadge[edge.node.state],
        },
        related_nodes: {
          display: (
            <InlineDisplay
              items={edge.node.related_nodes}
              render={(item) => {
                if (typeof item === "string") return null;

                if (!item.id) return null;

                return (
                  <Link
                    key={item.id}
                    to={getObjectDetailsUrl(item.kind, item.id, [
                      { name: QSP.BRANCH, value: edge.node.branch },
                    ])}
                  >
                    <Id id={item.id} kind={item.kind} preventCopy />
                  </Link>
                );
              }}
            />
          ),
        },
        progress: {
          display: edge.node.progress,
        },
        workflow: {
          display: edge.node.workflow,
        },
        updated_at: {
          display: <DateDisplay date={edge.node.updated_at} />,
        },
      },
    };
  });

  return (
    <Col className="gap-0">
      <Row className="p-2">
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
