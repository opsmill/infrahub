import ErrorFallback from "@/shared/components/errors/error-fallback";
import { Spinner } from "@/shared/components/ui/spinner";
import { useParams } from "react-router";
import { useActivities } from "../api/get-activities.query";
import { INFRAHUB_EVENT } from "../utils/constants";
import { Activity, ActivityType } from "./activity";

export const Activities = () => {
  const { objectid } = useParams();

  const { isLoading, data, error } = useActivities({ ids: [objectid] });

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    return <ErrorFallback error={error} />;
  }

  const activities: ActivityType[] = data?.data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node;
  });

  return (
    <div className="flex flex-col gap-2 p-2">
      {activities?.map((activity) => (
        <Activity key={activity.id} {...activity} />
      ))}
    </div>
  );
};
