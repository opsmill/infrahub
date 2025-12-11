import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { type GetProfilesParams, getProfiles } from "@/entities/profiles/domain/get-profiles";
import { profilesQueryKeys } from "@/entities/profiles/domain/profiles.query-keys";
import type { ProfileQueryParams } from "@/entities/profiles/types";

export function getProfilesQueryOptions(params: GetProfilesParams) {
  return queryOptions({
    queryKey: profilesQueryKeys.list(params),
    queryFn: () => getProfiles(params),
    enabled: params.profiles.length > 0,
  });
}

export interface UseGetProfilesParams {
  profiles: ProfileQueryParams[];
}

export const useGetProfiles = (params: UseGetProfilesParams) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery(
    getProfilesQueryOptions({
      ...params,
      branchName: currentBranch.name,
      atDate: timeMachineDate,
    })
  );
};
