import { queryOptions, useQuery } from "@tanstack/react-query";

import type { BranchContextParams } from "@/shared/api/types";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  type GetRepositoryPushStateParams,
  getRepositoryPushState,
} from "@/entities/repository/domain/use-cases/get-repository-push-state";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_ERROR_REFETCH_INTERVAL_MS,
  REPOSITORY_PUSH_PENDING_REFETCH_INTERVAL_MS,
} from "@/entities/repository/ui/queries/repository-polling";

export function getRepositoryPushStateQueryOptions(params: GetRepositoryPushStateParams) {
  return queryOptions({
    queryKey: repositoriesQueryKeys.pushState({ repositoryId: params.repositoryId }),
    queryFn: () => getRepositoryPushState(params),
    // No run reports the end of a push or of an abandon, so the state polls while pushes are pending.
    refetchInterval: ({ state }) => {
      if (state.status === "error") return REPOSITORY_ERROR_REFETCH_INTERVAL_MS;
      return state.data && state.data.status !== "none"
        ? REPOSITORY_PUSH_PENDING_REFETCH_INTERVAL_MS
        : false;
    },
  });
}

// Only the default branch holds the live state; another branch holds an old copy.
export function useGetRepositoryPushState(
  params: Omit<GetRepositoryPushStateParams, keyof BranchContextParams>
) {
  const defaultBranch = useDefaultBranch();

  return useQuery({
    ...getRepositoryPushStateQueryOptions({ ...params, branchName: defaultBranch?.name ?? "" }),
    enabled: !!defaultBranch,
  });
}
