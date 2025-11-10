import React from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";

import { useGetEvents } from "../domain/get-events.query";
import { EventCard } from "./event-card";

const MAX_EVENTS = 10;

export const HomeEvents = ({ maxEvent = MAX_EVENTS }: { maxEvent?: number }) => {
  const { isPending, data, error } = useGetEvents({
    filters: {
      limit: maxEvent,
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
    return (
      <EmptyHomeCard
        title={"No activity yet"}
        subtitle={"Try creating or updating something to get started."}
        className="py-28"
      />
    );
  }

  return (
    <div className="flex flex-col gap-2 p-2" data-testid="activities-container">
      {flatData.map((activity) => (
        <EventCard key={activity.id} {...activity} />
      ))}
    </div>
  );
};
