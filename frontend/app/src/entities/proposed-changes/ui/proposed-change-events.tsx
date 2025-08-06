import { useGetEvents } from "@/entities/events/domain/get-events.query";
import { EventCard } from "@/entities/events/ui/event-card";
import { PROPOSED_CHANGE_EVENTS } from "@/entities/proposed-changes/constants";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import React from "react";
import { useParams } from "react-router";

const THREAD_EVENT = {
  id: "e4683406-e068-4718-bfc4-5b84eebaa46z",
  event: "infrahub.proposed_change.thread",
  branch: "test",
  occurred_at: "2025-08-06T10:40:43.641161+00:00",
  level: 0,
  account_id: "1859250b-3078-9596-389b-c510ee80b9b9",
  primary_node: {
    id: "185925d3-3b1a-3a52-3893-c515647a53c9",
    kind: "CoreProposedChange",
    __typename: "RelatedNode",
  },
  related_nodes: [
    {
      id: "1859250b-3078-9596-389b-c510ee80b9b9",
      kind: "CoreGenericAccount",
      __typename: "RelatedNode",
    },
  ],
  payload: {
    id: "185927d4-18c4-fe04-3893-c5131b57fe98",
  },
  has_children: false,
  __typename: "ProposedChangeMergedEvent",
};

export const ProposedChangeEvents = () => {
  const { proposedChangeId } = useParams();

  const { isPending, data, error } = useGetEvents({
    filters: {
      primaryNodeIds: proposedChangeId ? [proposedChangeId] : undefined,
      eventType: PROPOSED_CHANGE_EVENTS,
      limit: 0,
      order: "ASC",
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
    <div className="flex flex-col gap-2 p-2" data-testid="activities-container">
      {flatData.map((activity) => (
        <EventCard key={activity.id} {...activity} />
      ))}

      <EventCard {...THREAD_EVENT} />
    </div>
  );
};
