import { queryOptions, useQuery } from "@tanstack/react-query";

import { getInfrahubAccountToken } from "@/entities/user-profile/domain/get-infrahub-account-token";

export function getInfrahubAccountTokenQueryOptions() {
  return queryOptions({
    queryKey: ["get-infrahub-account-token"],
    queryFn: getInfrahubAccountToken,
  });
}

export function useInfrahubAccountToken() {
  return useQuery(getInfrahubAccountTokenQueryOptions());
}
