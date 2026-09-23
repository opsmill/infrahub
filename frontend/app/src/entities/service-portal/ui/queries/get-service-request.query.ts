import { queryOptions, useQuery } from "@tanstack/react-query";

import type { QueryConfig } from "@/shared/api/types";

import {
  type GetServiceRequestParams,
  getServiceRequest,
} from "@/entities/service-portal/domain/use-cases/get-service-request";
import { servicePortalQueryKeys } from "@/entities/service-portal/ui/queries/service-portal.query-keys";

export function getServiceRequestQueryOptions(params: GetServiceRequestParams) {
  return queryOptions({
    queryKey: servicePortalQueryKeys.request(params),
    queryFn: () => getServiceRequest(params),
  });
}

export function useGetServiceRequest(
  params: GetServiceRequestParams,
  config?: QueryConfig<typeof getServiceRequestQueryOptions>
) {
  return useQuery({ ...getServiceRequestQueryOptions(params), ...config });
}
