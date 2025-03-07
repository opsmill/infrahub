import { QSP } from "@/config/qsp";
import { useNodeLabel } from "@/entities/nodes/object/api/get-display-label.query";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { Link } from "@/shared/components/ui/link";
import { Spinner } from "@/shared/components/ui/spinner";
import React from "react";
import { useParams } from "react-router";
import { useEvents } from "../api/get-events.query";
import { EventCard } from "./event-card";

const MAX_EVENTS = 5;

export const NodeEvents = ({
  parentId,
  relatedNodeId,
}: { parentId?: string; relatedNodeId?: string }) => {
  const { objectKind, objectid } = useParams();

  const relatedId = relatedNodeId || objectid;

  const { isPending, data, error } = useEvents({
    filters: {
      parentIds: parentId ? [parentId] : undefined,
      relatedNodeIds: relatedId ? [relatedId] : undefined,
      limit: parentId ? 0 : MAX_EVENTS,
    },
  });

  const {
    isPending: isLoadingNodeLabel,
    error: displayLabelError,
    data: displayLabelData,
  } = useNodeLabel({
    objectid: objectid,
    kind: objectKind as string,
    enabled: !parentId,
  });

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  if (isPending) {
    return (
      <div className="flex items-center justify-center flex-grow">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return <ErrorScreen message={error?.message || displayLabelError?.message} />;
  }

  if (!flatData.length) {
    return <NoDataFound message="No activity found for this object." />;
  }

  const filter = {
    name: "relatedNodeIds__value",
    value: [{ id: objectid, display_label: displayLabelData.display_label }],
  };

  return (
    <div className="flex flex-col gap-2 p-2">
      {flatData.map((activity) => (
        <EventCard key={activity.id} {...activity} />
      ))}

      {!parentId && !isLoadingNodeLabel && (
        <div className="flex items-center justify-center">
          <Link
            to={constructPath("/activities", [
              { name: QSP.FILTER, value: JSON.stringify([filter]) },
            ])}
            className="p-1 text-sm text-gray-400 text-center"
          >
            View all activities
          </Link>
        </div>
      )}
    </div>
  );
};
