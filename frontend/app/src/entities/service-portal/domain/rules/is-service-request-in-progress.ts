import { SERVICE_REQUEST_STATUS } from "@/entities/service-portal/domain/model/service-request";

export const isServiceRequestInProgress = (status: string | null | undefined): boolean =>
  status === SERVICE_REQUEST_STATUS.SUBMITTED || status === SERVICE_REQUEST_STATUS.GENERATING;
