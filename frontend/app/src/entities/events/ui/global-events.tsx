import ErrorFallback from "@/shared/components/errors/error-fallback";
import { Spinner } from "@/shared/components/ui/spinner";
import { useParams } from "react-router";
import { useEvents } from "../api/get-events.query";
import { INFRAHUB_EVENT } from "../utils/constants";
import { Event, EventType } from "./event";

export const GlobalEvents = () => {
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

  return (
    <div className="flex flex-col gap-2 p-2 overflow-auto">
      {activities?.map((activity) => (
        <Event key={activity.id} {...activity} />
      ))}
    </div>
  );
};
