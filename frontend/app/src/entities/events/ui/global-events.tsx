import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { Button } from "@/shared/components/buttons/button-primitive";
import ErrorFallback from "@/shared/components/errors/error-fallback";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { Spinner } from "@/shared/components/ui/spinner";
import useFilters from "@/shared/hooks/useFilters";
import React from "react";
import { useEvents } from "../api/get-events.query";
import { Event } from "./global-event";
import { GlobalEventsFilters } from "./global-events-filters";

export const GlobalEvents = () => {
  const [filters] = useFilters();

  const queryFilters = filters.reduce((acc, filter) => {
    if (Array.isArray(filter.value)) {
      return {
        ...acc,
        [filter.name.split("__")[0]]: filter.value.map((value) => {
          return value.id;
        }),
      };
    }

    return { ...acc, [filter.name.split("__")[0]]: filter.value };
  }, {});

  const { isLoading, data, error, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useEvents({
      filters: {
        ...queryFilters,
        level: 0,
      },
    });

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  if (error) {
    return <ErrorFallback error={error} />;
  }

  return (
    <Content.Card>
      <Content.CardTitle title="Activities" isReloadLoading={isLoading} reload={() => refetch()} />
      <div className="flex flex-col flex-grow gap-2 p-2">
        <div className="flex items-center gap-2">
          <GlobalEventsFilters />
          {filters.length > 0 && <FilterResetButton />}
        </div>

        <div className="flex flex-col gap-2">
          {!isLoading && !flatData?.length && <NoDataFound message="No activity found." />}

          {flatData?.map((activity) => (
            <Event key={activity?.id} {...activity} />
          ))}

          {hasNextPage && (
            <div className="flex items-center justify-center">
              <Button
                variant={"primary"}
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? "Loading more..." : "Load more"}
              </Button>
            </div>
          )}
        </div>

        {isLoading && (
          <div className="flex justify-center flex-grow">
            <Spinner />
          </div>
        )}
      </div>
    </Content.Card>
  );
};
