import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import {
  GetRepositoryObjectsCountParams,
  getRepositoryObjectsCount,
} from "@/entities/repository/domain/get-repository-objects-count";
import { ContextParams, QueryConfig } from "@/shared/api/types";
import { queryOptions, useQuery } from "@tanstack/react-query";

export function getRepositoryObjectsCountQueryOption(params: GetRepositoryObjectsCountParams) {
  return queryOptions({
    queryKey: [params.branchName, "objects", params.nodeId, "objects", "count"],
    queryFn: () => getRepositoryObjectsCount(params),
  });
}

export type useGetRepositoryObjectsCountOptions = QueryConfig<
  typeof getRepositoryObjectsCountQueryOption
>;

export function useGetRepositoryObjectsCount(
  params: Omit<GetRepositoryObjectsCountParams, keyof ContextParams>,
  config: useGetRepositoryObjectsCountOptions = {}
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getRepositoryObjectsCountQueryOption({ ...params, branchName: currentBranch.name }),
    ...config,
  });
}
