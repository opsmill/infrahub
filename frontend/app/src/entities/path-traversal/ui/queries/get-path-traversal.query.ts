import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getPathTraversal } from "@/entities/path-traversal/domain/get-path-traversal";
import type { GetPathTraversalParams } from "@/entities/path-traversal/domain/path-traversal.types";
import { pathTraversalQueryKeys } from "@/entities/path-traversal/ui/queries/path-traversal.query-keys";

export function getPathTraversalQueryOptions(params: GetPathTraversalParams) {
  return queryOptions({
    queryKey: pathTraversalQueryKeys.traverse(params),
    queryFn: () => getPathTraversal(params),
  });
}

type UseGetPathTraversalParams = Omit<GetPathTraversalParams, "branchName" | "atDate">;

export function useGetPathTraversal(
  params: UseGetPathTraversalParams,
  config?: QueryConfig<typeof getPathTraversalQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...getPathTraversalQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
