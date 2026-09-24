import {
  SERVICE_REQUEST_STATUS,
  type ServiceRequestStatus,
} from "@/entities/service-portal/domain/model/service-request";

export const isServiceRequestInProgress = (
  status: ServiceRequestStatus | null | undefined
): boolean =>
  status === SERVICE_REQUEST_STATUS.SUBMITTED || status === SERVICE_REQUEST_STATUS.GENERATING;
