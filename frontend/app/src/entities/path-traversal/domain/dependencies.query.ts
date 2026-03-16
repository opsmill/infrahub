import { type UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import {
  type DependencyResponse,
  type GetDependenciesParams,
  getDependencies,
} from "./get-dependencies";

type UseDependenciesParams = Omit<GetDependenciesParams, "branchName" | "atDate">;
type UseDependenciesConfig = Partial<UseQueryOptions<DependencyResponse>>;

export function useGetDependencies(params: UseDependenciesParams, config?: UseDependenciesConfig) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    queryKey: [
      "dependencies",
      currentBranch.name,
      timeMachineDate,
      params.sourceId,
      params.targetKinds,
      params.maxDepth,
    ],
    queryFn: () =>
      getDependencies({
        branchName: currentBranch.name,
        atDate: timeMachineDate,
        ...params,
      }),
    ...config,
  });
}
