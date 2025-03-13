import { GlobalEventDetails } from "@/entities/events/ui/global-event-details";
import { useParams } from "react-router";
import { useEventDetails } from "@/entities/events/api/get-event-details.query";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import ErrorScreen from "@/shared/components/errors/error-screen";

export function Component() {
  const { activityId } = useParams() as { activityId: string };
  const { isPending, isRefetching, data, error, refetch } = useEventDetails({ id: activityId });

  if (!isPending) {
    return (
      <Content.Card className="grow">
        <LoadingIndicator className="h-full" />
      </Content.Card>
    );
  }

  if (error) {
    return (
      <Content.Card>
        <ErrorScreen message="An error occured while retrieving the activity details." />
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
