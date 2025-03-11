import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { CardWithBorder } from "@/shared/components/ui/card";
import { useParams } from "react-router";
import { useEventDetails } from "../api/get-event-details.query";
import { EventDetails } from "./event-card";
import { NodeEvents } from "./node-details-events";

const EventDetailsView = () => {
  const { activityid } = useParams();

  const { isLoading, data, error, refetch } = useEventDetails({ id: activityid });

  return (
    <Content.Card>
      <Content.CardTitle title={data?.event} isReloadLoading={isLoading} reload={() => refetch()} />
      <Content.CardContent className="p-2">
        {error && <ErrorScreen message="An error occured while retrieving the activity details." />}

        {!error && (
          <div className="flex items-start gap-2">
            <CardWithBorder className="p-0 border-0 flex-1">
              <CardWithBorder.Title>Details</CardWithBorder.Title>
              <EventDetails {...data} />
            </CardWithBorder>

            {data?.has_children && (
              <CardWithBorder className="p-0 border-0 flex-1">
                <CardWithBorder.Title>Sub activities</CardWithBorder.Title>
                <NodeEvents parentId={activityid} />
              </CardWithBorder>
            )}
          </div>
        )}
      </Content.CardContent>
    </Content.Card>
  );
};

export default EventDetailsView;
