import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getReachableNodes } from "@/entities/path-traversal/domain/get-reachable-nodes";
import type { GetReachableNodesParams } from "@/entities/path-traversal/domain/path-traversal.types";
import { pathTraversalQueryKeys } from "@/entities/path-traversal/ui/queries/path-traversal.query-keys";

export function getReachableNodesQueryOptions(params: GetReachableNodesParams) {
  return queryOptions({
    queryKey: pathTraversalQueryKeys.reachable(params),
    queryFn: () => getReachableNodes(params),
  });
}

type UseGetReachableNodesParams = Omit<GetReachableNodesParams, "branchName" | "atDate">;

export function useGetReachableNodes(
  params: UseGetReachableNodesParams,
  config?: QueryConfig<typeof getReachableNodesQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getReachableNodesQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
