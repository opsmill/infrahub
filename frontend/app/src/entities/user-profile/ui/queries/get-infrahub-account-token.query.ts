import { queryOptions, useQuery } from "@tanstack/react-query";

import { getInfrahubAccountToken } from "@/entities/user-profile/domain/get-infrahub-account-token";
import { accountQueryKeys } from "@/entities/user-profile/ui/queries/account-query.keys";

export function getInfrahubAccountTokenQueryOptions() {
  return queryOptions({
    queryKey: accountQueryKeys.tokens(),
    queryFn: getInfrahubAccountToken,
  });
}

export function useInfrahubAccountToken() {
  return useQuery(getInfrahubAccountTokenQueryOptions());
}
