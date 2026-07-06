import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { GetPathTraversalParams } from "@/entities/path-traversal/domain/model/path-traversal";
import { getPathTraversal } from "@/entities/path-traversal/domain/use-cases/get-path-traversal";
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
