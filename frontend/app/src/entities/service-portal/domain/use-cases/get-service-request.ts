import {
  type GetServiceRequestFromApiParams,
  getServiceRequestFromApi,
} from "@/entities/service-portal/api/get-service-request-from-api";
import type { ServiceRequest } from "@/entities/service-portal/domain/model/service-request";

export type GetServiceRequestParams = GetServiceRequestFromApiParams;
export type GetServiceRequestResult = ServiceRequest;

export const getServiceRequest = async (
  params: GetServiceRequestParams
): Promise<GetServiceRequestResult> => {
  const { data } = await getServiceRequestFromApi(params);
  const node = data.CoreServiceRequest.edges[0]?.node;

  if (!node) {
    throw new Error("This request could not be found.");
  }

  const service = node.service.node;

  return {
    id: node.id,
    status: node.status?.value ?? null,
    message: node.message?.value ?? null,
    branch: node.branch?.value ?? null,
    entryName: node.entry.node?.name?.value ?? null,
    proposedChangeId: node.proposed_change.node?.id ?? null,
    service: service?.id ? { id: service.id, kind: service.__typename } : null,
  };
};
