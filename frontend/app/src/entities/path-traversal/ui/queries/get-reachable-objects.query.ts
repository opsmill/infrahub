import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getReachableObjects } from "@/entities/path-traversal/domain/get-reachable-objects";
import type { GetReachableObjectsParams } from "@/entities/path-traversal/domain/path-traversal.types";
import { pathTraversalQueryKeys } from "@/entities/path-traversal/ui/queries/path-traversal.query-keys";

export function getReachableObjectsQueryOptions(params: GetReachableObjectsParams) {
  return queryOptions({
    queryKey: pathTraversalQueryKeys.reachable(params),
    queryFn: () => getReachableObjects(params),
  });
}

type UseGetReachableObjectsParams = Omit<GetReachableObjectsParams, "branchName" | "atDate">;

export function useGetReachableObjects(
  params: UseGetReachableObjectsParams,
  config?: QueryConfig<typeof getReachableObjectsQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getReachableObjectsQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
