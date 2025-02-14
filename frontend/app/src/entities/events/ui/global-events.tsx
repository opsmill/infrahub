import { ActiveFilterTags } from "@/entities/nodes/object/ui/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import ErrorFallback from "@/shared/components/errors/error-fallback";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { Pagination } from "@/shared/components/ui/pagination";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Spinner } from "@/shared/components/ui/spinner";
import useFilters from "@/shared/hooks/useFilters";
import usePagination from "@/shared/hooks/usePagination";
import { useEvents } from "../api/get-events.query";
import { INFRAHUB_EVENT } from "../utils/constants";
import { EventType } from "./event";
import { Event } from "./global-event";

export const GlobalEvents = () => {
  const [pagination] = usePagination();
  const { isLoading, data, error, refetch } = useEvents({ ...pagination });

  const [filters] = useFilters();

  if (error) {
    return <ErrorFallback error={error} />;
  }

  const activities: EventType[] = data?.data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node;
  });

  const count = data?.data?.[INFRAHUB_EVENT]?.count;

  return (
    <Content.Card>
      <Content.CardTitle
        title="Activities"
        badgeContent={count}
        isReloadLoading={isLoading}
        reload={() => refetch()}
      />
      <div className="flex flex-col flex-grow gap-2 p-2">
        <div className="flex items-center">
          <FilterSearchInput placeholder="Search an activity" />

          {filters.length > 0 && (
            <>
              <ScrollArea scrollX>
                <ActiveFilterTags className="mx-2" />
              </ScrollArea>

              <FilterResetButton />
            </>
          )}
        </div>

        <div className="flex flex-col gap-2">
          {!isLoading && !activities?.length && <NoDataFound message="No activity found." />}

          {activities?.map((activity) => (
            <Event key={activity.id} {...activity} />
          ))}
        </div>

        {isLoading && (
          <div className="flex justify-center flex-grow">
            <Spinner />
          </div>
        )}

        <Pagination count={count} />
      </div>
    </Content.Card>
  );
};
