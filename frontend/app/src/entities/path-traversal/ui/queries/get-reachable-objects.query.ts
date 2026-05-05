import { queryOptions, type UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getReachableObjects } from "@/entities/path-traversal/domain/get-reachable-objects";
import type {
  GetReachableObjectsParams,
  ReachableObjectsResponse,
} from "@/entities/path-traversal/domain/path-traversal.types";
import { pathTraversalQueryKeys } from "@/entities/path-traversal/ui/queries/path-traversal.query-keys";

export function getReachableObjectsQueryOptions(params: GetReachableObjectsParams) {
  return queryOptions({
    queryKey: pathTraversalQueryKeys.reachable(params),
    queryFn: () => getReachableObjects(params),
  });
}

type UseGetReachableObjectsParams = Omit<GetReachableObjectsParams, "branchName" | "atDate">;
type UseGetReachableObjectsConfig = Partial<UseQueryOptions<ReachableObjectsResponse>>;

export function useGetReachableObjects(
  params: UseGetReachableObjectsParams,
  config?: UseGetReachableObjectsConfig
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
