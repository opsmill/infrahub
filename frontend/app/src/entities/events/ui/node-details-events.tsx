import React from "react";

import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Link } from "@/shared/components/ui/link";
import { QSP } from "@/shared/config/qsp";

import { useNodeLabel } from "@/entities/nodes/object/api/get-display-label.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

import { useGetEvents } from "../domain/get-events.query";
import { EventCard } from "./event-card";

const MAX_EVENTS = 5;

export const NodeEvents = ({
  parentId,
  objectId,
  objectKind,
  maxEvent = MAX_EVENTS,
}: {
  parentId?: string;
  objectId?: string;
  objectKind?: string;
  maxEvent?: number;
}) => {
  const { isPending, data, error } = useGetEvents({
    filters: {
      parentIds: parentId ? [parentId] : undefined,
      relatedNodeIds: objectId ? [objectId] : undefined,
      limit: parentId ? 0 : maxEvent,
    },
  });

  const {
    isPending: isLoadingNodeLabel,
    error: displayLabelError,
    data: displayLabelData,
  } = useNodeLabel({
    objectId,
    kind: objectKind as string,
    enabled: !parentId && !!objectKind,
  });

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  if (isPending) {
    return <LoadingIndicator className="p-4" message="" />;
  }

  if (error) {
    return <ErrorScreen message={error?.message || displayLabelError?.message} />;
  }

  if (!flatData.length) {
    return <NoDataFound message="No activity found for this object." />;
  }

  const filter = {
    name: "relatedNodeIds__value",
    value: [{ id: objectId, display_label: getNodeLabel(displayLabelData) }],
  };

  return (
    <div className="flex flex-col gap-2 p-2" data-testid="activities-container">
      {flatData.map((activity) => (
        <EventCard key={activity.id} {...activity} />
      ))}

      {!parentId && !isLoadingNodeLabel && (
        <div className="flex items-center justify-center">
          <Link
            to={constructPath("/activities", [
              { name: QSP.FILTER, value: JSON.stringify([filter]) },
            ])}
            className="p-1 text-center text-gray-400 text-sm"
          >
            View all activities
          </Link>
        </div>
      )}
    </div>
  );
};
