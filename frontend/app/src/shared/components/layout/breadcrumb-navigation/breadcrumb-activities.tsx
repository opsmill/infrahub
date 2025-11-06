import { useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Breadcrumb, BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbActivities() {
  const { activityId } = useParams();

  return (
    <Breadcrumb data-testid="breadcrumb-activities">
      <BreadcrumbItem href={constructPath("/activities")}>Activities</BreadcrumbItem>
      {activityId && (
        <BreadcrumbItem href={constructPath(`/activities/${activityId}`)}>
          {activityId}
        </BreadcrumbItem>
      )}
    </Breadcrumb>
  );
}
