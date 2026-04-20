import { type UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import {
  type GetReachableNodesParams,
  type ReachableNodesResponse,
  getReachableNodes,
} from "./get-reachable-nodes";

type UseReachableNodesParams = Omit<GetReachableNodesParams, "branchName" | "atDate">;
type UseReachableNodesConfig = Partial<UseQueryOptions<ReachableNodesResponse>>;

export function useGetReachableNodes(
  params: UseReachableNodesParams,
  config?: UseReachableNodesConfig
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    queryKey: [
      "reachable-nodes",
      currentBranch.name,
      timeMachineDate,
      params.sourceId,
      params.targetKinds,
      params.maxDepth,
    ],
    queryFn: () =>
      getReachableNodes({
        branchName: currentBranch.name,
        atDate: timeMachineDate,
        ...params,
      }),
    ...config,
  });
}
