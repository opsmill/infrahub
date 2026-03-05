import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { GlobalEventDetails } from "@/entities/events/ui/global-event-details";
import { useGetEventDetails } from "@/entities/events/ui/queries/get-event-details.query";

export function Component() {
  const { activityId } = useParams() as { activityId: string };
  const { isPending, isRefetching, data, error, refetch } = useGetEventDetails({ id: activityId });

  if (isPending) {
    return (
      <Content.Card className="grow">
        <LoadingIndicator className="h-full" />
      </Content.Card>
    );
  }

  if (error) {
    return (
      <Content.Card>
        <ErrorScreen message={error.message} />
      </Content.Card>
    );
  }

  return (
    <Content.Card>
      <Content.CardTitle
        title={data.event}
        isReloadLoading={isRefetching}
        reload={() => refetch()}
      />
      <GlobalEventDetails eventNode={data} />
    </Content.Card>
  );
}
