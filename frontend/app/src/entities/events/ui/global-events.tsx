import ErrorFallback from "@/shared/components/errors/error-fallback";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { Spinner } from "@/shared/components/ui/spinner";
import { useEvents } from "../api/get-events.query";
import { INFRAHUB_EVENT } from "../utils/constants";
import { EventType } from "./event";
import { Event } from "./global-event";

export const GlobalEvents = () => {
  const { isLoading, data, error, refetch } = useEvents({});

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
    <Content.Card>
      <Content.CardTitle
        title="Activities"
        badgeContent={data?.data?.[INFRAHUB_EVENT]?.count}
        isReloadLoading={isLoading}
        reload={() => refetch()}
      />
      <div className="flex flex-col gap-2 p-2">
        {!activities?.length && <NoDataFound message="No activity found." />}

        {activities?.map((activity) => (
          <Event key={activity.id} {...activity} />
        ))}
      </div>
    </Content.Card>
  );
};
