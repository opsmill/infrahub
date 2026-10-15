import { queryOptions, useQuery } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import {
  type GetRepositoryPushStateParams,
  getRepositoryPushState,
} from "@/entities/repository/domain/use-cases/get-repository-push-state";

function getRepositoryPushStateQueryOptions(params: GetRepositoryPushStateParams) {
  return queryOptions({
    queryKey: [
      ...objectQueryKeys.lists({
        branchName: params.branchName,
        atDate: null,
        objectKind: REPOSITORY_KIND,
      }),
      params.repositoryId,
      "push-state",
    ],
    queryFn: () => getRepositoryPushState(params),
  });
}

// Only the default branch holds the live state; another branch holds an old copy.
export function useGetRepositoryPushState(
  params: Omit<GetRepositoryPushStateParams, keyof BranchContextParams>
) {
  const { data: branches } = useGetBranches();
  const defaultBranch = branches?.find((branch) => branch.is_default);

  return useQuery({
    ...getRepositoryPushStateQueryOptions({ ...params, branchName: defaultBranch?.name ?? "" }),
    enabled: !!defaultBranch,
  });
}
