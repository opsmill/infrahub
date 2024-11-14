import { Table, tColumn } from "@/components/table/table";
import { Pagination } from "@/components/ui/pagination";
import { SEARCH_ANY_FILTER, SEARCH_FILTERS, TASK_OBJECT, TASK_TAB } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import Content from "@/screens/layout/content";
import { gql } from "@apollo/client";

import { DateDisplay } from "@/components/display/date-display";
import { Filters } from "@/components/filters/filters";
import { Id } from "@/components/ui/id";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import { QSP } from "@/config/qsp";
import { getTasksItems } from "@/graphql/queries/tasks/getTasksItems";
import useFilters, { Filter } from "@/hooks/useFilters";
import ErrorScreen from "@/screens/errors/error-screen";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { debounce } from "@/utils/common";
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
  const [filters, setFilters] = useFilters();

  const search = filters.find((filter) => filter.name === SEARCH_ANY_FILTER)?.value;
  const branch = filters.find((filter) => filter.name === "branch__value")?.value;
  const state = filters.find((filter) => filter.name === "state__value")?.value;

  const { pathname } = location;

  const queryString = getTasksItems({
    kind: TASK_OBJECT,
    relatedNode: objectid || proposedChangeId,
  });

  const query = gql`
    ${queryString}
  `;

  const {
    loading,
    error,
    data = {},
    refetch,
  } = useQuery(query, {
    variables: {
      search,
      branch,
      state,
    },
  });

  const handleSearch: SearchInputProps["onChange"] = (e) => {
    const value = e.target.value as string;

    if (!value) {
      const newFilters = filters.filter((filter: Filter) => !SEARCH_FILTERS.includes(filter.name));

      setFilters(newFilters);

      return;
    }

    const newFilters = [
      ...filters,
      {
        name: SEARCH_ANY_FILTER,
        value: value,
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
      name: "related_node",
      label: "Related node",
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
    if (!objectid && !proposedChangeId) {
      return constructPath(`/tasks/${id}`);
    }

    const url = constructPath(pathname, [
      { name: proposedChangeId ? QSP.PROPOSED_CHANGES_TAB : QSP.TAB, value: TASK_TAB },
      { name: QSP.TASK_ID, value: id },
    ]);

    return url;
  };

  const rows = edges?.map((edge: any) => ({
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
      related_node: {
        display: edge.node.related_node_kind && (
          <Id id={edge.node.related_node} kind={edge.node.related_node_kind} preventCopy />
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
  }));

  return (
    <Content.Card>
      <Content.CardTitle title="Task Overview" badgeContent={count} />

      <div className="bg-custom-white flex-1 flex flex-col">
        <div className="flex items-center gap-2 p-2">
          <SearchInput
            loading={loading}
            defaultValue={search}
            onChange={debouncedHandleSearch}
            placeholder="Search an object"
            className="border-none focus-visible:ring-0 h-7"
            data-testid="object-list-search-bar"
          />

          <Filters kind={TASK_OBJECT} />
        </div>

        {loading && !rows && <LoadingScreen message="Loading tasks" />}

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
