import { useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { BreadcrumbItem, Breadcrumbs } from "@/shared/components/aria/breadcrumbs";

export function BreadcrumbActivities() {
  const { activityId } = useParams();

  return (
    <Breadcrumbs data-testid="breadcrumb-activities">
      <BreadcrumbItem href={constructPath("/activities")}>Activities</BreadcrumbItem>
      {activityId && (
        <BreadcrumbItem href={constructPath(`/activities/${activityId}`)}>
          {activityId}
        </BreadcrumbItem>
      )}
    </Breadcrumbs>
  );
}
