import { type QueryClient, queryOptions, useQuery } from "@tanstack/react-query";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { RepositoryActivity } from "@/entities/repository/domain/model/repository-activity";
import { isRepositoryActivityAccessDenied } from "@/entities/repository/domain/rules/repository-activity-error";
import {
  type GetRepositoryActivityParams,
  getRepositoryActivity,
} from "@/entities/repository/domain/use-cases/get-repository-activity";
import {
  repositoriesQueryKeys,
  repositoryQueryKeys,
} from "@/entities/repository/ui/queries/repository.query-keys";
import {
  REPOSITORY_ACTIVITY_ACTIVE_REFETCH_INTERVAL_MS,
  REPOSITORY_ACTIVITY_IDLE_REFETCH_INTERVAL_MS,
  REPOSITORY_ERROR_REFETCH_INTERVAL_MS,
} from "@/entities/repository/ui/queries/repository-polling";

function hasRunEnded(previous: RepositoryActivity, next: RepositoryActivity): boolean {
  return previous.activeRuns.some(
    ({ runId }) => !next.activeRuns.some((run) => run.runId === runId)
  );
}

// Not awaited, so the card shows the finished run without waiting for the rest of the page.
function refreshWhatARunChanges(
  client: QueryClient,
  { id, branchName }: GetRepositoryActivityParams
) {
  client.invalidateQueries({
    queryKey: repositoriesQueryKeys.repository({ repositoryId: id, branchName }),
  });
  client.invalidateQueries({ queryKey: repositoryQueryKeys.branchStatuses() });
  client.invalidateQueries({ queryKey: objectQueryKeys.all });
}

export function getRepositoryActivityQueryOptions(params: GetRepositoryActivityParams) {
  const queryKey = repositoriesQueryKeys.activity({ repositoryId: params.id });

  return queryOptions({
    queryKey,
    queryFn: async ({ client }) => {
      const activity = await getRepositoryActivity(params);
      const previous = client.getQueryData<RepositoryActivity>(queryKey);

      if (previous && hasRunEnded(previous, activity)) {
        refreshWhatARunChanges(client, params);
      }

      return activity;
    },
    refetchInterval: ({ state }) => {
      if (isRepositoryActivityAccessDenied(state.error)) return false;
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
