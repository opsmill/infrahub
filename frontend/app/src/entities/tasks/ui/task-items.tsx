import { forwardRef, useImperativeHandle } from "react";
import { useLocation, useParams } from "react-router";

import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { InlineDisplay } from "@/shared/components/display/inline-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Table, type tColumn } from "@/shared/components/table/table";
import { Id } from "@/shared/components/ui/id";
import { Link } from "@/shared/components/ui/link";
import { Pagination } from "@/shared/components/ui/pagination";
import { SearchInput, type SearchInputProps } from "@/shared/components/ui/search-input";
import {
  SEARCH_ANY_FILTER,
  SEARCH_FILTERS,
  TASK_OBJECT,
  TASK_TAB,
} from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";
import { debounce } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { GET_TASKS } from "@/entities/tasks/api/getTasksItems";
import { TaskFilters } from "@/entities/tasks/ui/task-filters";

import { getStateBadge } from "./task-item-details";

interface TaskItemsProps {
  hideRelatedNode?: boolean;
}

export const TaskItems = forwardRef(({ hideRelatedNode }: TaskItemsProps, ref) => {
  const { objectId, proposedChangeId } = useParams();
  const location = useLocation();
  const [filters, setFilters] = useFilters();

  const search = filters.find((filter) => filter.name === SEARCH_ANY_FILTER)?.value;
  const branch = filters.find((filter) => filter.name === "branch__value")?.value;
  const state = filters.find((filter) => filter.name === "state__value")?.value;
  const node = filters.find((filter) => filter.name === "node__value")?.value;

  const { pathname } = location;

  const relatedNode = node || objectId || proposedChangeId;

  const {
    loading,
    error,
    data = {},
    refetch,
  } = useQuery(GET_TASKS, {
    variables: {
      search,
      branch,
      state,
      relatedNodes: relatedNode ? [relatedNode] : [],
    },
  });

  const handleSearch: SearchInputProps["onChange"] = (e) => {
    const value = e.target.value as string;

    if (!value) {
      const newFilters = filters.filter((filter: Filter) => !SEARCH_FILTERS.includes(filter.name));

      setFilters(newFilters);

      return;
    }

    const newFilters: Array<Filter> = [
      ...filters,
      {
        name: SEARCH_ANY_FILTER,
        value,
      },
    ];

    setFilters(newFilters);
  };

  const debouncedHandleSearch = debounce(handleSearch, 500);

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

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
    !hideRelatedNode && {
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
    if (!objectId && !proposedChangeId) {
      return constructPath(`/tasks/${id}`);
    }

    return constructPath(pathname, [
      { name: proposedChangeId ? QSP.PROPOSED_CHANGES_TAB : QSP.TAB, value: TASK_TAB },
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
    <Content.Card>
      <Content.CardTitle title="Task Overview" badgeContent={count} />

      <div className="flex flex-1 flex-col bg-white dark:bg-slate-700">
        <div className="flex items-center gap-2 p-2">
          <SearchInput
            loading={loading}
            defaultValue={search}
            onChange={debouncedHandleSearch}
            placeholder="Search an object"
            className="h-7 border-none focus-visible:ring-0"
            data-testid="object-list-search-bar"
          />

          <TaskFilters />
        </div>

        {loading && !rows && <LoadingIndicator className="p-4" />}

        {rows && (
          <div>
            <Table columns={columns} rows={rows} className="border-none" />

            <Pagination count={count} />
          </div>
        )}
      </div>
    </Content.Card>
  );
});
