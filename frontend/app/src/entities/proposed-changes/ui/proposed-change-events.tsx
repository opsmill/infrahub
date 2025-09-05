import React from "react";
import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { InfiniteTrigger } from "@/shared/components/utils/infinite-trigger";

import { useGetEvents } from "@/entities/events/domain/get-events.query";
import { EventCard } from "@/entities/events/ui/event-card";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/constants";

export const ProposedChangeEvents = () => {
  const { proposedChangeId } = useParams();

  const { isPending, data, error, hasNextPage, fetchNextPage, isFetchingNextPage } = useGetEvents({
    filters: {
      primaryNodeIds: proposedChangeId ? [proposedChangeId] : undefined,
      eventType: PROPOSED_CHANGE_EVENTS,
      order: "ASC",
    },
    config: {
      refetchInterval: 10_000,
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
    return null;
  }

  return (
    <div className="flex flex-col gap-2 p-2">
      {flatData.map((activity) => (
        <EventCard key={activity.id} {...activity} />
      ))}
      <InfiniteTrigger
        hasNextPage={hasNextPage}
        onLoadMore={fetchNextPage}
        isFetchingNextPage={isFetchingNextPage}
      />
    </div>
  );
};
