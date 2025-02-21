import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import ErrorFallback from "@/shared/components/errors/error-fallback";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { Pagination } from "@/shared/components/ui/pagination";
import { Spinner } from "@/shared/components/ui/spinner";
import useFilters from "@/shared/hooks/useFilters";
import usePagination from "@/shared/hooks/usePagination";
import { useEvents } from "../api/get-events.query";
import { Event } from "./global-event";
import { GlobalEventsFilters } from "./global-events-filters";

export const GlobalEvents = () => {
  const [pagination] = usePagination();
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

  const { isLoading, data, error, refetch } = useEvents({ ...pagination, ...queryFilters });

  if (error) {
    return <ErrorFallback error={error} />;
  }

  return (
    <Content.Card>
      <Content.CardTitle
        title="Activities"
        badgeContent={data?.count}
        isReloadLoading={isLoading}
        reload={() => refetch()}
      />
      <div className="flex flex-col flex-grow gap-2 p-2">
        <div className="flex items-center gap-2">
          <GlobalEventsFilters />
          {filters.length > 0 && <FilterResetButton />}
        </div>

        <div className="flex flex-col gap-2">
          {!isLoading && !data?.activities?.length && <NoDataFound message="No activity found." />}

          {data?.activities?.map((activity) => (
            <Event key={activity.id} {...activity} />
          ))}
        </div>

        {isLoading && (
          <div className="flex justify-center flex-grow">
            <Spinner />
          </div>
        )}

        <Pagination count={data?.count} />
      </div>
    </Content.Card>
  );
};
