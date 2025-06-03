import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  GetRepositoryGroupParams,
  getRepositoryGroup,
} from "@/entities/repository/domain/get-repository-group";
import { ContextParams, QueryConfig } from "@/shared/api/types";
import { queryOptions, useQuery } from "@tanstack/react-query";

export function getRepositoryGroupQueryOption(params: GetRepositoryGroupParams) {
  return queryOptions({
    queryKey: [params.branchName, "objects", params.nodeId],
    queryFn: () => getRepositoryGroup(params),
  });
}

export type useGetRepositoryGroupOptions = QueryConfig<typeof getRepositoryGroupQueryOption>;

export function useGetRepositoryGroup(
  params: Omit<GetRepositoryGroupParams, keyof ContextParams>,
  config: useGetRepositoryGroupOptions = {}
) {
  const { currentBranch } = useCurrentBranch();

  return useQuery({
    ...getRepositoryGroupQueryOption({ ...params, branchName: currentBranch.name }),
    ...config,
  });
}
