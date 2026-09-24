import { Badge, type BadgeProps } from "@/shared/components/ui/badge";

import {
  SERVICE_REQUEST_STATUS,
  type ServiceRequestStatus,
} from "@/entities/service-portal/domain/model/service-request";

const STATUS_DISPLAY: Record<
  ServiceRequestStatus,
  { label: string; variant: BadgeProps["variant"] }
> = {
  [SERVICE_REQUEST_STATUS.SUBMITTED]: { label: "Submitted", variant: "blue" },
  [SERVICE_REQUEST_STATUS.GENERATING]: { label: "Building", variant: "yellow" },
  [SERVICE_REQUEST_STATUS.FAILED]: { label: "Failed", variant: "red" },
  [SERVICE_REQUEST_STATUS.IN_REVIEW]: { label: "In review", variant: "purple" },
  [SERVICE_REQUEST_STATUS.MERGED]: { label: "Delivered", variant: "green" },
  [SERVICE_REQUEST_STATUS.REJECTED]: { label: "Rejected", variant: "dark-gray" },
};

export function ServiceRequestStatusBadge({ status }: { status: ServiceRequestStatus | null }) {
  const display = status ? STATUS_DISPLAY[status] : { label: "Unknown", variant: "gray" as const };

  return <Badge variant={display.variant}>{display.label}</Badge>;
}
