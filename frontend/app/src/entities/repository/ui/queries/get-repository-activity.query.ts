import { queryOptions, useQuery } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type GetRepositoryActivityParams,
  getRepositoryActivity,
} from "@/entities/repository/domain/use-cases/get-repository-activity";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_ACTIVITY_ACTIVE_REFETCH_INTERVAL_MS,
  REPOSITORY_ACTIVITY_IDLE_REFETCH_INTERVAL_MS,
  REPOSITORY_ERROR_REFETCH_INTERVAL_MS,
} from "@/entities/repository/ui/queries/repository-polling";

export function getRepositoryActivityQueryOptions(params: GetRepositoryActivityParams) {
  return queryOptions({
    queryKey: repositoriesQueryKeys.activity({ repositoryId: params.id }),
    queryFn: () => getRepositoryActivity(params),
    refetchInterval: ({ state }) => {
      if (state.status === "error") return REPOSITORY_ERROR_REFETCH_INTERVAL_MS;
      return state.data?.activeRuns.length
        ? REPOSITORY_ACTIVITY_ACTIVE_REFETCH_INTERVAL_MS
        : REPOSITORY_ACTIVITY_IDLE_REFETCH_INTERVAL_MS;
    },
  });
}

export interface UseGetRepositoryActivityParams {
  repositoryId: string;
}

export function useGetRepositoryActivity({ repositoryId }: UseGetRepositoryActivityParams) {
  const { currentBranch } = useCurrentBranch();

  return useQuery(
    getRepositoryActivityQueryOptions({ id: repositoryId, branchName: currentBranch.name })
  );
}
