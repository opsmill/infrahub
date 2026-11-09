import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { GetReachableNodesParams } from "@/entities/path-traversal/domain/model/path-traversal";
import { getReachableNodes } from "@/entities/path-traversal/domain/use-cases/get-reachable-nodes";
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
