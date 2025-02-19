import { constructPath } from "@/shared/api/rest/fetch";
import ErrorFallback from "@/shared/components/errors/error-fallback";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { Link } from "@/shared/components/ui/link";
import { Spinner } from "@/shared/components/ui/spinner";
import { useParams } from "react-router";
import { useEvents } from "../api/get-events.query";
import { Event } from "./event";

const MAX_EVENTS = 5;

export const NodeEvents = () => {
  const { objectid } = useParams();

  const { isLoading, data, count, error } = useEvents({ ids: [objectid], limit: MAX_EVENTS });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center flex-grow">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return <ErrorFallback error={error} />;
  }

  if (!data?.length) {
    return <NoDataFound message="No activity found for this object." />;
  }

  return (
    <div className="flex flex-col gap-2 p-2">
      {data?.map((activity) => (
        <Event key={activity.id} {...activity} />
      ))}

      {count > MAX_EVENTS && (
        <div className="flex items-center justify-center">
          <Link to={constructPath("/activities")} className="p-1 text-sm text-gray-400 text-center">
            More events...
          </Link>
        </div>
      )}
    </div>
  );
};
