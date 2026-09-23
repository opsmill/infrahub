import { queryOptions, useQuery } from "@tanstack/react-query";

import { getServiceCatalog } from "@/entities/service-portal/domain/use-cases/get-service-catalog";
import { servicePortalQueryKeys } from "@/entities/service-portal/ui/queries/service-portal.query-keys";

export function getServiceCatalogQueryOptions() {
  return queryOptions({
    queryKey: servicePortalQueryKeys.catalog(),
    queryFn: getServiceCatalog,
  });
}

export function useGetServiceCatalog() {
  return useQuery(getServiceCatalogQueryOptions());
}
