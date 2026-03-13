import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { type GetProfilesParams, getProfiles } from "@/entities/nodes/profiles/domain/get-profiles";

export function getProfilesQueryOptions(params: GetProfilesParams) {
  return queryOptions({
    queryKey: objectQueryKeys.profiles({ ...params, objectKind: params.schema.kind! }),
    queryFn: () => getProfiles(params),
  });
}

export const useGetProfiles = (
  params: Omit<GetProfilesParams, keyof ContextParams>,
  config?: QueryConfig<typeof getProfilesQueryOptions>
) => {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getProfilesQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
};
