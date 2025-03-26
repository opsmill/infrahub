import { getInfrahubAccountToken } from "@/entities/user-profile/domain/get-infrahub-account-token";
import { queryOptions, useQuery } from "@tanstack/react-query";

export function getInfrahubAccountTokenQueryOptions() {
  return queryOptions({
    queryKey: ["get-infrahub-account-token"],
    queryFn: getInfrahubAccountToken,
  });
}

export function useInfrahubAccountToken() {
  return useQuery(getInfrahubAccountTokenQueryOptions());
}
