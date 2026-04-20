import { type UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import {
  type GetReachableObjectsParams,
  type ReachableObjectsResponse,
  getReachableObjects,
} from "./get-reachable-objects";

type UseReachableObjectsParams = Omit<GetReachableObjectsParams, "branchName" | "atDate">;
type UseReachableObjectsConfig = Partial<UseQueryOptions<ReachableObjectsResponse>>;

export function useGetReachableObjects(
  params: UseReachableObjectsParams,
  config?: UseReachableObjectsConfig
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    queryKey: [
      "reachable-objects",
      currentBranch.name,
      timeMachineDate,
      params.sourceId,
      params.targetKinds,
      params.maxDepth,
    ],
    queryFn: () =>
      getReachableObjects({
        branchName: currentBranch.name,
        atDate: timeMachineDate,
        ...params,
      }),
    ...config,
  });
}
