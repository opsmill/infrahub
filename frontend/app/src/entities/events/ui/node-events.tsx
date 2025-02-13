import ErrorFallback from "@/shared/components/errors/error-fallback";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { Spinner } from "@/shared/components/ui/spinner";
import { useParams } from "react-router";
import { useEvents } from "../api/get-events.query";
import { INFRAHUB_EVENT } from "../utils/constants";
import { Event, EventType } from "./event";

export const NodeEvents = () => {
  const { objectid } = useParams();

  const { isLoading, data, error } = useEvents({ ids: [objectid] });

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    return <ErrorFallback error={error} />;
  }

  const activities: EventType[] = data?.data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node;
  });

  if (!activities.length) {
    return <NoDataFound message="No activity found for this object." />;
  }

  return (
    <div className="flex flex-col gap-2 p-2">
      {activities?.map((activity) => (
        <Event key={activity.id} {...activity} />
      ))}
    </div>
  );
};
