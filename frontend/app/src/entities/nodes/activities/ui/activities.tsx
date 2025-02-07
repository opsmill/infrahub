import { EventNodeInterface } from "@/shared/api/graphql/generated/graphql";
import ErrorFallback from "@/shared/components/errors/error-fallback";
import { Spinner } from "@/shared/components/ui/spinner";
import { useActivities } from "../api/get-activities.query";
import { INFRAHUB_EVENT } from "../utils/constants";
import { Activity } from "./activity";

export const Activities = () => {
  const { isLoading, data, error } = useActivities();

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    return <ErrorFallback error={error} />;
  }

  const activities: EventNodeInterface[] = data?.data?.[INFRAHUB_EVENT]?.edges?.map((edge) => {
    return edge.node;
  });

  return (
    <div className="flex flex-col gap-4">
      {activities?.map((activity) => (
        <Activity key={activity.id} {...activity} />
      ))}
    </div>
  );
};
