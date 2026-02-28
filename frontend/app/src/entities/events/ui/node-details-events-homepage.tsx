import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

import { EmptyHomeCard } from "@/entities/homepage/ui/empty-home-card";

import { useGetEvents } from "@/entities/events/ui/queries/get-events.query";
import { EventCard } from "./event-card";

const MAX_EVENTS = 10;

export const HomeEvents = ({ maxEvent = MAX_EVENTS }: { maxEvent?: number }) => {
  const { isPending, data, error } = useGetEvents({
    limit: maxEvent,
  });

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const flatData = data?.pages?.flat() ?? [];

  if (!flatData.length) {
    return (
      <EmptyHomeCard
        title={"No activity yet"}
        subtitle={"Try creating or updating something to get started."}
      />
    );
  }

  return (
    <ScrollArea>
      <div className="flex flex-col gap-2 p-2" data-testid="activities-container">
        {flatData.map((activity) => (
          <EventCard key={activity.id} {...activity} />
        ))}
      </div>
    </ScrollArea>
  );
};
