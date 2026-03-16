import { type UseQueryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import {
  type GetPathTraversalParams,
  getPathTraversal,
  type PathTraversalResponse,
} from "./get-path-traversal";
import { pathTraversalKeys } from "./path-traversal.query-keys";

type UseGetPathTraversalParams = Omit<GetPathTraversalParams, "branchName" | "atDate">;

type UseGetPathTraversalConfig = Partial<UseQueryOptions<PathTraversalResponse>>;

export function useGetPathTraversal(
  params: UseGetPathTraversalParams,
  config?: UseGetPathTraversalConfig
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    queryKey: pathTraversalKeys.traverse({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    queryFn: () =>
      getPathTraversal({
        branchName: currentBranch.name,
        atDate: timeMachineDate,
        ...params,
      }),
    ...config,
  });
}
