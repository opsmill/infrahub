import { useMemo } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Spinner } from "@/shared/components/ui/spinner";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";

import { useGetEvents } from "@/entities/events/ui/queries/get-events.query";
import { GlobalEventsFilters } from "@/entities/events/ui/filters/global-events-filters";
import { Event } from "@/entities/events/ui/global-event";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";

export function Component() {
  const [filters] = useFilters();

  const queryFilters = useMemo(() => {
    return filters.reduce((acc, filter) => {
      const key = filter.name.split("__")[0];

      if (!key) return acc;

      if (Array.isArray(filter.value)) {
        return {
          ...acc,
          [key]: filter.value.map((value) => value.id),
        };
      }

      return { ...acc, [key]: filter.value };
    }, {});
  }, [filters]);

  const {
    isPending,
    data,
    error,
    refetch,
    isRefetching,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useGetEvents({
    ...queryFilters,
    level: 0,
  });

  if (isPending) {
    return (
      <Content.Card className="grow">
        <LoadingIndicator className="h-full" />
      </Content.Card>
    );
  }

  if (error) {
    return (
      <Content.Card>
        <ErrorScreen message={error.message} />
      </Content.Card>
    );
  }

  const hasActivities = data.pages.some((page) => page.length > 0);

  return (
    <Content.Card className="flex grow flex-col">
      <Content.CardTitle
        title="Activities"
        isReloadLoading={isRefetching}
        reload={() => refetch()}
      />
      <FiltersSection hasFilters={filters.length > 0} />

      {!hasActivities ? (
        <EmptyActivitiesView hasFilters={filters.length > 0} />
      ) : (
        <>
          <div className="grid grid-cols-8 gap-2 px-4 py-2 font-semibold text-gray-500 text-xs">
            <span>Date</span>
            <span className="col-span-5">Event</span>
            <span>Branch</span>
            <span>Action</span>
          </div>

          <InfiniteScroll hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
            <div className="flex grow flex-col gap-2 p-2">
              {data.pages.map((page) =>
                page.map((activity) => <Event key={activity?.id} {...activity} />)
              )}

              {isFetchingNextPage && (
                <div className="flex grow justify-center">
                  <Spinner />
                </div>
              )}
            </div>
          </InfiniteScroll>
        </>
      )}
    </Content.Card>
  );
}

function FiltersSection({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="flex items-center gap-2 px-2 py-4">
      <GlobalEventsFilters />
      {hasFilters && <FilterResetButton />}
    </div>
  );
}

function EmptyActivitiesView({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="flex grow flex-col items-center justify-center p-8 text-gray-500">
      <p className="mb-2 font-medium text-lg">No activities found</p>
      <p className="text-center text-sm">
        {hasFilters
          ? "Try adjusting your filters to see more results"
          : "Activities will appear here when changes are made"}
      </p>
    </div>
  );
}
