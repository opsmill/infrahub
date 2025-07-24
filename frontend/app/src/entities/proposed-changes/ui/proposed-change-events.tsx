import { useGetEvents } from "@/entities/events/domain/get-events.query";
import { EventCard } from "@/entities/events/ui/event-card";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import React from "react";
import { useParams } from "react-router";

export const ProposedChangeEvents = () => {
  const { proposedChangeId } = useParams();

  const { isPending, data, error } = useGetEvents({
    filters: {
      relatedNodeIds: proposedChangeId ? [proposedChangeId] : undefined,
      limit: 0,
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
    return <NoDataFound message="No activity found for this object." />;
  }

  return (
    <div className="flex flex-col gap-2 p-2" data-testid="activities-container">
      {flatData.map((activity) => (
        <EventCard key={activity.id} {...activity} />
      ))}
    </div>
  );
};
