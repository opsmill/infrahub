import { queryOptions, useQuery } from "@tanstack/react-query";

import { getAccountProfile } from "@/entities/user-profile/domain/get-account-profile";
import { accountQueryKeys } from "@/entities/user-profile/ui/queries/account-query.keys";

export function getAccountProfileQueryOptions() {
  return queryOptions({
    queryKey: accountQueryKeys.details(),
    queryFn: getAccountProfile,
  });
}

export function useGetAccountProfile() {
  return useQuery(getAccountProfileQueryOptions());
}
