import { useGetEvents } from "@/entities/events/domain/get-events.query";
import { EventCard } from "@/entities/events/ui/event-card";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/constants";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { InfiniteTrigger } from "@/shared/components/utils/infinite-trigger";
import React from "react";
import { useParams } from "react-router";

export const ProposedChangeEvents = () => {
  const { proposedChangeId } = useParams();

  const { isPending, data, error, hasNextPage, fetchNextPage } = useGetEvents({
    filters: {
      primaryNodeIds: proposedChangeId ? [proposedChangeId] : undefined,
      eventType: PROPOSED_CHANGE_EVENTS,
      order: "ASC",
    },
    config: {
      refetchInterval: 1000,
    },
  });

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  if (isPending) {
    return <LoadingIndicator className="p-4" message="" />;
  }

  if (error) {
    return <ErrorScreen message={error?.message} />;
  }

  if (!flatData.length) {
    return <NoDataFound message="No activity found for this proposed change." />;
  }

  return (
    <InfiniteTrigger
      hasNextPage={hasNextPage}
      onLoadMore={fetchNextPage}
      className="flex flex-col gap-2 p-2"
    >
      {flatData.map((activity) => (
        <EventCard key={activity.id} {...activity} />
      ))}
    </InfiniteTrigger>
  );
};
